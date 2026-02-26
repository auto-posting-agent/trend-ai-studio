from pydantic import BaseModel, HttpUrl
from datetime import datetime
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    RSS = "rss"
    PLAYWRIGHT = "playwright"
    API = "api"
    HTML_ARTICLE = "html_article"
    RSS_ENTRY = "rss_entry"
    GITHUB_REPO = "github_repo"
    PRODUCT_HUNT = "product_hunt"


class CategoryHint(str, Enum):
    LLM = "llm"
    HARDWARE = "hardware"
    POLICY = "policy"
    STARTUP = "startup"
    RESEARCH = "research"
    STOCK = "stock"
    CRYPTO = "crypto"
    GENERAL = "general"


class ThreadStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    READY = "ready"
    PUBLISHED = "published"
    FAILED = "failed"


class ContentType(str, Enum):
    MODEL_RELEASE = "model_release"
    BREAKING_NEWS = "breaking_news"
    RESEARCH_PAPER = "research_paper"
    TOOL_LAUNCH = "tool_launch"
    MARKET_UPDATE = "market_update"
    COMPANY_NEWS = "company_news"
    COMMUNITY_POST = "community_post"
    GENERAL = "general"


class SourceCreate(BaseModel):
    name: str
    url: HttpUrl
    source_type: SourceType
    category_hint: CategoryHint = CategoryHint.GENERAL
    crawl_interval_minutes: int = 5
    enabled: bool = True
    config: dict[str, Any] | None = None


class SourceResponse(BaseModel):
    id: str
    name: str
    url: HttpUrl
    source_type: SourceType
    category_hint: CategoryHint
    crawl_interval_minutes: int
    enabled: bool
    config: dict[str, Any] | None
    last_crawled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CrawledContent(BaseModel):
    """Data schema for crawled content - matches the spec from user."""
    source_id: str
    title: str
    content: str
    summary_hint: str | None = None
    image_urls: list[str] = []
    source_url: HttpUrl
    published_at: datetime
    extra_data: dict[str, Any] = {}
    category_hint: CategoryHint = CategoryHint.GENERAL
    thread_status: ThreadStatus = ThreadStatus.PENDING
    content_hash: str | None = None
    source_type: SourceType = SourceType.HTML_ARTICLE
    source_name: str | None = None
    canonical_url: HttpUrl | None = None
    fetched_at: datetime
    author: str | None = None
    image_positions: list[dict[str, Any]] = []
    outbound_urls: list[HttpUrl] = []
    content_type: ContentType = ContentType.GENERAL
    tags: list[str] = []
    language: str = "en"
    raw_payload: dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "OpenAI Releases GPT-5",
                "content": "OpenAI has announced the release of GPT-5...",
                "summary_hint": "GPT-5 brings significant improvements...",
                "image_urls": ["https://example.com/image.jpg"],
                "source_url": "https://techcrunch.com/article",
                "published_at": "2026-02-21T10:00:00Z",
                "extra_data": {"author": "John Doe", "likes": 1500},
                "category_hint": "llm",
                "thread_status": "pending",
                "content_hash": "hash",
                "source_type": "html_article",
                "source_name": "Google Blog",
                "canonical_url": "https://techcrunch.com/article",
                "fetched_at": "2026-02-21T10:01:00Z",
                "author": "John Doe",
                "image_positions": [],
                "outbound_urls": ["https://example.com/ref"],
                "content_type": "general",
                "tags": ["ai", "news"],
                "language": "en",
                "raw_payload": {},
            }
        }
