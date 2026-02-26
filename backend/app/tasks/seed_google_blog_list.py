from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.services.crawler.google_blog_ingest import crawl_and_upsert_google_blog_article


DEFAULT_LIST_FILE = (
    Path(__file__).resolve().parents[2] / "crawl_targets" / "google_blog_urls.txt"
)


def _load_urls(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"List file not found: {path}")

    seen: set[str] = set()
    urls: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        urls.append(line)
    return urls


async def _run(
    list_file: Path,
    *,
    dry_run: bool,
    trust_env: bool,
    limit: int | None,
    continue_on_error: bool,
) -> None:
    urls = _load_urls(list_file)
    if limit is not None:
        urls = urls[:limit]

    if not urls:
        print(
            json.dumps(
                {
                    "status": "empty",
                    "message": "No URLs found in list file.",
                    "list_file": str(list_file),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    results: list[dict[str, Any]] = []
    for idx, url in enumerate(urls, start=1):
        print(f"[{idx}/{len(urls)}] {url}")
        try:
            res = await crawl_and_upsert_google_blog_article(
                url,
                dry_run=dry_run,
                trust_env=trust_env,
            )
            results.append({"url": url, "ok": True, "result": res})
        except Exception as e:  # noqa: BLE001
            err = {"url": url, "ok": False, "error": f"{type(e).__name__}: {e}"}
            results.append(err)
            if not continue_on_error:
                break

    success = sum(1 for r in results if r.get("ok"))
    failed = len(results) - success
    summary = {
        "list_file": str(list_file),
        "dry_run": dry_run,
        "processed": len(results),
        "success": success,
        "failed": failed,
        "results": results,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl Google Blog URLs from a list file and upsert to DB."
    )
    parser.add_argument(
        "--list-file",
        default=str(DEFAULT_LIST_FILE),
        help="Path to URL list file (default: backend/crawl_targets/google_blog_urls.txt)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N URLs from the list.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Crawl only, do not write to DB.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to use environment proxy variables.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing other URLs even if one fails.",
    )
    args = parser.parse_args()
    asyncio.run(
        _run(
            Path(args.list_file),
            dry_run=args.dry_run,
            trust_env=args.trust_env,
            limit=args.limit,
            continue_on_error=args.continue_on_error,
        )
    )


if __name__ == "__main__":
    main()
