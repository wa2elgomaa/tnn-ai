# app/cache.py
from __future__ import annotations
import os, json, asyncio
from typing import Any, Optional
from redis import asyncio as aioredis
from ..config.settings import settings

REDIS_URL = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
CACHE_TTL = int(settings.CACHE_TTL_SECONDS if settings.CACHE_TTL_SECONDS else "300")

# Create a global client (connection pool under the hood)
redis: aioredis.Redis | None = None

async def init_cache() -> None:
    global redis
    if redis is None:
        redis = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=32,
            socket_connect_timeout=3.0,
            socket_timeout=3.0,
            health_check_interval=30,
        )
        # Quick ping to fail fast if unreachable (don’t crash app if optional)
        try:
            await redis.ping()
        except Exception as e:
            # Log and keep going; your app can work without cache
            print(f"[redis] ping failed: {e}")

async def close_cache() -> None:
    global redis
    if redis is not None:
        await redis.close()
        redis = None

# Helpers
async def cache_get_json(key: str) -> Optional[Any]:
    if not redis: return None
    val = await redis.get(key)
    return json.loads(val) if val else None

async def cache_set_json(key: str, value: Any, ttl: Optional[int] = None) -> None:
    if not redis: return
    await redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl or CACHE_TTL)

async def cache_del(key: str) -> None:
    if not redis: return
    await redis.delete(key)
