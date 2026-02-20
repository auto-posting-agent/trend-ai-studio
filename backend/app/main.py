from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.api.routes import threads, sources, scheduler


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting {settings.APP_NAME}...")
    yield
    # Shutdown
    print(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Automated trend content generation and Threads publishing",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads.router, prefix="/api/threads", tags=["threads"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
