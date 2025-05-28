import redis
from src.core.config.settings import settings

# 创建Redis连接池
redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True
)

def get_redis_client():
    """获取Redis客户端"""
    return redis.Redis(connection_pool=redis_pool)

def set_key(key: str, value: str, expire: int = None):
    """设置键值对"""
    client = get_redis_client()
    client.set(key, value, ex=expire)

def get_key(key: str) -> str:
    """获取键值"""
    client = get_redis_client()
    return client.get(key)

def delete_key(key: str):
    """删除键"""
    client = get_redis_client()
    client.delete(key)

def key_exists(key: str) -> bool:
    """检查键是否存在"""
    client = get_redis_client()
    return client.exists(key)

def set_hash(hash_name: str, key: str, value: str):
    """设置哈希表字段"""
    client = get_redis_client()
    client.hset(hash_name, key, value)

def get_hash(hash_name: str, key: str) -> str:
    """获取哈希表字段"""
    client = get_redis_client()
    return client.hget(hash_name, key)

def delete_hash(hash_name: str, key: str):
    """删除哈希表字段"""
    client = get_redis_client()
    client.hdel(hash_name, key)

def hash_exists(hash_name: str, key: str) -> bool:
    """检查哈希表字段是否存在"""
    client = get_redis_client()
    return client.hexists(hash_name, key) 