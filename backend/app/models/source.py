from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


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


class Source(SQLModel, table=True):
    """Source configuration for crawling."""

    __tablename__ = "sources"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    url: str
    source_type: SourceType = Field(default=SourceType.RSS)
    category_hint: CategoryHint = Field(default=CategoryHint.GENERAL)
    crawl_interval_minutes: int = Field(default=5)
    enabled: bool = Field(default=True)
    config: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    last_crawled_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CrawledContent(SQLModel, table=True):
    """Crawled content from sources."""

    __tablename__ = "crawled_contents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    source_id: str = Field(foreign_key="sources.id", index=True)
    title: str
    content: str
    summary_manual: str | None = Field(default=None)
    image_urls: list[str] = Field(default=[], sa_column=Column(JSON))
    source_url: str = Field(unique=True)
    published_at: datetime
    metadata: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    category_hint: CategoryHint = Field(default=CategoryHint.GENERAL)
    thread_status: ThreadStatus = Field(default=ThreadStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
