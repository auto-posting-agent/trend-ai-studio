import asyncio
from app.core.database import async_session
from sqlalchemy import select
from app.models.source import CrawledContent, ThreadStatus
from app.services.agent.workflow import TrendAgentWorkflow

async def test():
    async with async_session() as session:
        # Get a content item
        result = await session.execute(
            select(CrawledContent).where(CrawledContent.thread_status == ThreadStatus.ANALYZING).limit(1)
        )
        content = result.scalar_one_or_none()

        if not content:
            print('No analyzing content found')
            return

        print(f'Testing workflow with: {content.title[:50]}...')

        workflow = TrendAgentWorkflow(session)
        state = {
            'content_id': content.id,
            'raw_content': content.content[:1000],
            'title': content.title,
            'source_url': str(content.source_url),
            'category_hint': content.category_hint.value,
            'content_type': content.content_type.value,
            'errors': [],
            'retry_count': 0
        }

        try:
            print('Running graph.ainvoke...')
            raw_result = await workflow.graph.ainvoke(state)
            print(f'\\nRaw result keys: {list(raw_result.keys())}')
            print(f'\\nChecking for final_output:')
            print(f'  - Has final_output key: {"final_output" in raw_result}')
            if 'final_output' in raw_result:
                print(f'  - final_output value: {raw_result["final_output"]}')
            else:
                print(f'  - Available keys: {list(raw_result.keys())}')
                print(f'  - should_publish: {raw_result.get("should_publish")}')
                print(f'  - skip_reason: {raw_result.get("skip_reason")}')
                print(f'  - errors: {raw_result.get("errors")}')

        except Exception as e:
            import traceback
            print(f'\\nWorkflow EXCEPTION: {type(e).__name__}: {e}')
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
