from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

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


DEFAULT_CATALOG = (
    Path(__file__).resolve().parents[2] / "crawl_targets" / "source_catalog.yaml"
)


@dataclass
class SourceSample:
    source_catalog_id: str
    source_name: str
    source_kind: str
    source_feed_url: str
    url: str
    title: str
    published_raw: str | None
    published_at: datetime | None


@dataclass
class SampleCrawlResult:
    final_url: str
    canonical_url: str
    title: str
    summary_hint: str | None
    content: str
    author: str | None
    published_at: datetime | None
    image_urls: list[str]
    outbound_urls: list[str]
    language: str
    raw_payload: dict[str, Any]


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


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root object: {path}")
    return data


def _sorted_items_by_recency(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []
    with_time = []
    without_time = []
    for idx, item in enumerate(items):
        p = _parse_datetime(item.get("published"))
        if p:
            with_time.append((p, idx, item))
        else:
            without_time.append((idx, item))
    ranked: list[dict[str, Any]] = []
    if with_time:
        with_time.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        ranked.extend([x[2] for x in with_time])
    without_time.sort(key=lambda x: x[0])
    ranked.extend([x[1] for x in without_time])
    return ranked


def _collect_one_each(
    discovery: dict[str, Any],
    *,
    catalog: dict[str, Any],
) -> tuple[list[SourceSample], list[dict[str, Any]]]:
    source_map = {str(s.get("id")): s for s in (catalog.get("sources") or [])}
    samples: list[SourceSample] = []
    skipped: list[dict[str, Any]] = []
    selected_urls: set[str] = set()

    for src in discovery.get("sources") or []:
        sid = str(src.get("id"))
        if not src.get("ok"):
            skipped.append(
                {
                    "source_catalog_id": sid,
                    "reason": "source_failed",
                    "error": src.get("error"),
                }
            )
            continue
        items = src.get("items") or []
        if not items:
            skipped.append(
                {
                    "source_catalog_id": sid,
                    "reason": "no_items",
                }
            )
            continue
        ranked = _sorted_items_by_recency(items)
        best: dict[str, Any] | None = None
        for item in ranked:
            candidate_url = str(item.get("url") or "").strip()
            if candidate_url and candidate_url not in selected_urls:
                best = item
                break
        if best is None and ranked:
            # Fallback: all candidates duplicated by URL across feeds.
            best = ranked[0]
            skipped.append(
                {
                    "source_catalog_id": sid,
                    "reason": "url_conflict_all_candidates",
                    "url": str(best.get("url") or ""),
                }
            )
        if best is None:
            skipped.append(
                {
                    "source_catalog_id": sid,
                    "reason": "no_selectable_item",
                }
            )
            continue

        url = str(best.get("url") or "").strip()
        if not url:
            skipped.append(
                {
                    "source_catalog_id": sid,
                    "reason": "empty_url",
                }
            )
            continue
        selected_urls.add(url)

        published_raw = best.get("published")
        samples.append(
            SourceSample(
                source_catalog_id=sid,
                source_name=str(src.get("name") or sid),
                source_kind=str(src.get("type") or ""),
                source_feed_url=str((source_map.get(sid) or {}).get("url") or ""),
                url=url,
                title=str(best.get("title") or url),
                published_raw=str(published_raw) if published_raw else None,
                published_at=_parse_datetime(published_raw),
            )
        )

    return samples, skipped


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
    session,
    cache: dict[tuple[str, str], Source],
    *,
    source_name: str,
    source_url: str,
    source_kind: str,
    source_catalog_id: str,
) -> Source:
    key = (source_name, source_url)
    if key in cache:
        return cache[key]

    stmt = select(Source).where(Source.name == source_name, Source.url == source_url)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        cache[key] = existing
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
            "seed_mode": "one_per_source",
        },
    )
    session.add(source)
    await session.flush()
    cache[key] = source
    return source


