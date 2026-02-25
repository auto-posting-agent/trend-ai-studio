from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import asc, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import CrawledContent, Source
from app.services.vector.embedder import VectorEmbedder


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _host_from_url(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).hostname or "").lower()


class TrendCandidateSelector:
    """Select trend candidates using time window, semantic dedup, and source tiers."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tier_config: dict[str, Any] | None = None,
    ) -> None:
        self.session = session
        self.embedder = VectorEmbedder(session)

        cfg = tier_config or {}
        self.default_tier = int(cfg.get("default_tier", 2))
        host_tiers = cfg.get("host_tiers") or {}
        self.host_tiers: dict[str, int] = {
            str(k).lower(): int(v) for k, v in host_tiers.items()
        }

        source_name_tiers = cfg.get("source_name_tiers") or {}
        self.source_name_tiers: dict[str, int] = {
            str(k).lower(): int(v) for k, v in source_name_tiers.items()
        }

    async def _ensure_vector_table(self) -> None:
        # Extension creation can fail if permission is restricted; table check below is decisive.
        try:
            await self.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass

        await self.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS content_embeddings (
                    content_id TEXT PRIMARY KEY REFERENCES crawled_contents(id) ON DELETE CASCADE,
                    embedding vector(768) NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                )
                """
            )
        )
        await self.session.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_content_embeddings_content_id
                ON content_embeddings (content_id)
                """
            )
        )
        await self.session.commit()

    async def _load_recent(
        self,
        *,
        cutoff: datetime,
        max_candidates: int,
    ) -> list[tuple[CrawledContent, Source | None]]:
        stmt = (
            select(CrawledContent, Source)
            .outerjoin(Source, Source.id == CrawledContent.source_id)
            .where(
                or_(
                    CrawledContent.published_at >= cutoff,
                    CrawledContent.fetched_at >= cutoff,
                )
            )
            .order_by(asc(CrawledContent.published_at), asc(CrawledContent.fetched_at))
            .limit(max_candidates)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    def _content_for_embedding(self, item: CrawledContent) -> str:
        title = (item.title or "").strip()
        summary = (item.summary_hint or "").strip()
        body = (item.content or "").strip()
        body = body[:4000]
        return "\n\n".join(part for part in [title, summary, body] if part)

    def _resolve_tier(self, item: CrawledContent, source: Source | None) -> int:
        host = _host_from_url(item.canonical_url or item.source_url)
        if host:
            for domain, tier in self.host_tiers.items():
                if host == domain or host.endswith(f".{domain}"):
                    return tier

        source_name = (
            (item.source_name or "") + " " + ((source.name if source else "") or "")
        ).lower()
        for name_part, tier in self.source_name_tiers.items():
            if name_part in source_name:
                return tier

        return self.default_tier

    async def _upsert_embedding(
        self,
        *,
        content_id: str,
        embedding_literal: str,
        metadata: dict[str, Any],
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO content_embeddings (content_id, embedding, metadata)
                VALUES (:content_id, CAST(:embedding AS vector), :metadata)
                ON CONFLICT (content_id)
                DO UPDATE SET
                    embedding = CAST(:embedding AS vector),
                    metadata = :metadata
                """
            ),
            {
                "content_id": content_id,
                "embedding": embedding_literal,
                "metadata": metadata,
            },
        )

    async def _find_similar_older(
        self,
        *,
        content_id: str,
        embedding_literal: str,
        published_at: datetime,
        threshold: float,
    ) -> dict[str, Any] | None:
        sql = text(
            """
            SELECT
                ce.content_id,
                cc.title,
                cc.source_url,
                cc.published_at,
                1 - (ce.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM content_embeddings ce
            JOIN crawled_contents cc ON cc.id = ce.content_id
            WHERE ce.content_id != :content_id
              AND cc.published_at <= :published_at
              AND 1 - (ce.embedding <=> CAST(:embedding AS vector)) >= :threshold
            ORDER BY ce.embedding <=> CAST(:embedding AS vector)
            LIMIT 1
            """
        )
        row = (
            await self.session.execute(
                sql,
                {
                    "content_id": content_id,
                    "embedding": embedding_literal,
                    "published_at": published_at,
                    "threshold": threshold,
                },
            )
        ).first()
        if not row:
            return None
        return {
            "content_id": row[0],
            "title": row[1],
            "source_url": row[2],
            "published_at": row[3].isoformat() if row[3] else None,
            "similarity": float(row[4]),
        }

    async def select_candidates(
        self,
        *,
        hours: int = 12,
        similarity_threshold: float = 0.85,
        max_candidates: int = 200,
        limit: int = 50,
        ensure_vector_table: bool = True,
    ) -> dict[str, Any]:
        if hours <= 0:
            raise ValueError("hours must be > 0")
        if not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError("similarity_threshold must be between 0 and 1")

        if ensure_vector_table:
            await self._ensure_vector_table()

        now = _now_utc_naive()
        cutoff = now - timedelta(hours=hours)
        recent_rows = await self._load_recent(cutoff=cutoff, max_candidates=max_candidates)

        if not recent_rows:
            return {
                "hours": hours,
                "cutoff_utc": cutoff.isoformat(),
                "total_recent": 0,
                "total_after_dedup": 0,
                "selected_count": 0,
                "duplicates_removed": 0,
                "candidates": [],
                "duplicates": [],
            }

        kept: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []

        for item, source in recent_rows:
            if not item.content and not item.title:
                continue

            content_for_embedding = self._content_for_embedding(item)
            if not content_for_embedding:
                continue

            embedding = await self.embedder.embed_text(content_for_embedding)
            embedding_literal = self.embedder.to_vector_literal(embedding)
            await self._upsert_embedding(
                content_id=item.id,
                embedding_literal=embedding_literal,
                metadata={
                    "title": item.title,
                    "source_url": item.source_url,
                },
            )

            similar = await self._find_similar_older(
                content_id=item.id,
                embedding_literal=embedding_literal,
                published_at=item.published_at,
                threshold=similarity_threshold,
            )
            if similar:
                duplicates.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "source_url": item.source_url,
                        "published_at": item.published_at.isoformat(),
                        "duplicate_of": similar,
                    }
                )
                continue

            host = _host_from_url(item.canonical_url or item.source_url)
            tier = self._resolve_tier(item, source)
            kept.append(
                {
                    "id": item.id,
                    "source_id": item.source_id,
                    "source_name": item.source_name or (source.name if source else None),
                    "source_url": item.source_url,
                    "canonical_url": item.canonical_url,
                    "source_host": host,
                    "source_tier": tier,
                    "title": item.title,
                    "summary_hint": item.summary_hint,
                    "published_at": item.published_at.isoformat(),
                    "fetched_at": item.fetched_at.isoformat(),
                    "content_type": item.content_type.value,
                    "category_hint": item.category_hint.value,
                    "thread_status": item.thread_status.value,
                }
            )

        await self.session.commit()

        kept.sort(
            key=lambda x: (
                x["source_tier"],
                -datetime.fromisoformat(x["published_at"]).timestamp(),
                -datetime.fromisoformat(x["fetched_at"]).timestamp(),
            )
        )

        selected = kept[:limit]
        return {
            "hours": hours,
            "cutoff_utc": cutoff.isoformat(),
            "total_recent": len(recent_rows),
            "total_after_dedup": len(kept),
            "selected_count": len(selected),
            "duplicates_removed": len(duplicates),
            "similarity_threshold": similarity_threshold,
            "max_candidates": max_candidates,
            "limit": limit,
            "candidates": selected,
            "duplicates": duplicates,
        }
