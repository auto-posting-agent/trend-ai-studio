from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_session
from app.models.source import GeneratedPost, CrawledContent, PostStatus

router = APIRouter()


class UpdatePostRequest(BaseModel):
    thread_parts: list[str]


@router.get("/{content_id}/posts")
async def list_generated_posts(
    content_id: str,
    session: AsyncSession = Depends(get_session)
):
    """List all generated posts for a content item."""
    query = select(GeneratedPost).where(
        GeneratedPost.content_id == content_id
    ).order_by(GeneratedPost.created_at.desc())

    result = await session.execute(query)
    posts = result.scalars().all()

    return {
        "content_id": content_id,
        "posts": [
            {
                "id": post.id,
                "generated_post": post.generated_post,
                "thread_parts": post.thread_parts,
                "analysis_summary": post.analysis_summary,
                "web_search_results": post.web_search_results,
                "status": post.status.value if hasattr(post.status, 'value') else post.status,
                "hashtags": post.hashtags,
                "link": post.link,
                "threads_permalink": post.threads_permalink,
                "created_at": post.created_at.isoformat()
            }
            for post in posts
        ]
    }


@router.get("/post/{post_id}")
async def get_generated_post(
    post_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific generated post."""
    post = await session.get(GeneratedPost, post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")

    return {
        "id": post.id,
        "content_id": post.content_id,
        "generated_post": post.generated_post,
        "thread_parts": post.thread_parts,
        "analysis_summary": post.analysis_summary,
        "web_search_results": post.web_search_results,
        "status": post.status.value if hasattr(post.status, 'value') else post.status,
        "hashtags": post.hashtags,
        "link": post.link,
        "threads_permalink": post.threads_permalink,
        "created_at": post.created_at.isoformat()
    }


@router.put("/post/{post_id}")
async def update_generated_post(
    post_id: str,
    data: UpdatePostRequest,
    session: AsyncSession = Depends(get_session)
):
    """Update a generated post (for editing)."""
    post = await session.get(GeneratedPost, post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")

    post.thread_parts = data.thread_parts
    post.generated_post = "\n\n".join(data.thread_parts)

    await session.commit()

    return {
        "status": "updated",
        "post_id": post_id
    }


@router.post("/post/{post_id}/publish")
async def publish_generated_post(
    post_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Publish a generated post to Threads."""
    post = await session.get(GeneratedPost, post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")

    # Check status - handle both enum and string
    # Allow both "ready" and "failed" status (to allow retrying failed posts)
    status_value = post.status.value if hasattr(post.status, 'value') else post.status
    if status_value not in ["ready", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Post must be in READY or FAILED status, currently {status_value}"
        )

    try:
        # Publish to Threads
        from app.services.threads.publisher import ThreadsPublisher
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Starting publish for post_id: {post_id}")

        publisher = ThreadsPublisher()

        # Get user profile to get username
        try:
            profile = await publisher.get_profile()
            username = profile.get("username", "trend_ai_studio")
            logger.info(f"Got username: {username}")
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            raise

        # Get CrawledContent to access images
        content = await session.get(CrawledContent, post.content_id)
        logger.info(f"Got content: {content.id if content else 'None'}")

        # Publish thread parts as a thread (first post + replies)
        raw_parts = post.thread_parts if post.thread_parts else [post.generated_post]

        # Split any parts longer than 500 characters (Threads API limit)
        thread_parts = []
        for part in raw_parts:
            if len(part) <= 500:
                thread_parts.append(part)
            else:
                # Split by sentence boundaries (Korean: . ! ? and newlines)
                import re
                # Split by sentence endings but keep the punctuation
                sentences = re.split(r'([.!?\n])', part)

                current_chunk = ""
                i = 0
                while i < len(sentences):
                    sentence = sentences[i]
                    # Check if next item is punctuation
                    if i + 1 < len(sentences) and sentences[i + 1] in '.!?\n':
                        sentence += sentences[i + 1]
                        i += 2
                    else:
                        i += 1

                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # Check if adding this sentence would exceed limit
                    test_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence
                    if len(test_chunk) <= 500:
                        current_chunk = test_chunk
                    else:
                        # Save current chunk and start new one
                        if current_chunk:
                            thread_parts.append(current_chunk.strip())
                        current_chunk = sentence

                # Add remaining chunk
                if current_chunk:
                    thread_parts.append(current_chunk.strip())

        logger.info(f"Publishing {len(thread_parts)} parts (split from {len(raw_parts)} raw parts)")
        for idx, part in enumerate(thread_parts):
            logger.info(f"  Part {idx + 1}: {len(part)} chars")

        # Publish first part (with image if available)
        first_part = thread_parts[0]
        logger.info(f"Publishing main post (length: {len(first_part)})")

        # Check if content has images
        # TEMPORARILY DISABLED: Testing text-only posts
        # if content and content.image_urls and len(content.image_urls) > 0:
        #     # Use first image for the post
        #     image_url = content.image_urls[0]
        #     result = await publisher.create_image_post(
        #         user_id="",
        #         text=first_part,
        #         image_url=image_url
        #     )
        # else:
        # Text-only post (temporary - testing without images)
        try:
            result = await publisher.create_text_post(
                user_id="",
                text=first_part
            )
            logger.info(f"Published main post successfully")
            logger.info(f"  Post ID: {result.get('id')}")
            logger.info(f"  Full response: {result}")
        except Exception as e:
            logger.error(f"Failed to publish main post: {e}", exc_info=True)
            raise

        main_post_id = result.get("id")

        # Publish remaining parts as replies
        if len(thread_parts) > 1:
            reply_to_id = main_post_id
            logger.info(f"Publishing {len(thread_parts) - 1} replies")
            for i, part in enumerate(thread_parts[1:], 1):
                try:
                    logger.info(f"Publishing reply {i} (length: {len(part)}, replying to: {reply_to_id})")
                    reply_result = await publisher.create_text_post(
                        user_id="",
                        text=part,
                        reply_to=reply_to_id
                    )
                    reply_to_id = reply_result.get("id")
                    logger.info(f"Published reply {i} successfully")
                    logger.info(f"  Reply ID: {reply_to_id}")
                    logger.info(f"  Full response: {reply_result}")
                except Exception as e:
                    logger.error(f"Failed to publish reply {i}: {e}", exc_info=True)
                    logger.error(f"  Part length: {len(part)}")
                    logger.error(f"  Replying to: {reply_to_id}")
                    raise

        # Update post status with correct username
        logger.info(f"Updating DB for post_id: {post_id}")
        logger.info(f"  Current status: {post.status}")
        logger.info(f"  Main post ID: {main_post_id}")
        logger.info(f"  Username: {username}")

        try:
            post.status = PostStatus.PUBLISHED
            post.threads_post_id = main_post_id
            post.threads_permalink = f"https://www.threads.net/@{username}/post/{main_post_id}"

            from datetime import datetime
            post.published_at = datetime.utcnow()

            logger.info(f"Committing to DB...")
            logger.info(f"  New status: {post.status}")
            logger.info(f"  Permalink: {post.threads_permalink}")
            logger.info(f"  Published at: {post.published_at}")

            await session.commit()
            logger.info(f"DB commit successful")
        except Exception as e:
            logger.error(f"DB update failed: {e}", exc_info=True)
            logger.error(f"  Post ID: {post_id}")
            logger.error(f"  Main post ID: {main_post_id}")
            logger.error(f"  Username: {username}")
            raise

        return {
            "status": "published",
            "post_id": post_id,
            "thread_url": post.threads_permalink
        }

    except Exception as e:
        # Mark as failed
        post.status = PostStatus.FAILED
        post.error = str(e)
        await session.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish to Threads: {str(e)}"
        )


@router.delete("/post/{post_id}")
async def delete_generated_post(
    post_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Delete a generated post and update content status if needed."""
    post = await session.get(GeneratedPost, post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")

    content_id = post.content_id

    # Delete the post
    await session.delete(post)
    await session.flush()

    # Check if any posts remain for this content
    remaining_query = select(GeneratedPost).where(
        GeneratedPost.content_id == content_id
    )
    remaining_result = await session.execute(remaining_query)
    remaining_posts = remaining_result.scalars().all()

    # If no posts remain, reset content status to PENDING
    if not remaining_posts:
        content = await session.get(CrawledContent, content_id)
        if content:
            from app.models.source import ThreadStatus
            content.thread_status = ThreadStatus.PENDING

    await session.commit()

    return {
        "status": "deleted",
        "post_id": post_id,
        "content_status_reset": len(remaining_posts) == 0
    }
