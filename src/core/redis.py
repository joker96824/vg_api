from .utils.redis import RedisManager

def get_redis_client():
    """获取Redis客户端实例"""
    return RedisManager().get_redis() 