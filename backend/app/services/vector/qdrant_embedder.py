from google import genai
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

settings = get_settings()

# Initialize Gemini client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)

COLLECTION_NAME = "content_embeddings"


class QdrantEmbedder:
    """Handle vector embeddings and similarity search with Gemini + Qdrant."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = "models/gemini-embedding-001"
        self.dimensions = 3072
        self.client = qdrant_client
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if COLLECTION_NAME not in collection_names:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.dimensions,
                    distance=Distance.COSINE
                )
            )

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
        """Embed text and store in Qdrant."""
        embedding = await self.embed_text(content)

        # Store in Qdrant
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=content_id,
                    vector=embedding,
                    payload=metadata or {}
                )
            ]
        )

    async def search_similar(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[dict]:
        """Search for similar content using vector similarity."""
        query_embedding = await self.embed_query(query)

        # Search in Qdrant
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=limit,
            score_threshold=threshold
        )

        return [
            {
                "content_id": hit.id,
                "metadata": hit.payload,
                "similarity": hit.score
            }
            for hit in results.points
        ]

    async def check_duplicate(
        self,
        content: str,
        threshold: float = 0.9,
        exclude_id: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if content is duplicate via vector similarity.

        Args:
            content: Content text to check
            threshold: Similarity threshold (0-1)
            exclude_id: Content ID to exclude from results (e.g., current content)

        Returns:
            tuple: (is_duplicate, existing_content_id)
        """
        similar = await self.search_similar(
            query=content,
            limit=5,  # Get more results to filter
            threshold=threshold
        )

        # Filter out the excluded ID
        if exclude_id:
            similar = [s for s in similar if s["content_id"] != exclude_id]

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

    def delete_embedding(self, content_id: str):
        """Delete embedding from Qdrant."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=[content_id]
            )
        )
