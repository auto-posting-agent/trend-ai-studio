import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import (
    CrawledContent,
    ContentType,
    CategoryHint,
    SourceType,
    ThreadStatus
)
from app.models.embedding import ContentEmbedding
from app.services.vector.pipeline import EmbeddingPipeline


class TestUrgencyClassification:
    """Test urgency classification logic."""

    def test_classify_breaking_news_as_urgent(self):
        """Breaking news should be classified as urgent."""
        pipeline = EmbeddingPipeline()
        content = CrawledContent(
            id="test-1",
            source_id="source-1",
            title="Breaking: OpenAI releases GPT-5",
            content="Major announcement today...",
            content_type=ContentType.BREAKING_NEWS,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/gpt5",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        urgency = pipeline._classify_urgency(content)
        assert urgency == "urgent"

    def test_classify_model_release_as_urgent(self):
        """Model releases should be urgent."""
        pipeline = EmbeddingPipeline()
        content = CrawledContent(
            id="test-2",
            source_id="source-1",
            title="Anthropic announces Claude 4",
            content="New model available...",
            content_type=ContentType.MODEL_RELEASE,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/claude4",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        urgency = pipeline._classify_urgency(content)
        assert urgency == "urgent"

    def test_classify_by_keywords(self):
        """Urgent keywords should trigger urgent classification."""
        pipeline = EmbeddingPipeline()
        urgent_titles = [
            "Just released: New AI tool",
            "Breaking news in tech",
            "Company announces major update",
            "Launched today: Revolutionary product"
        ]

        for title in urgent_titles:
            content = CrawledContent(
                id=f"test-{title}",
                source_id="source-1",
                title=title,
                content="Content...",
                content_type=ContentType.GENERAL,
                category_hint=CategoryHint.LLM,
                source_url="https://example.com",
                source_type=SourceType.HTML_ARTICLE,
                published_at=datetime.utcnow(),
                fetched_at=datetime.utcnow()
            )

            urgency = pipeline._classify_urgency(content)
            assert urgency == "urgent", f"Expected '{title}' to be urgent"

    def test_classify_normal_content(self):
        """Regular content should be classified as normal."""
        pipeline = EmbeddingPipeline()
        content = CrawledContent(
            id="test-normal",
            source_id="source-1",
            title="Interesting article about AI trends",
            content="Today we discuss...",
            content_type=ContentType.GENERAL,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/article",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        urgency = pipeline._classify_urgency(content)
        assert urgency == "normal"


@pytest.mark.asyncio
class TestPipelineRouting:
    """Test pipeline routing based on urgency."""

    async def test_urgent_path_skips_embedding(
        self,
        session: AsyncSession,
        mock_agent_workflow
    ):
        """
        Urgent content should skip embedding and go directly to agent.

        Note: This is an integration test that requires:
        - Database connection
        - Mock agent workflow
        """
        # Create urgent content
        content = CrawledContent(
            id="urgent-test",
            source_id="source-1",
            title="Breaking: Major AI announcement",
            content="Breaking news content...",
            content_type=ContentType.BREAKING_NEWS,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/breaking",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        session.add(content)
        await session.commit()

        # Process through pipeline
        pipeline = EmbeddingPipeline()
        result = await pipeline.process_crawled_content(session, content.id)

        # Verify urgent path
        assert result["urgency"] == "urgent"
        assert result["status"] == "urgent_processed"
        assert "agent_result" in result

        # Verify no embedding was created
        embedding = await session.get(ContentEmbedding, content.id)
        assert embedding is None

    async def test_normal_path_creates_embedding(
        self,
        session: AsyncSession
    ):
        """Normal content should be embedded before agent processing."""
        # Create normal content
        content = CrawledContent(
            id="normal-test",
            source_id="source-1",
            title="Regular tech article",
            content="Normal content...",
            content_type=ContentType.GENERAL,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/article",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        session.add(content)
        await session.commit()

        # Process through pipeline
        pipeline = EmbeddingPipeline()
        result = await pipeline.process_crawled_content(session, content.id)

        # Verify normal path
        assert result["urgency"] == "normal"
        assert result["status"] == "embedded"
        assert result["content_id"] == content.id

        # Verify embedding was created
        embedding = await session.get(ContentEmbedding, content.id)
        assert embedding is not None
        assert len(embedding.embedding) == 768  # Gemini embedding dimension

    async def test_duplicate_detection(
        self,
        session: AsyncSession
    ):
        """Duplicate content should be detected and marked as FAILED."""
        # Create first content
        content1 = CrawledContent(
            id="original",
            source_id="source-1",
            title="OpenAI releases GPT-5",
            content="OpenAI has announced the release of GPT-5...",
            content_type=ContentType.GENERAL,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/original",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        session.add(content1)
        await session.commit()

        # Process first content
        pipeline = EmbeddingPipeline()
        await pipeline.process_crawled_content(session, content1.id)

        # Create very similar content
        content2 = CrawledContent(
            id="duplicate",
            source_id="source-1",
            title="OpenAI announces GPT-5",
            content="OpenAI has announced the release of GPT-5...",
            content_type=ContentType.GENERAL,
            category_hint=CategoryHint.LLM,
            source_url="https://example.com/duplicate",
            source_type=SourceType.HTML_ARTICLE,
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow()
        )

        session.add(content2)
        await session.commit()

        # Process duplicate
        result = await pipeline.process_crawled_content(session, content2.id)

        # Verify duplicate detection
        assert result["status"] == "duplicate"
        assert result["duplicate_of"] == content1.id

        # Verify content2 marked as FAILED
        await session.refresh(content2)
        assert content2.thread_status == ThreadStatus.FAILED
        assert content2.extra_data.get("duplicate_of") == content1.id


# Pytest fixtures
@pytest.fixture
async def session():
    """
    Provide async database session for tests.

    TODO: Implement actual database fixture with test database.
    """
    # This is a placeholder - implement actual test database
    pass


@pytest.fixture
def mock_agent_workflow(monkeypatch):
    """
    Mock agent workflow to avoid actual API calls during tests.
    """
    async def mock_run(state):
        return {
            "status": "generated",
            "content": ["Mock thread content"],
            "link": state["source_url"],
            "hashtags": ["AI", "tech"]
        }

    # This is a placeholder - implement actual mocking
    pass
