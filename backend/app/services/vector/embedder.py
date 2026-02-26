from google import genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings

settings = get_settings()

# Initialize Gemini client
client = genai.Client(api_key=settings.GEMINI_API_KEY)


class VectorEmbedder:
    """Handle vector embeddings and similarity search with Gemini + pgvector."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = "models/gemini-embedding-001"
        self.dimensions = 3072  # gemini-embedding-001 uses 3072 dimensions

    @staticmethod
    def to_vector_literal(values: list[float]) -> str:
        """Convert embedding floats to pgvector text literal format."""
        return "[" + ",".join(f"{v:.8f}" for v in values) + "]"

    async def embed_text(self, content: str) -> list[float]:
        """Generate embedding for a single text using Gemini."""
        result = await client.aio.models.embed_content(
            model=self.model,
            contents=content
        )
        return result.embeddings[0].values

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query."""
        result = await client.aio.models.embed_content(
            model=self.model,
            contents=query
        )
        return result.embeddings[0].values

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
            VALUES (:content_id, CAST(:embedding AS vector), :metadata)
            ON CONFLICT (content_id)
            DO UPDATE SET embedding = CAST(:embedding AS vector), metadata = :metadata
        """)

        await self.session.execute(
            query,
            {
                "content_id": content_id,
                "embedding": self.to_vector_literal(embedding),
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
            SELECT content_id, metadata, 1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM content_embeddings
            WHERE 1 - (embedding <=> CAST(:embedding AS vector)) > :threshold
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        result = await self.session.execute(
            sql,
            {
                "embedding": self.to_vector_literal(query_embedding),
                "threshold": threshold,
                "limit": limit,
            },
        )

        return [
            {"content_id": row[0], "metadata": row[1], "similarity": row[2]}
            for row in result.fetchall()
        ]

    async def check_duplicate(
        self,
        content: str,
        threshold: float = 0.9
    ) -> tuple[bool, str | None]:
        """
        Check if content is duplicate via vector similarity.

        Returns:
            tuple: (is_duplicate, existing_content_id)
        """
        similar = await self.search_similar(
            query=content,
            limit=1,
            threshold=threshold
        )

        if similar:
            return (True, similar[0]["content_id"])
        return (False, None)

    async def embed_batch(
        self,
        contents: list[tuple[str, str]]
    ) -> list[dict]:
        """
        Batch embed multiple texts (100 per API call for cost efficiency).

        Args:
            contents: List of (content_id, text) tuples

        Returns:
            List of dicts with content_id and embedding
        """
        embeddings = []

        # Process in batches of 100 (Gemini API limit)
        for i in range(0, len(contents), 100):
            batch = contents[i:i+100]
            texts = [text for _, text in batch]

            # Gemini batch embedding
            result = await client.aio.models.embed_content(
                model=self.model,
                contents=texts
            )

            # Match embeddings with content IDs
            for idx, (content_id, _) in enumerate(batch):
                embeddings.append({
                    "content_id": content_id,
                    "embedding": result.embeddings[idx].values
                })

        return embeddings

    async def get_embedding_cached(
        self,
        content_id: str,
        content: str
    ) -> list[float]:
        """
        Get embedding with Redis cache (7-day TTL) to reduce API calls.

        Args:
            content_id: Unique content identifier
            content: Text content to embed

        Returns:
            Embedding vector
        """
        import json
        import redis.asyncio as redis

        redis_client = redis.from_url(settings.REDIS_URL)

        try:
            cache_key = f"embedding:{content_id}"

            # Check cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Generate embedding
            embedding = await self.embed_text(content)

            # Cache for 7 days (604800 seconds)
            await redis_client.setex(
                cache_key,
                604800,
                json.dumps(embedding)
            )

            return embedding
        finally:
            await redis_client.aclose()
