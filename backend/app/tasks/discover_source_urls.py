from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import feedparser
import httpx
import yaml
from bs4 import BeautifulSoup


@dataclass
class HttpDefaults:
    timeout_sec: float = 20.0
    retries: int = 2
    user_agent: str = "TrendAIStudioBot/0.1"
    trust_env: bool = False


def _normalize_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def _is_http_url(url: str) -> bool:
    scheme = (urlparse(url).scheme or "").lower()
    return scheme in {"http", "https"}


def _extract_feed_items(text: str, limit: int | None) -> list[dict[str, Any]]:
    parsed = feedparser.parse(text)
    out: list[dict[str, Any]] = []
    for ent in parsed.entries:
        link = getattr(ent, "link", None)
        if not link:
            continue
        out.append(
            {
                "url": _normalize_url(str(link)),
                "title": getattr(ent, "title", None),
                "published": getattr(ent, "published", None)
                or getattr(ent, "updated", None),
            }
        )
        if limit and len(out) >= limit:
            break
    return out


def _extract_index_items(
    base_url: str,
    html: str,
    *,
    allow_prefixes: list[str] | None,
    deny_prefixes: list[str] | None,
    allow_regexes: list[str] | None,
    deny_regexes: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    allow_prefixes = allow_prefixes or []
    deny_prefixes = deny_prefixes or []
    allow_regexes = allow_regexes or []
    deny_regexes = deny_regexes or []
    allow_patterns = [re.compile(p) for p in allow_regexes]
    deny_patterns = [re.compile(p) for p in deny_regexes]

    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a.get("href", ""))
        if not _is_http_url(full):
            continue
        norm = _normalize_url(full)

        if allow_prefixes and not any(norm.startswith(p) for p in allow_prefixes):
            continue
        if any(norm.startswith(p) for p in deny_prefixes):
            continue
        if allow_patterns and not any(p.search(norm) for p in allow_patterns):
            continue
        if any(p.search(norm) for p in deny_patterns):
            continue
        if norm in seen:
            continue

        seen.add(norm)
        title = a.get_text(" ", strip=True) or None
        out.append({"url": norm, "title": title, "published": None})
        if limit and len(out) >= limit:
            break

    return out


def _request_with_retries(
    client: httpx.Client,
    url: str,
    *,
    retries: int,
) -> httpx.Response:
    last_err: Exception | None = None
    for _ in range(max(1, retries + 1)):
        try:
            res = client.get(url)
            res.raise_for_status()
            return res
        except Exception as e:  # noqa: BLE001
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError("Unexpected retry state")


def discover_from_catalog(
    catalog: dict[str, Any],
    *,
    only_ids: set[str] | None = None,
) -> dict[str, Any]:
    http_cfg = (catalog.get("defaults") or {}).get("http") or {}
    defaults = HttpDefaults(
        timeout_sec=float(http_cfg.get("timeout_sec", 20)),
        retries=int(http_cfg.get("retries", 2)),
        user_agent=str(http_cfg.get("user_agent", "TrendAIStudioBot/0.1")),
        trust_env=bool(http_cfg.get("trust_env", False)),
    )

    sources = catalog.get("sources") or []
    selected_sources = [
        src
        for src in sources
        if not only_ids or str(src.get("id", "")).strip() in only_ids
    ]
    results: list[dict[str, Any]] = []
    flat_urls: list[str] = []
    skipped_ids: list[str] = []

    with httpx.Client(
        timeout=defaults.timeout_sec,
        follow_redirects=True,
        headers={"User-Agent": defaults.user_agent},
        trust_env=defaults.trust_env,
    ) as client:
        for src in selected_sources:
            sid = str(src.get("id"))
            enabled = bool(src.get("enabled", True))
            if not enabled:
                skipped_ids.append(sid)
                continue

            stype = str(src.get("type", "")).lower()
            url = str(src.get("url", "")).strip()
            limit = int(src.get("limit", 30))
            allow_prefixes = src.get("allow_prefixes") or []
            deny_prefixes = src.get("deny_prefixes") or []
            allow_regexes = src.get("allow_regexes") or []
            deny_regexes = src.get("deny_regexes") or []

            if not url:
                results.append(
                    {"id": sid, "ok": False, "error": "missing url", "items": []}
                )
                continue

            try:
                res = _request_with_retries(client, url, retries=defaults.retries)

                if stype in {"rss", "atom"}:
                    items = _extract_feed_items(res.text, limit)
                    if allow_prefixes:
                        items = [
                            it
                            for it in items
                            if any(it["url"].startswith(p) for p in allow_prefixes)
                        ]
                    if deny_prefixes:
                        items = [
                            it
                            for it in items
                            if not any(it["url"].startswith(p) for p in deny_prefixes)
                        ]
                elif stype == "html_index":
                    items = _extract_index_items(
                        str(res.url),
                        res.text,
                        allow_prefixes=allow_prefixes,
                        deny_prefixes=deny_prefixes,
                        allow_regexes=allow_regexes,
                        deny_regexes=deny_regexes,
                        limit=limit,
                    )
                else:
                    results.append(
                        {
                            "id": sid,
                            "ok": False,
                            "error": f"unsupported source type: {stype}",
                            "items": [],
                        }
                    )
                    continue

                results.append(
                    {
                        "id": sid,
                        "name": src.get("name"),
                        "type": stype,
                        "ok": True,
                        "count": len(items),
                        "items": items,
                    }
                )
                flat_urls.extend([it["url"] for it in items])
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": sid,
                        "name": src.get("name"),
                        "type": stype,
                        "ok": False,
                        "error": f"{type(e).__name__}: {e}",
                        "items": [],
                    }
                )

    unique_urls = list(dict.fromkeys(flat_urls))
    return {
        "version": catalog.get("version"),
        "configured_sources": len(selected_sources),
        "total_sources": len(results),
        "skipped_sources": len(skipped_ids),
        "skipped_ids": skipped_ids,
        "ok_sources": sum(1 for r in results if r.get("ok")),
        "failed_sources": sum(1 for r in results if not r.get("ok")),
        "unique_url_count": len(unique_urls),
        "urls": unique_urls,
        "sources": results,
    }


def main() -> None:
    default_catalog = (
        Path(__file__).resolve().parents[2] / "crawl_targets" / "source_catalog.yaml"
    )
    parser = argparse.ArgumentParser(
        description="Discover latest article URLs from source catalog."
    )
    parser.add_argument(
        "--catalog",
        default=str(default_catalog),
        help="Path to source catalog YAML file.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional source IDs to run (space-separated).",
    )
    parser.add_argument(
        "--out-json",
        default="",
        help="Optional output JSON path.",
    )
    parser.add_argument(
        "--out-urls",
        default="",
        help="Optional output plain-text URL list path.",
    )
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise SystemExit(f"Catalog file not found: {catalog_path}")

    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    only_ids = set(args.only) if args.only else None
    result = discover_from_catalog(catalog, only_ids=only_ids)

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if args.out_urls:
        out_urls = Path(args.out_urls)
        out_urls.parent.mkdir(parents=True, exist_ok=True)
        out_urls.write_text("\n".join(result["urls"]) + "\n", encoding="utf-8")

    # Windows CP949 consoles can fail on non-ASCII feed text/emojis.
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
