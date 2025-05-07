from typing import Optional

import aioredis
from config.settings import settings

# Redis 连接 URL
REDIS_URL = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

# 创建 Redis 连接池
redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    password=settings.REDIS_PASSWORD or None,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接"""
    redis = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield redis
    finally:
        await redis.close()


async def get_cache(key: str) -> Optional[str]:
    """获取缓存"""
    async with get_redis() as redis:
        return await redis.get(key)


async def set_cache(key: str, value: str, expire: int = 3600) -> None:
    """设置缓存"""
    async with get_redis() as redis:
        await redis.set(key, value, ex=expire)


async def delete_cache(key: str) -> None:
    """删除缓存"""
    async with get_redis() as redis:
        await redis.delete(key) 