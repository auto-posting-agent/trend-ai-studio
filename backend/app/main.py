from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.api.routes import threads, sources, scheduler, content, generated_posts
from app.middleware import RateLimitMiddleware


settings = get_settings()


def setup_logging():
    """Configure logging for better readability."""
    # SQLAlchemy 모든 로거 완전히 끄기
    logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)

    # httpx는 WARNING (에러는 보이게)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # uvicorn access log 끄기
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # 애플리케이션 로그는 DEBUG (모든 로그 보이게)
    logging.getLogger("app").setLevel(logging.DEBUG)

    # 루트 로거 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
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

# Security: Rate limiting
app.add_middleware(RateLimitMiddleware)

# Security: Trusted host (only in production)
if settings.ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.yourdomain.com", "yourdomain.com"]
    )

# Performance: GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS
if settings.ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(threads.router, prefix="/api/threads", tags=["threads"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(generated_posts.router, prefix="/api/content", tags=["generated_posts"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
