import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.models.source import CrawledContent, ThreadStatus, ContentType, GeneratedPost, PostStatus
from app.services.vector.qdrant_embedder import QdrantEmbedder


class EmbeddingPipeline:
    """Automated embedding pipeline after crawling."""

    def _classify_urgency(self, content: CrawledContent) -> str:
        """
        Classify content as urgent or normal.

        Urgent: Breaking news, major releases that need immediate posting
        Normal: Regular content that goes through full pipeline
        """
        # Urgent content types
        urgent_types = [
            ContentType.BREAKING_NEWS,
            ContentType.MODEL_RELEASE,
            ContentType.TOOL_LAUNCH
        ]

        if content.content_type in urgent_types:
            return "urgent"

        # Urgent keywords in title
        urgent_keywords = [
            "breaking", "just released", "announces", "launched",
            "unveiled", "introducing", "available now"
        ]

        title_lower = content.title.lower()
        if any(keyword in title_lower for keyword in urgent_keywords):
            return "urgent"

        return "normal"

    async def process_crawled_content(
        self,
        session: AsyncSession,
        content_id: str
    ) -> dict:
        """
        Generate content using AI agent workflow.

        Simplified flow:
        1. Fetch content from DB
        2. Run agent workflow (web search + vector similarity for context)
        3. Generate high-quality post
        4. Save to DB

        No duplicate blocking - duplicates are only used for context.

        Args:
            session: Database session
            content_id: ID of crawled content

        Returns:
            dict with status and details
        """
        from app.services.agent.workflow import TrendAgentWorkflow

        # 1. Fetch content from DB
        content = await session.get(CrawledContent, content_id)
        if not content:
            return {"status": "error", "reason": "content_not_found"}

        # 2. Update status to ANALYZING (allow re-generation)
        content.thread_status = ThreadStatus.ANALYZING

        # Clear previous generation data for fresh start
        if content.extra_data:
            content.extra_data.pop("generated_post", None)
            content.extra_data.pop("thread_parts", None)
            content.extra_data.pop("error", None)
            attributes.flag_modified(content, "extra_data")

        await session.commit()

        # 3. Run agent workflow
        # Agent will:
        # - Search for similar content in vector DB (for context)
        # - Perform web search for additional info
        # - Generate high-quality post
        workflow = TrendAgentWorkflow(session)
        result = await workflow.run({
            "content_id": content.id,
            "raw_content": content.content,
            "title": content.title,
            "source_url": str(content.source_url),
            "category_hint": content.category_hint.value,
            "content_type": content.content_type.value,
            "errors": [],
            "retry_count": 0
        })

        # 4. Save result to database as GeneratedPost
        if result.get("status") == "generated":
            # Create new GeneratedPost record
            generated_post = GeneratedPost(
                content_id=content.id,
                thread_parts=result.get("content", []),
                generated_post="\n\n".join(result.get("content", [])),
                analysis_summary=result.get("analysis_summary", ""),
                web_search_results=result.get("web_search_summary", ""),
                link=result.get("link"),
                hashtags=result.get("hashtags", []),
                status=PostStatus.READY
            )
            session.add(generated_post)
            content.thread_status = ThreadStatus.READY
        else:
            # Error case - keep in extra_data for now
            if not content.extra_data:
                content.extra_data = {}
            content.extra_data["error"] = result.get("reason", "Unknown error")
            content.thread_status = ThreadStatus.FAILED
            attributes.flag_modified(content, "extra_data")

        await session.commit()

        return {
            "status": "processed",
            "content_id": content_id,
            "agent_result": result,
            "generated_post_id": generated_post.id if result.get("status") == "generated" else None
        }

    def _generate_hash(self, title: str, content: str) -> str:
        """
        Generate SHA256 hash for duplicate detection.

        Args:
            title: Content title
            content: Content body

        Returns:
            SHA256 hash string
        """
        combined = f"{title}||{content}".encode('utf-8')
        return hashlib.sha256(combined).hexdigest()
