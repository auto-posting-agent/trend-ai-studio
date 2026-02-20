from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.source import SourceCreate, SourceResponse, CrawledContent

router = APIRouter()


@router.get("/", response_model=List[SourceResponse])
async def list_sources():
    """List all configured sources."""
    # TODO: Implement with Supabase
    return []


@router.post("/", response_model=SourceResponse)
async def create_source(source: SourceCreate):
    """Add a new source to crawl."""
    # TODO: Implement with Supabase
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str):
    """Get a specific source by ID."""
    # TODO: Implement with Supabase
    raise HTTPException(status_code=404, detail="Source not found")


@router.delete("/{source_id}")
async def delete_source(source_id: str):
    """Delete a source."""
    # TODO: Implement with Supabase
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{source_id}/crawl", response_model=List[CrawledContent])
async def trigger_crawl(source_id: str):
    """Manually trigger crawling for a specific source."""
    # TODO: Implement with crawler service
    raise HTTPException(status_code=501, detail="Not implemented")
