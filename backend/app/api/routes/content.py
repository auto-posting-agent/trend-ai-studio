from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_session
from app.models.source import CrawledContent, ThreadStatus, ContentType, CategoryHint
from app.services.vector.pipeline import EmbeddingPipeline

router = APIRouter()


@router.post("/process/{content_id}")
async def process_content(
    content_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Trigger pipeline processing for crawled content.

    Called by crawler team after saving content to DB.
    Handles urgency classification and routing.
    """
    pipeline = EmbeddingPipeline()

    try:
        result = await pipeline.process_crawled_content(session, content_id)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline processing failed: {str(e)}"
        )


@router.get("/")
async def list_content(
    status: Optional[ThreadStatus] = None,
    content_type: Optional[ContentType] = None,
    category: Optional[CategoryHint] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session)
):
    """
    List crawled content with filters.

    Useful for frontend to display content pipeline.
    """
    query = select(CrawledContent)

    # Apply filters
    if status:
        query = query.where(CrawledContent.thread_status == status)
    if content_type:
        query = query.where(CrawledContent.content_type == content_type)
    if category:
        query = query.where(CrawledContent.category_hint == category)

    # Order by status priority (READY first, then PENDING, ANALYZING, FAILED, PUBLISHED)
    # Then by most recent within each status
    from sqlalchemy import case

    status_priority = case(
        (CrawledContent.thread_status == ThreadStatus.READY, 1),
        (CrawledContent.thread_status == ThreadStatus.PENDING, 2),
        (CrawledContent.thread_status == ThreadStatus.ANALYZING, 3),
        (CrawledContent.thread_status == ThreadStatus.FAILED, 4),
        (CrawledContent.thread_status == ThreadStatus.PUBLISHED, 5),
        else_=6
    )

    query = query.order_by(status_priority, CrawledContent.created_at.desc())

    # Pagination
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    contents = result.scalars().all()

    return {
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "source_url": c.source_url,
                "content_type": c.content_type.value,
                "category_hint": c.category_hint.value,
                "thread_status": c.thread_status.value,
                "created_at": c.created_at.isoformat(),
                "extra_data": c.extra_data
            }
            for c in contents
        ],
        "total": len(contents),
        "limit": limit,
        "offset": offset
    }


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session)
):
    """
    Get pipeline statistics.

    Returns counts by status, content type, and today's metrics.
    """
    # Status breakdown
    status_query = select(
        CrawledContent.thread_status,
        func.count(CrawledContent.id)
    ).group_by(CrawledContent.thread_status)

    status_result = await session.execute(status_query)
    status_counts = {
        status.value: count
        for status, count in status_result.all()
    }

    # Content type breakdown
    type_query = select(
        CrawledContent.content_type,
        func.count(CrawledContent.id)
    ).group_by(CrawledContent.content_type)

    type_result = await session.execute(type_query)
    type_counts = {
        ctype.value: count
        for ctype, count in type_result.all()
    }

    # Today's stats
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    today_query = select(func.count(CrawledContent.id)).where(
        CrawledContent.created_at >= today_start
    )
    today_total = await session.execute(today_query)
    today_count = today_total.scalar()

    # Duplicates today
    # Note: Using JSONB cast for ? operator compatibility
    try:
        duplicates_query = select(func.count(CrawledContent.id)).where(
            and_(
                CrawledContent.created_at >= today_start,
                CrawledContent.thread_status == ThreadStatus.FAILED,
                func.cast(CrawledContent.extra_data, JSONB).op('?')("duplicate_of")
            )
        )
        duplicates_result = await session.execute(duplicates_query)
        duplicates_count = duplicates_result.scalar()
    except Exception:
        # Fallback if JSONB operator not supported
        duplicates_count = 0

    return {
        "by_status": status_counts,
        "by_content_type": type_counts,
        "today": {
            "total_crawled": today_count,
            "duplicates": duplicates_count,
            "unique": today_count - duplicates_count
        }
    }


@router.get("/{content_id}")
async def get_content(
    content_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get single content item with full details."""
    content = await session.get(CrawledContent, content_id)

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return {
        "id": content.id,
        "title": content.title,
        "content": content.content,
        "source_url": content.source_url,
        "source_type": content.source_type.value,
        "source_name": content.source_name,
        "content_type": content.content_type.value,
        "category_hint": content.category_hint.value,
        "thread_status": content.thread_status.value,
        "content_hash": content.content_hash,
        "author": content.author,
        "tags": content.tags,
        "language": content.language,
        "published_at": content.published_at.isoformat(),
        "fetched_at": content.fetched_at.isoformat(),
        "created_at": content.created_at.isoformat(),
        "extra_data": content.extra_data
    }


@router.post("/{content_id}/approve")
async def approve_content(
    content_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Approve content for publishing.

    Finds the latest GeneratedPost for this content and publishes it.
    """
    from app.models.source import GeneratedPost, PostStatus

    # Find the latest READY GeneratedPost for this content
    query = select(GeneratedPost).where(
        GeneratedPost.content_id == content_id,
        GeneratedPost.status == PostStatus.READY
    ).order_by(GeneratedPost.created_at.desc())

    result = await session.execute(query)
    post = result.scalars().first()

    if not post:
        raise HTTPException(
            status_code=404,
            detail="No ready post found for this content. Please process the content first."
        )

    # Redirect to the publish endpoint
    from app.api.routes.generated_posts import publish_generated_post

    return await publish_generated_post(post.id, session)


@router.post("/{content_id}/reject")
async def reject_content(
    content_id: str,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """
    Reject content.

    Marks as FAILED with rejection reason.
    """
    content = await session.get(CrawledContent, content_id)

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Update status
    content.thread_status = ThreadStatus.FAILED

    if reason:
        if not content.extra_data:
            content.extra_data = {}
        content.extra_data["rejection_reason"] = reason

    await session.commit()

    return {
        "status": "rejected",
        "content_id": content_id,
        "reason": reason
    }


@router.post("/{content_id}/save-edit")
async def save_edited_content(
    content_id: str,
    edited_posts: dict,
    session: AsyncSession = Depends(get_session)
):
    """
    Save edited post content.

    Request body:
    {
        "thread_parts": ["edited post 1", "edited post 2"]
    }
    """
    content = await session.get(CrawledContent, content_id)

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if not content.extra_data:
        content.extra_data = {}

    # Update thread parts with edited content
    content.extra_data["thread_parts"] = edited_posts.get("thread_parts", [])
    content.extra_data["generated_post"] = "\n\n".join(edited_posts.get("thread_parts", []))

    from sqlalchemy.orm import attributes
    attributes.flag_modified(content, "extra_data")

    await session.commit()

    return {
        "status": "saved",
        "content_id": content_id,
        "message": "Edited content saved successfully"
    }
