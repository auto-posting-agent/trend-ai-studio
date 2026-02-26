import asyncio
import sys
from app.core.database import async_session
from sqlalchemy import select
from app.models.source import CrawledContent, ThreadStatus
from app.services.vector.pipeline import EmbeddingPipeline

async def debug_process():
    """Debug the full pipeline flow with detailed logging."""
    async with async_session() as session:
        # Get a pending or analyzing item
        result = await session.execute(
            select(CrawledContent)
            .where(CrawledContent.thread_status.in_([ThreadStatus.PENDING, ThreadStatus.ANALYZING]))
            .limit(1)
        )
        content = result.scalar_one_or_none()

        if not content:
            print('No pending/analyzing content found')
            return

        print(f'\n{"="*80}')
        print(f'TESTING CONTENT: {content.title[:60]}...')
        print(f'ID: {content.id}')
        print(f'Status: {content.thread_status}')
        print(f'Content Type: {content.content_type}')
        print(f'Category: {content.category_hint}')
        print(f'Current extra_data: {content.extra_data}')
        print(f'{"="*80}\n')

        # Process through pipeline
        pipeline = EmbeddingPipeline()

        print('STEP 1: Starting pipeline.process_crawled_content...')
        try:
            result = await pipeline.process_crawled_content(session, content.id)
            print(f'\nSTEP 2: Pipeline returned result:')
            print(f'  Status: {result.get("status")}')
            print(f'  Urgency: {result.get("urgency")}')
            print(f'  Agent result: {result.get("agent_result")}')
            print(f'  Duplicate of: {result.get("duplicate_of")}')

            if result.get("agent_result"):
                agent_result = result["agent_result"]
                print(f'\n  Agent result details:')
                print(f'    - status: {agent_result.get("status")}')
                print(f'    - reason: {agent_result.get("reason")}')
                print(f'    - content: {agent_result.get("content")}')
                print(f'    - link: {agent_result.get("link")}')
                print(f'    - hashtags: {agent_result.get("hashtags")}')

        except Exception as e:
            import traceback
            print(f'\nSTEP 2: Pipeline EXCEPTION: {type(e).__name__}: {e}')
            traceback.print_exc()
            return

        # Refresh and check database
        print(f'\nSTEP 3: Refreshing content from database...')
        await session.refresh(content)

        print(f'\nSTEP 4: Final database state:')
        print(f'  Status: {content.thread_status}')
        print(f'  extra_data: {content.extra_data}')
        print(f'  Has generated_post: {"generated_post" in (content.extra_data or {})}')
        print(f'  Has skip_reason: {"skip_reason" in (content.extra_data or {})}')
        print(f'  Has error: {"error" in (content.extra_data or {})}')

        if content.extra_data:
            if "generated_post" in content.extra_data:
                print(f'\n  Generated post preview:')
                post = content.extra_data["generated_post"]
                print(f'    {post[:200]}...' if len(post) > 200 else f'    {post}')
            if "skip_reason" in content.extra_data:
                print(f'  Skip reason: {content.extra_data["skip_reason"]}')
            if "error" in content.extra_data:
                print(f'  Error: {content.extra_data["error"]}')

        print(f'\n{"="*80}\n')

if __name__ == '__main__':
    asyncio.run(debug_process())
