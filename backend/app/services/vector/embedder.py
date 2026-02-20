import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings

settings = get_settings()

genai.configure(api_key=settings.GEMINI_API_KEY)


class VectorEmbedder:
    """Handle vector embeddings and similarity search with Gemini + pgvector."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = "models/text-embedding-004"
        self.dimensions = 768

    async def embed_text(self, content: str) -> list[float]:
        """Generate embedding for a single text using Gemini."""
        result = genai.embed_content(
            model=self.model,
            content=content,
            task_type="retrieval_document",
        )
        return result["embedding"]

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query."""
        result = genai.embed_content(
            model=self.model,
            content=query,
            task_type="retrieval_query",
        )
        return result["embedding"]

    async def embed_and_store(
        self,
        content_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Embed text and store in pgvector."""
        embedding = await self.embed_text(content)

        query = text("""
            INSERT INTO content_embeddings (content_id, embedding, metadata)
            VALUES (:content_id, :embedding, :metadata)
            ON CONFLICT (content_id)
            DO UPDATE SET embedding = :embedding, metadata = :metadata
        """)

        await self.session.execute(
            query,
            {
                "content_id": content_id,
                "embedding": embedding,
                "metadata": metadata or {},
            },
        )
        await self.session.commit()

    async def search_similar(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[dict]:
        """Search for similar content using vector similarity."""
        query_embedding = await self.embed_query(query)

        sql = text("""
            SELECT content_id, metadata, 1 - (embedding <=> :embedding) as similarity
            FROM content_embeddings
            WHERE 1 - (embedding <=> :embedding) > :threshold
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)

        result = await self.session.execute(
            sql,
            {
                "embedding": query_embedding,
                "threshold": threshold,
                "limit": limit,
            },
        )

        return [
            {"content_id": row[0], "metadata": row[1], "similarity": row[2]}
            for row in result.fetchall()
        ]
