from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/status")
async def get_scheduler_status():
    """Get current scheduler status."""
    # TODO: Implement with APScheduler
    return {
        "running": False,
        "jobs": [],
    }


@router.post("/start")
async def start_scheduler():
    """Start the background scheduler."""
    # TODO: Implement with APScheduler
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/stop")
async def stop_scheduler():
    """Stop the background scheduler."""
    # TODO: Implement with APScheduler
    raise HTTPException(status_code=501, detail="Not implemented")
