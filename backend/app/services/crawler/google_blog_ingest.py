from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.database import async_session
from app.models.source import (
    CategoryHint,
    ContentType,
    CrawledContent,
    Source,
    SourceType as SourceConfigType,
    ThreadStatus,
)
from app.services.crawler.google_blog import crawl_google_blog_article


ALLOWED_HOSTS = {"blog.google", "www.blog.google"}
DEFAULT_SOURCE_NAME = "Google Blog (Innovation & AI)"
DEFAULT_SOURCE_URL = "https://blog.google/innovation-and-ai/"


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_utc_naive(dt: datetime | None) -> datetime:
    if dt is None:
        return _now_utc_naive()
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _validate_google_blog_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Only https URLs are allowed.")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("Only blog.google URLs are allowed for this crawler.")


def _map_category(hints: list[str]) -> CategoryHint:
    lowered = {h.lower() for h in hints}
    if {"gemini", "google", "llm"} & lowered:
        return CategoryHint.LLM
    if {"research", "benchmark"} & lowered:
        return CategoryHint.RESEARCH
    return CategoryHint.GENERAL


def _map_source_type() -> SourceConfigType:
    return SourceConfigType.HTML_ARTICLE


def _map_content_type(raw_type: str) -> ContentType:
    mapped = {
        "MODEL_RELEASE": ContentType.MODEL_RELEASE,
        "RESEARCH_PAPER": ContentType.RESEARCH_PAPER,
        "TOOLING": ContentType.TOOL_LAUNCH,
        "PRODUCT_UPDATE": ContentType.COMPANY_NEWS,
        "BENCHMARK": ContentType.RESEARCH_PAPER,
        "OPINION": ContentType.COMMUNITY_POST,
        "FUNDING": ContentType.COMPANY_NEWS,
        "SECURITY": ContentType.COMPANY_NEWS,
        "OTHER": ContentType.GENERAL,
    }
    return mapped.get(raw_type, ContentType.GENERAL)


async def _get_or_create_source() -> Source:
    async with async_session() as session:
        stmt = select(Source).where(
            Source.url == DEFAULT_SOURCE_URL,
            Source.source_type == SourceConfigType.PLAYWRIGHT,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        source = Source(
            name=DEFAULT_SOURCE_NAME,
            url=DEFAULT_SOURCE_URL,
            source_type=SourceConfigType.PLAYWRIGHT,
            category_hint=CategoryHint.LLM,
            crawl_interval_minutes=60,
            enabled=True,
            config={"crawler": "google_blog"},
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)
        return source


async def crawl_and_upsert_google_blog_article(
    url: str,
    *,
    dry_run: bool = False,
    html: str | None = None,
    trust_env: bool = False,
) -> dict[str, Any]:
    _validate_google_blog_url(url)
    item = await crawl_google_blog_article(url, html=html, trust_env=trust_env)

    canonical_url = str(item.canonical_url or item.source_url)
    payload = {
        "canonical_url": canonical_url,
        "title": item.title,
        "published_at": _to_utc_naive(item.published_at).isoformat(),
        "summary_hint": item.summary_hint,
        "content_hash": item.content_hash,
        "image_count": len(item.image_urls),
        "outbound_count": len(item.outbound_urls),
    }

    if dry_run:
        return {
            "status": "dry_run",
            "message": "Crawl succeeded; no DB write was performed.",
            "result": payload,
        }

    source = await _get_or_create_source()
    now = _now_utc_naive()
    category = _map_category(item.category_hint)
    source_type = _map_source_type()
    content_type = _map_content_type(item.content_type.name)
    image_urls = [str(u) for u in item.image_urls]
    outbound_urls = [str(u) for u in item.outbound_urls]

    extra_data = {
        "crawler": "google_blog",
        "category_hint_raw": item.category_hint,
        "metadata": item.metadata,
    }

    async with async_session() as session:
        stmt = select(CrawledContent).where(CrawledContent.source_url == canonical_url)
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.source_id = source.id
            existing.title = item.title
            existing.content = item.content
            existing.summary_hint = item.summary_hint
            existing.image_urls = image_urls
            existing.published_at = _to_utc_naive(item.published_at)
            existing.extra_data = extra_data
            existing.category_hint = category
            existing.thread_status = ThreadStatus.PENDING
            existing.content_hash = item.content_hash
            existing.source_type = source_type
            existing.source_name = item.source_name
            existing.canonical_url = canonical_url
            existing.fetched_at = _to_utc_naive(item.fetched_at)
            existing.author = item.author
            existing.image_positions = item.image_positions
            existing.outbound_urls = outbound_urls
            existing.content_type = content_type
            existing.tags = item.tags
            existing.language = item.language or "en"
            existing.raw_payload = item.raw_payload
            existing.updated_at = now
            action = "updated"
            db_id = existing.id
        else:
            record = CrawledContent(
                source_id=source.id,
                title=item.title,
                content=item.content,
                summary_hint=item.summary_hint,
                image_urls=image_urls,
                source_url=canonical_url,
                published_at=_to_utc_naive(item.published_at),
                extra_data=extra_data,
                category_hint=category,
                thread_status=ThreadStatus.PENDING,
                content_hash=item.content_hash,
                source_type=source_type,
                source_name=item.source_name,
                canonical_url=canonical_url,
                fetched_at=_to_utc_naive(item.fetched_at),
                author=item.author,
                image_positions=item.image_positions,
                outbound_urls=outbound_urls,
                content_type=content_type,
                tags=item.tags,
                language=item.language or "en",
                raw_payload=item.raw_payload,
            )
            session.add(record)
            await session.flush()
            action = "inserted"
            db_id = record.id

        source_stmt = select(Source).where(Source.id == source.id)
        source_ref = (await session.execute(source_stmt)).scalar_one()
        source_ref.last_crawled_at = now
        source_ref.updated_at = now

        await session.commit()

    return {
        "status": action,
        "record_id": db_id,
        "source_id": source.id,
        "result": payload,
    }
