import logging
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


async def init_redis():
    global _redis_client
    try:
        _redis_client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        await _redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis not available, using memory fallback: {e}")
        _redis_client = None


async def get_redis() -> aioredis.Redis | None:
    return _redis_client


async def close_redis():
    if _redis_client:
        await _redis_client.aclose()


# Simple in-memory cache fallback
_memory_cache: dict = {}


async def cache_get(key: str) -> str | None:
    if _redis_client:
        return await _redis_client.get(key)
    return _memory_cache.get(key)


async def cache_set(key: str, value: str, ttl: int = 3600) -> None:
    if _redis_client:
        await _redis_client.setex(key, ttl, value)
    else:
        _memory_cache[key] = value


async def cache_delete(key: str) -> None:
    if _redis_client:
        await _redis_client.delete(key)
    else:
        _memory_cache.pop(key, None)
