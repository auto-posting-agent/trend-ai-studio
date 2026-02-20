from pydantic import BaseModel, HttpUrl
from datetime import datetime
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    RSS = "rss"
    PLAYWRIGHT = "playwright"
    API = "api"


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
    summary_manual: str | None = None
    image_urls: list[str] = []
    source_url: HttpUrl
    published_at: datetime
    metadata: dict[str, Any] = {}
    category_hint: CategoryHint = CategoryHint.GENERAL
    thread_status: ThreadStatus = ThreadStatus.PENDING

    class Config:
        json_schema_extra = {
            "example": {
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "OpenAI Releases GPT-5",
                "content": "OpenAI has announced the release of GPT-5...",
                "summary_manual": "GPT-5 brings significant improvements...",
                "image_urls": ["https://example.com/image.jpg"],
                "source_url": "https://techcrunch.com/article",
                "published_at": "2026-02-21T10:00:00Z",
                "metadata": {"author": "John Doe", "likes": 1500},
                "category_hint": "llm",
                "thread_status": "pending",
            }
        }
