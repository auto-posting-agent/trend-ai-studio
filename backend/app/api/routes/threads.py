from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.thread import ThreadCreate, ThreadResponse, ThreadStatus

router = APIRouter()


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