async def _upsert_one(
    session,
    source_cache: dict[tuple[str, str], Source],
    sample: SourceSample,
    *,
    crawl_details: bool,
    allow_fallback: bool,
    trust_env: bool,
) -> str:
    now = _now_utc_naive()
    source = await _get_or_create_source(
        session,
        source_cache,
        source_name=sample.source_name,
        source_url=sample.source_feed_url,
        source_kind=sample.source_kind,
        source_catalog_id=sample.source_catalog_id,
    )
    crawl: SampleCrawlResult | None = None
    crawl_error: str | None = None

    if crawl_details:
        try:
            fetched = await crawl_generic_article(sample.url, trust_env=trust_env)
            if not _content_looks_valid(fetched.content, fetched.title):
                raise ValueError("low_quality_content")
            crawl = SampleCrawlResult(
                final_url=fetched.final_url,
                canonical_url=fetched.canonical_url,
                title=fetched.title,
                summary_hint=fetched.summary_hint,
                content=fetched.content,
                author=fetched.author,
                published_at=fetched.published_at,
                image_urls=fetched.image_urls,
                outbound_urls=fetched.outbound_urls,
                language=fetched.language or "en",
                raw_payload=fetched.raw_payload,
            )
        except Exception as e:  # noqa: BLE001
            crawl_error = f"{type(e).__name__}: {e}"
            if not allow_fallback:
                raise RuntimeError(f"crawl_failed: {crawl_error}") from e

    effective_url = (crawl.final_url if crawl else sample.url).strip()
    canonical_url = (crawl.canonical_url if crawl else sample.url).strip()
    title = (crawl.title if crawl else sample.title) or sample.url
    content = (crawl.content if crawl else sample.title) or title
    summary_hint = (crawl.summary_hint if crawl else sample.title) or title
    author = crawl.author if crawl else None
    published_at = (crawl.published_at if crawl else sample.published_at) or now
    image_urls = crawl.image_urls if crawl else []
    outbound_urls = crawl.outbound_urls if crawl else []
    language = (crawl.language if crawl else "en") or "en"

    hash_basis = f"{canonical_url}\n{title}\n{published_at.isoformat()}\n{content[:800]}"
    content_hash = hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()

    stmt = select(CrawledContent).where(
        or_(
            CrawledContent.source_url == effective_url,
            CrawledContent.canonical_url == canonical_url,
        )
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    common = {
        "source_id": source.id,
        "title": title,
        "content": content,
        "summary_hint": summary_hint,
        "source_url": effective_url,
        "canonical_url": canonical_url,
        "published_at": published_at,
        "category_hint": CategoryHint.GENERAL,
        "thread_status": ThreadStatus.PENDING,
        "content_hash": content_hash,
        "source_type": SourceType.HTML_ARTICLE if crawl else _map_source_type_for_content(sample.source_kind),
        "source_name": sample.source_name,
        "fetched_at": now,
        "content_type": ContentType.GENERAL,
        "language": language,
        "author": author,
        "image_urls": image_urls,
        "outbound_urls": outbound_urls,
        "extra_data": {
            "seed_mode": "one_per_source",
            "crawl_details": crawl_details,
            "discovery": {
                "source_catalog_id": sample.source_catalog_id,
                "source_kind": sample.source_kind,
                "published_raw": sample.published_raw,
            },
            "crawl_error": crawl_error,
        },
        "raw_payload": {
            "candidate": {
                "url": sample.url,
                "title": sample.title,
                "published_raw": sample.published_raw,
            },
            "crawl": crawl.raw_payload if crawl else {},
        },
    }

    if existing:
        existing.source_id = common["source_id"]
        existing.title = common["title"]
        existing.content = common["content"]
        existing.summary_hint = common["summary_hint"]
        existing.source_url = common["source_url"]
        existing.canonical_url = common["canonical_url"]
        existing.published_at = common["published_at"]
        existing.category_hint = common["category_hint"]
        existing.thread_status = common["thread_status"]
        existing.content_hash = common["content_hash"]
        existing.source_type = common["source_type"]
        existing.source_name = common["source_name"]
        existing.fetched_at = common["fetched_at"]
        existing.content_type = common["content_type"]
        existing.language = common["language"]
        existing.author = common["author"]
        existing.image_urls = common["image_urls"]
        existing.outbound_urls = common["outbound_urls"]
        existing.extra_data = common["extra_data"]
        existing.raw_payload = common["raw_payload"]
        existing.updated_at = now
        return "updated"

    session.add(CrawledContent(**common))
    return "inserted"


async def _run(args: argparse.Namespace) -> None:
    catalog = _load_yaml(Path(args.catalog))
    discovery = discover_from_catalog(catalog)
    samples, skipped = _collect_one_each(discovery, catalog=catalog)
    if args.limit_sources and args.limit_sources > 0:
        samples = samples[: args.limit_sources]

    result: dict[str, Any] = {
        "total_sources_configured": discovery.get("configured_sources"),
        "total_sources_run": discovery.get("total_sources"),
        "sources_ok": discovery.get("ok_sources"),
        "sources_failed": discovery.get("failed_sources"),
        "sampled_count": len(samples),
        "skipped": skipped,
        "samples": [
            {
                "source_catalog_id": s.source_catalog_id,
                "source_name": s.source_name,
                "source_kind": s.source_kind,
                "source_feed_url": s.source_feed_url,
                "url": s.url,
                "title": s.title,
                "published_at": s.published_at.isoformat() if s.published_at else None,
                "published_raw": s.published_raw,
            }
            for s in samples
        ],
    }

    if not args.dry_run:
        inserted = 0
        updated = 0
        failed = 0
        errors: list[dict[str, str]] = []

        async with async_session() as session:
            source_cache: dict[tuple[str, str], Source] = {}
            for sample in samples:
                try:
                    action = await _upsert_one(
                        session,
                        source_cache,
                        sample,
                        crawl_details=not args.no_crawl_details,
                        allow_fallback=args.allow_fallback,
                        trust_env=args.trust_env,
                    )
                    if action == "inserted":
                        inserted += 1
                    else:
                        updated += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    errors.append(
                        {
                            "source_catalog_id": sample.source_catalog_id,
                            "url": sample.url,
                            "error": f"{type(e).__name__}: {e}",
                        }
                    )
            await session.commit()

        result["db_result"] = {
            "inserted": inserted,
            "updated": updated,
            "failed": failed,
            "errors": errors,
        }

    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample one item from each enabled source and upsert to DB."
    )
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--out-json",
        default="",
        help="Optional output JSON path. If omitted, no file is written.",
    )
    parser.add_argument(
        "--no-crawl-details",
        action="store_true",
        help="Do not fetch article pages; store feed/index metadata only.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to use environment proxy variables for article crawling.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow metadata-only fallback insert when detail crawling fails.",
    )
    parser.add_argument(
        "--limit-sources",
        type=int,
        default=0,
        help="Optional: process only first N sampled sources (for quick tests).",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
