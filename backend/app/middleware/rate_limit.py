from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from app.config import get_settings
import time

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis.

    Limits:
    - 100 requests per minute per IP
    - 1000 requests per hour per IP
    """

    def __init__(self, app):
        super().__init__(app)
        self.redis_client = None

    async def get_redis(self):
        if self.redis_client is None:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self.redis_client

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check
        if request.url.path == "/health":
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        try:
            r = await self.get_redis()
            current_time = int(time.time())

            # Minute-based rate limit (100 req/min)
            minute_key = f"rate_limit:min:{client_ip}:{current_time // 60}"
            minute_count = await r.incr(minute_key)
            if minute_count == 1:
                await r.expire(minute_key, 60)

            if minute_count > 100:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded: 100 requests per minute"
                )

            # Hour-based rate limit (1000 req/hour)
            hour_key = f"rate_limit:hour:{client_ip}:{current_time // 3600}"
            hour_count = await r.incr(hour_key)
            if hour_count == 1:
                await r.expire(hour_key, 3600)

            if hour_count > 1000:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded: 1000 requests per hour"
                )

        except HTTPException:
            raise
        except Exception as e:
            # If Redis fails, allow the request through
            print(f"Rate limit check failed: {e}")

        response = await call_next(request)
        return response
