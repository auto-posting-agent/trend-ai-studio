from fastapi import APIRouter, HTTPException
from typing import List, Optional
import asyncio
import json
from datetime import timedelta

from app.schemas.thread import ThreadCreate, ThreadResponse, ThreadStatus
from app.services.threads import ThreadsPublisher
from app.config import get_settings
import redis.asyncio as redis

settings = get_settings()
router = APIRouter()

# Redis client for caching
_redis_client = None


async def get_redis():
    """Get Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


@router.get("/", response_model=List[ThreadResponse])
async def list_threads(
    status: ThreadStatus | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all threads with optional status filter."""
    # TODO: Implement with Supabase
    return []


@router.post("/", response_model=ThreadResponse)
async def create_thread(thread: ThreadCreate):
    """Create a new thread draft."""
    # TODO: Implement with Supabase
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: str):
    """Get a specific thread by ID."""
    # TODO: Implement with Supabase
    raise HTTPException(status_code=404, detail="Thread not found")


@router.post("/{thread_id}/publish")
async def publish_thread(thread_id: str):
    """Publish a thread to Threads platform."""
    # TODO: Implement with Threads API
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread."""
    # TODO: Implement with Supabase
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/api/profile")
async def get_threads_profile(user_id: Optional[str] = None):
    """
    Get Threads profile information from Meta API.
    """
    try:
        publisher = ThreadsPublisher()
        profile = await publisher.get_profile(user_id)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


@router.get("/api/posts")
async def get_threads_posts(user_id: Optional[str] = None, limit: int = 25):
    """
    Get user's published threads from Meta API.
    """
    try:
        publisher = ThreadsPublisher()
        threads = await publisher.get_threads(user_id, limit)
        return threads
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch threads: {str(e)}")


@router.get("/api/insights/{thread_id}")
async def get_thread_insights(thread_id: str):
    """
    Get insights for a specific thread from Meta API.
    """
    try:
        publisher = ThreadsPublisher()
        insights = await publisher.get_thread_insights(thread_id)
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch insights: {str(e)}")


@router.get("/api/metrics")
async def get_threads_metrics(user_id: Optional[str] = None):
    """
    Get aggregated metrics from all threads with Redis caching.
    Cache: 5 minutes
    """
    cache_key = "threads:metrics"
    r = await get_redis()

    # Try cache first
    try:
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis error: {e}")

    try:
        publisher = ThreadsPublisher()

        if not user_id:
            user_id = await publisher.get_user_id()

        # Fetch profile and threads in parallel
        profile_task = publisher.get_profile(user_id)
        threads_task = publisher.get_threads(user_id, limit=100)

        profile, threads = await asyncio.gather(profile_task, threads_task)

        # Limit to 20 threads for insights (reduce API calls)
        threads_data = threads.get("data", [])[:20]

        # Fetch insights in parallel with limited concurrency
        async def get_insights_safe(thread_id: str):
            try:
                return await publisher.get_thread_insights(thread_id)
            except:
                return {"data": []}

        # Use semaphore to limit concurrent requests (max 5 at once)
        sem = asyncio.Semaphore(5)

        async def fetch_with_limit(thread_id: str):
            async with sem:
                return await get_insights_safe(thread_id)

        insights_tasks = [fetch_with_limit(t.get("id")) for t in threads_data]
        all_insights = await asyncio.gather(*insights_tasks)

        # Aggregate metrics
        total_views = 0
        total_likes = 0
        total_comments = 0

        for insights in all_insights:
            for metric in insights.get("data", []):
                if metric["name"] == "views":
                    total_views += metric["values"][0]["value"]
                elif metric["name"] == "likes":
                    total_likes += metric["values"][0]["value"]
                elif metric["name"] == "replies":
                    total_comments += metric["values"][0]["value"]

        result = {
            "profile": profile,
            "total_threads": len(threads.get("data", [])),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "threads": threads.get("data", [])[:10]
        }

        # Cache for 5 minutes
        try:
            await r.setex(cache_key, 300, json.dumps(result))
        except Exception as e:
            print(f"Redis cache error: {e}")

        return result

    except Exception as e:
        # Return empty data instead of 500 error
        return {
            "profile": {"id": "", "username": "trend_ai_studio", "name": "Trend AI Studio"},
            "total_threads": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "threads": []
        }


@router.get("/api/comments")
async def get_recent_comments(user_id: Optional[str] = None, limit: int = 10):
    """
    Get recent comments/replies from all published threads with Redis caching.
    Cache: 3 minutes
    """
    cache_key = "threads:comments"
    r = await get_redis()

    # Try cache first
    try:
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis error: {e}")

    try:
        publisher = ThreadsPublisher()

        if not user_id:
            user_id = await publisher.get_user_id()

        threads = await publisher.get_threads(user_id, limit=20)
        threads_data = threads.get("data", [])

        # Fetch replies in parallel with limited concurrency
        async def get_replies_safe(thread_id: str):
            try:
                return await publisher.get_replies(thread_id)
            except:
                return {"data": []}

        # Use semaphore to limit concurrent requests (max 5 at once)
        sem = asyncio.Semaphore(5)

        async def fetch_with_limit(thread_id: str):
            async with sem:
                return await get_replies_safe(thread_id)

        replies_tasks = [fetch_with_limit(t.get("id")) for t in threads_data]
        all_replies = await asyncio.gather(*replies_tasks)

        # Flatten and format comments
        all_comments = []
        for i, replies in enumerate(all_replies):
            thread_id = threads_data[i].get("id")
            for reply in replies.get("data", []):
                all_comments.append({
                    "id": reply.get("id"),
                    "thread_id": thread_id,
                    "username": reply.get("username"),
                    "text": reply.get("text"),
                    "timestamp": reply.get("timestamp"),
                    "hide_status": reply.get("hide_status"),
                    "replied": False
                })

        # Sort by timestamp (newest first)
        all_comments.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        result = {
            "data": all_comments[:limit],
            "total": len(all_comments)
        }

        # Cache for 3 minutes
        try:
            await r.setex(cache_key, 180, json.dumps(result))
        except Exception as e:
            print(f"Redis cache error: {e}")

        return result

    except Exception as e:
        # Return empty data instead of 500 error
        return {
            "data": [],
            "total": 0
        }


@router.get("/api/auto-reply-stats")
async def get_auto_reply_stats():
    """
    Get auto-reply statistics.

    TODO: Implement proper tracking of auto-replies in database.
    For now, returns mock data structure.
    """
    return {
        "enabled": True,
        "total_replies_today": 0,
        "avg_response_time_seconds": 0,
        "yesterday_replies": 0,
        "yesterday_avg_response_time": 0
    }
