"""
Reset all FAILED content status to PENDING.
"""
import asyncio
from sqlalchemy import update, select
from app.core.database import get_session
from app.models.source import CrawledContent, ThreadStatus


async def reset_failed_to_pending():
    """Reset all failed content to pending status."""
    async for session in get_session():
        try:
            # Count failed items
            count_query = select(CrawledContent).where(
                CrawledContent.thread_status == ThreadStatus.FAILED
            )
            count_result = await session.execute(count_query)
            failed_items = count_result.scalars().all()

            print(f"Found {len(failed_items)} failed items")

            # Update to pending
            update_query = (
                update(CrawledContent)
                .where(CrawledContent.thread_status == ThreadStatus.FAILED)
                .values(thread_status=ThreadStatus.PENDING)
            )

            result = await session.execute(update_query)
            await session.commit()

            print(f"✓ Updated {result.rowcount} items from FAILED to PENDING")

        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()

        break


if __name__ == "__main__":
    asyncio.run(reset_failed_to_pending())
