from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.services.crawler.google_blog_ingest import crawl_and_upsert_google_blog_article


async def _run(url: str, dry_run: bool, html_file: str | None, trust_env: bool) -> None:
    html = Path(html_file).read_text(encoding="utf-8") if html_file else None
    result = await crawl_and_upsert_google_blog_article(
        url,
        dry_run=dry_run,
        html=html,
        trust_env=trust_env,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl one Google Blog article and upsert it into Supabase DB."
    )
    parser.add_argument("url", help="Target Google Blog article URL")
    parser.add_argument(
        "--html-file",
        help="Use local HTML file instead of live HTTP fetch.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Allow httpx to use environment proxy variables.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Crawl only, do not write to DB.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.url, args.dry_run, args.html_file, args.trust_env))


if __name__ == "__main__":
    main()
