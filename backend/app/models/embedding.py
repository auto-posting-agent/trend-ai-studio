from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from pgvector.sqlalchemy import Vector
from datetime import datetime


class ContentEmbedding(SQLModel, table=True):
    """Vector embeddings for crawled content."""

    __tablename__ = "content_embeddings"

    content_id: str = Field(
        foreign_key="crawled_contents.id",
        primary_key=True
    )
    embedding: list[float] = Field(sa_column=Column(Vector(3072)))
    extra_data: dict = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
