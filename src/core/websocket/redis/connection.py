from typing import Optional
import logging
from redis import Redis
from redis.client import PubSub
from src.core.utils.redis import RedisManager

logger = logging.getLogger(__name__)

class RedisConnection:
    """Redis连接管理类"""
    
    _instance: Optional['RedisConnection'] = None
    
    def __new__(cls):
        """单例模式，确保只有一个Redis连接实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化Redis连接"""
        if self._initialized:
            return
            
        try:
            # 使用共享的Redis管理器
            self._redis_manager = RedisManager()
            self._redis: Optional[Redis] = None
            self._pubsub: Optional[PubSub] = None
            self._initialized = True
            logger.info("Redis连接管理器初始化完成")
        except Exception as e:
            logger.error(f"Redis连接管理器初始化失败: {str(e)}")
            raise
    
    @property
    def redis(self) -> Redis:
        """获取Redis客户端实例"""
        if self._redis is None:
            self._redis = self._redis_manager.get_redis()
        return self._redis
    
    @property
    def pubsub(self) -> PubSub:
        """获取Redis PubSub实例"""
        if self._pubsub is None:
            self._pubsub = self._redis_manager.get_pubsub()
        return self._pubsub
    
    def close(self):
        """关闭Redis连接"""
        try:
            if self._pubsub is not None:
                self._pubsub.close()
                self._pubsub = None
            if self._redis is not None:
                self._redis.close()
                self._redis = None
            logger.info("Redis连接已关闭")
        except Exception as e:
            logger.error(f"关闭Redis连接时发生错误: {str(e)}")
            raise 