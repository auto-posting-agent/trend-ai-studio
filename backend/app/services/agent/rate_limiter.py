import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()


class RateLimiter:
    """Rate limit API calls to prevent cost overruns."""

    LIMITS = {
        "gemini_flash": {"hour": 1000, "day": 10000},
        "gemini_pro": {"hour": 100, "day": 500},
        "tavily": {"hour": 50, "day": 200},
        "embedding": {"hour": 5000, "day": 50000}
    }

    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)

    async def check_limit(self, service: str) -> bool:
        """
        Check if within rate limits.

        Args:
            service: Service name (gemini_flash, gemini_pro, tavily, embedding)

        Returns:
            bool: True if within limits, False otherwise
        """
        key = f"ratelimit:{service}:hour"
        count = await self.redis.incr(key)

        if count == 1:
            await self.redis.expire(key, 3600)

        return count <= self.LIMITS[service]["hour"]

    async def get_usage(self, service: str) -> dict:
        """Get current usage stats for a service."""
        hour_key = f"ratelimit:{service}:hour"
        day_key = f"ratelimit:{service}:day"

        hour_count = await self.redis.get(hour_key)
        day_count = await self.redis.get(day_key)

        return {
            "service": service,
            "hourly": {
                "used": int(hour_count or 0),
                "limit": self.LIMITS[service]["hour"]
            },
            "daily": {
                "used": int(day_count or 0),
                "limit": self.LIMITS[service]["day"]
            }
        }

    async def close(self):
        """Close Redis connection."""
        await self.redis.aclose()
