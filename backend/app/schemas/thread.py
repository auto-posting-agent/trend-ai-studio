from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Any


class ThreadStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class ThreadCreate(BaseModel):
    source_content_id: str | None = None
    content: str
    image_urls: list[str] = []
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = {}


class ThreadResponse(BaseModel):
    id: str
    source_content_id: str | None
    content: str
    image_urls: list[str]
    status: ThreadStatus
    scheduled_at: datetime | None
    published_at: datetime | None
    threads_post_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "source_content_id": "660e8400-e29b-41d4-a716-446655440000",
                "content": "OpenAI just dropped GPT-5 and it's insane...",
                "image_urls": [],
                "status": "ready",
                "scheduled_at": None,
                "published_at": None,
                "threads_post_id": None,
                "metadata": {"topic": "AI", "sentiment": "positive"},
                "created_at": "2026-02-21T10:00:00Z",
                "updated_at": "2026-02-21T10:00:00Z",
            }
        }
