import redis
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class RedisManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化 Redis 连接"""
        try:
            logger.info("初始化 Redis 连接")
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # 测试连接
            self.redis.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.error(f"Redis 连接初始化失败: {str(e)}")
            raise
            
    def get_redis(self):
        """获取 Redis 连接"""
        return self.redis
        
    def get_pubsub(self):
        """获取 Redis pubsub 对象"""
        return self.redis.pubsub()

def set_key(key: str, value: str, expire: int = None):
    """设置键值对"""
    client = RedisManager().get_redis()
    client.set(key, value, ex=expire)

def get_key(key: str) -> str:
    """获取键值"""
    client = RedisManager().get_redis()
    return client.get(key)

def delete_key(key: str):
    """删除键"""
    client = RedisManager().get_redis()
    client.delete(key)

def key_exists(key: str) -> bool:
    """检查键是否存在"""
    client = RedisManager().get_redis()
    return client.exists(key)

def set_hash(hash_name: str, key: str, value: str):
    """设置哈希表字段"""
    client = RedisManager().get_redis()
    client.hset(hash_name, key, value)

def get_hash(hash_name: str, key: str) -> str:
    """获取哈希表字段"""
    client = RedisManager().get_redis()
    return client.hget(hash_name, key)

def delete_hash(hash_name: str, key: str):
    """删除哈希表字段"""
    client = RedisManager().get_redis()
    client.hdel(hash_name, key)

def hash_exists(hash_name: str, key: str) -> bool:
    """检查哈希表字段是否存在"""
    client = RedisManager().get_redis()
    return client.hexists(hash_name, key) 