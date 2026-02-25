from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dateutil import parser as dt_parser
from sqlalchemy import or_, select
import yaml

from app.core.database import async_session
from app.models.source import (
    CategoryHint,
    ContentType,
    CrawledContent,
    Source,
    SourceType,
    ThreadStatus,
)
from app.services.crawler.generic_article import crawl_generic_article
from app.tasks.discover_source_urls import discover_from_catalog


DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "crawl_targets" / "source_catalog.yaml"
DEFAULT_TIERS = Path(__file__).resolve().parents[2] / "crawl_targets" / "source_tiers.yaml"


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _content_looks_valid(content: str, title: str) -> bool:
    c = (content or "").strip()
    t = (title or "").strip()
    if not c:
        return False
    if t and c == t:
        return False
    if len(c) < 120 and len(c.split()) < 20:
        return False
    return True


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = dt_parser.parse(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _host_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


@dataclass
class RankedCandidate:
    url: str
    title: str
    published_at: datetime | None
    published_raw: str | None
    source_catalog_id: str
    source_name: str
    source_kind: str
    source_feed_url: str
    tier: int


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root object: {path}")
    return data


def _resolve_tier(
    *,
    url: str,
    source_name: str,
    tier_cfg: dict[str, Any],
) -> int:
    default_tier = int(tier_cfg.get("default_tier", 2))
    host_tiers = {
        str(k).lower(): int(v)
        for k, v in (tier_cfg.get("host_tiers") or {}).items()
    }
    source_name_tiers = {
        str(k).lower(): int(v)
        for k, v in (tier_cfg.get("source_name_tiers") or {}).items()
    }

    host = _host_from_url(url)
    for domain, tier in host_tiers.items():
        if host == domain or host.endswith(f".{domain}"):
            return tier

    lowered_name = (source_name or "").lower()
    for needle, tier in source_name_tiers.items():
        if needle in lowered_name:
            return tier

    return default_tier


def _rank_top_candidates(
    discovery: dict[str, Any],
    *,
    catalog: dict[str, Any],
    tier_cfg: dict[str, Any],
    limit: int,
) -> list[RankedCandidate]:
    source_meta = {str(s.get("id")): s for s in (catalog.get("sources") or [])}
    dedup_seen: set[str] = set()
    tier1: list[RankedCandidate] = []
    non_tier1: list[RankedCandidate] = []

    for src in discovery.get("sources") or []:
        if not src.get("ok"):
            continue
        sid = str(src.get("id"))
        source_name = str(src.get("name") or sid)
        source_kind = str(src.get("type") or "")
        source_feed_url = str((source_meta.get(sid) or {}).get("url") or "")

        for item in src.get("items") or []:
            url = str(item.get("url") or "").strip()
            if not url or url in dedup_seen:
                continue
            dedup_seen.add(url)

            published_raw = item.get("published")
            published_at = _parse_datetime(published_raw)
            title = str(item.get("title") or url).strip()
            tier = _resolve_tier(url=url, source_name=source_name, tier_cfg=tier_cfg)

            candidate = RankedCandidate(
                url=url,
                title=title,
                published_at=published_at,
                published_raw=str(published_raw) if published_raw else None,
                source_catalog_id=sid,
                source_name=source_name,
                source_kind=source_kind,
                source_feed_url=source_feed_url,
                tier=tier,
            )
            if tier == 1:
                tier1.append(candidate)
            else:
                non_tier1.append(candidate)

    def sort_key(c: RankedCandidate) -> tuple[float, str]:
        ts = c.published_at.timestamp() if c.published_at else 0.0
        return (-ts, c.url)

    tier1.sort(key=sort_key)
    non_tier1.sort(key=sort_key)

    selected = tier1[:limit]
    if len(selected) < limit:
        selected.extend(non_tier1[: (limit - len(selected))])
    return selected


def _map_source_type_for_source(source_kind: str) -> SourceType:
    if source_kind in {"rss", "atom"}:
        return SourceType.RSS
    if source_kind == "html_index":
        return SourceType.PLAYWRIGHT
    return SourceType.API


def _map_source_type_for_content(source_kind: str) -> SourceType:
    if source_kind in {"rss", "atom"}:
        return SourceType.RSS_ENTRY
    return SourceType.HTML_ARTICLE


async def _get_or_create_source(
    *,
    source_name: str,
    source_url: str,
    source_kind: str,
    source_catalog_id: str,
) -> Source:
    async with async_session() as session:
        stmt = select(Source).where(Source.url == source_url, Source.name == source_name)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        source = Source(
            name=source_name,
            url=source_url or "https://example.com/",
            source_type=_map_source_type_for_source(source_kind),
            category_hint=CategoryHint.GENERAL,
            crawl_interval_minutes=60,
            enabled=True,
            config={
                "catalog_id": source_catalog_id,
                "catalog_kind": source_kind,
            },
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)
        return source


async def _upsert_candidate(
    candidate: RankedCandidate,
    *,
    allow_fallback: bool,
    trust_env: bool,
) -> str:
    now = _now_utc_naive()
    source = await _get_or_create_source(
        source_name=candidate.source_name,
        source_url=candidate.source_feed_url,
        source_kind=candidate.source_kind,
        source_catalog_id=candidate.source_catalog_id,
    )

    crawl_error: str | None = None
    try:
        crawled = await crawl_generic_article(candidate.url, trust_env=trust_env)
        if not _content_looks_valid(crawled.content, crawled.title):
            raise ValueError("low_quality_content")
        final_url = crawled.final_url
        canonical_url = crawled.canonical_url
        title = crawled.title or candidate.title or candidate.url
        content_text = crawled.content or title
        summary_hint = crawled.summary_hint or candidate.title or title
        author = crawled.author
        published_at = crawled.published_at or candidate.published_at or now
        image_urls = crawled.image_urls
        outbound_urls = crawled.outbound_urls
        language = crawled.language or "en"
        raw_crawl = crawled.raw_payload
        content_source_type = SourceType.HTML_ARTICLE
    except Exception as e:  # noqa: BLE001
        crawl_error = f"{type(e).__name__}: {e}"
        if not allow_fallback:
            raise RuntimeError(f"crawl_failed: {crawl_error}") from e
        final_url = candidate.url
        canonical_url = candidate.url
        title = candidate.title or candidate.url
        content_text = candidate.title or candidate.url
        summary_hint = candidate.title or None
        author = None
        published_at = candidate.published_at or now
        image_urls = []
        outbound_urls = []
        language = "en"
        raw_crawl = {}
        content_source_type = _map_source_type_for_content(candidate.source_kind)

    hash_basis = f"{canonical_url}\n{title}\n{published_at.isoformat()}\n{content_text[:800]}"
    content_hash = hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()

    async with async_session() as session:
        stmt = select(CrawledContent).where(
            or_(
                CrawledContent.source_url == final_url,
                CrawledContent.canonical_url == canonical_url,
            )
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        common_payload = {
            "source_id": source.id,
            "title": title,
            "content": content_text,
            "summary_hint": summary_hint,
            "source_url": final_url,
            "canonical_url": canonical_url,
            "published_at": published_at,
            "category_hint": CategoryHint.GENERAL,
            "thread_status": ThreadStatus.PENDING,
            "content_hash": content_hash,
            "source_type": content_source_type,
            "source_name": candidate.source_name,
            "fetched_at": now,
            "content_type": ContentType.GENERAL,
            "language": language,
            "author": author,
            "image_urls": image_urls,
            "outbound_urls": outbound_urls,
            "extra_data": {
                "discovery": {
                    "source_catalog_id": candidate.source_catalog_id,
                    "source_kind": candidate.source_kind,
                    "published_raw": candidate.published_raw,
                    "tier": candidate.tier,
                },
                "crawl_error": crawl_error,
            },
            "raw_payload": {
                "candidate": {
                    "url": candidate.url,
                    "title": candidate.title,
                    "published_raw": candidate.published_raw,
                    "tier": candidate.tier,
                },
                "crawl": raw_crawl,
            },
        }

        if existing:
            existing.source_id = common_payload["source_id"]
            existing.title = common_payload["title"]
            existing.content = common_payload["content"]
            existing.summary_hint = common_payload["summary_hint"]
            existing.source_url = common_payload["source_url"]
            existing.canonical_url = common_payload["canonical_url"]
            existing.published_at = common_payload["published_at"]
            existing.category_hint = common_payload["category_hint"]
            existing.thread_status = common_payload["thread_status"]
            existing.content_hash = common_payload["content_hash"]
            existing.source_type = common_payload["source_type"]
            existing.source_name = common_payload["source_name"]
            existing.fetched_at = common_payload["fetched_at"]
            existing.content_type = common_payload["content_type"]
            existing.language = common_payload["language"]
            existing.author = common_payload["author"]
            existing.image_urls = common_payload["image_urls"]
            existing.outbound_urls = common_payload["outbound_urls"]
            existing.extra_data = common_payload["extra_data"]
            existing.raw_payload = common_payload["raw_payload"]
            existing.updated_at = now
            action = "updated"
        else:
            record = CrawledContent(**common_payload)
            session.add(record)
            action = "inserted"

        await session.commit()
        return action


async def _run(args: argparse.Namespace) -> None:
    catalog = _load_yaml(Path(args.catalog))
    tiers = _load_yaml(Path(args.tiers))

    discovery = discover_from_catalog(catalog)
    selected = _rank_top_candidates(
        discovery,
        catalog=catalog,
        tier_cfg=tiers,
        limit=args.limit,
    )

    result: dict[str, Any] = {
        "requested_limit": args.limit,
        "selected_count": len(selected),
        "selected": [
            {
                "url": c.url,
                "title": c.title,
                "published_at": c.published_at.isoformat() if c.published_at else None,
                "published_raw": c.published_raw,
                "source_catalog_id": c.source_catalog_id,
                "source_name": c.source_name,
                "source_kind": c.source_kind,
                "source_feed_url": c.source_feed_url,
                "tier": c.tier,
            }
            for c in selected
        ],
    }

    if not args.dry_run:
        inserted = 0
        updated = 0
        failed = 0
        errors: list[dict[str, str]] = []
        for c in selected:
            try:
                action = await _upsert_candidate(
                    c,
                    allow_fallback=args.allow_fallback,
                    trust_env=args.trust_env,
                )
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                errors.append({"url": c.url, "error": f"{type(e).__name__}: {e}"})

        result["db_result"] = {
            "inserted": inserted,
            "updated": updated,
            "failed": failed,
            "errors": errors,
        }

    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover sources and upsert top N priority candidates "
        "(official latest first, fallback to latest overall).",
    )
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--tiers", default=str(DEFAULT_TIERS))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--out-json",
        default="",
        help="Optional output JSON path. If omitted, no file is written.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow metadata-only fallback insert when detail crawling fails.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to use environment proxy variables for article crawling.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
