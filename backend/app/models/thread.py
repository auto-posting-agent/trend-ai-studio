from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class ThreadStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class Thread(SQLModel, table=True):
    """Generated thread content for publishing."""

    __tablename__ = "threads"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    source_content_id: str | None = Field(
        default=None, foreign_key="crawled_contents.id", index=True
    )
    content: str
    image_urls: list[str] = Field(default=[], sa_column=Column(JSON))
    status: ThreadStatus = Field(default=ThreadStatus.PENDING)
    scheduled_at: datetime | None = Field(default=None)
    published_at: datetime | None = Field(default=None)
    threads_post_id: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
