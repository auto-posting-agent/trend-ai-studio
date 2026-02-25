from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


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
    summary_hint: str | None = Field(default=None)
    image_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_url: str = Field(unique=True)
    published_at: datetime
    extra_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    category_hint: CategoryHint = Field(default=CategoryHint.GENERAL)
    thread_status: ThreadStatus = Field(default=ThreadStatus.PENDING)
    content_hash: str | None = Field(default=None)
    source_type: SourceType = Field(default=SourceType.HTML_ARTICLE)
    source_name: str | None = Field(default=None)
    canonical_url: str | None = Field(default=None)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    author: str | None = Field(default=None)
    image_positions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    outbound_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    content_type: ContentType = Field(default=ContentType.GENERAL)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    language: str = Field(default="en")
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
