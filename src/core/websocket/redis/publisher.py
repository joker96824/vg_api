from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime
from .connection import RedisConnection

logger = logging.getLogger(__name__)

class RedisPublisher:
    """Redis发布器类"""
    
    def __init__(self, connection: RedisConnection):
        """
        初始化发布器
        
        Args:
            connection: Redis连接实例
        """
        self.connection = connection
        self._channels = {
            'broadcast': 'websocket_broadcast',
            'private': 'websocket_private'
        }
        
    async def publish_broadcast(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None) -> None:
        """
        发布广播消息
        
        Args:
            message: 要广播的消息
            exclude_user_id: 要排除的用户ID
        """
        try:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
                
            # 发布消息到 Redis
            logger.info(f"发布广播消息: 类型={message.get('type')}, 内容={message.get('content', '')}, 排除用户={exclude_user_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['broadcast'],
                json.dumps({
                    'message': message,
                    'exclude_user_id': exclude_user_id
                })
            )
            logger.info("广播消息已发布到 Redis")
            
        except Exception as e:
            logger.error(f"发布广播消息时发生错误: {str(e)}")
            raise
            
    async def publish_private(self, target_user_id: str, message: Dict[str, Any]) -> None:
        """
        发布私聊消息
        
        Args:
            target_user_id: 目标用户ID
            message: 要发送的消息
        """
        try:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
                
            # 发布消息到 Redis
            logger.info(f"发布私聊消息: 目标用户={target_user_id}, 类型={message.get('type')}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['private'],
                json.dumps({
                    'target_user_id': target_user_id,
                    'message': message
                })
            )
            logger.info(f"私聊消息已发布到 Redis: 目标用户={target_user_id}")
            
        except Exception as e:
            logger.error(f"发布私聊消息时发生错误: {str(e)}")
            raise
            
    def add_channel(self, name: str, channel: str):
        """
        添加发布频道
        
        Args:
            name: 频道名称
            channel: 频道标识符
        """
        if name not in self._channels:
            self._channels[name] = channel
            logger.info(f"添加发布频道: {name}={channel}")
            
    def remove_channel(self, name: str):
        """
        移除发布频道
        
        Args:
            name: 频道名称
        """
        if name in self._channels:
            del self._channels[name]
            logger.info(f"移除发布频道: {name}")
            
    @property
    def channels(self) -> Dict[str, str]:
        """获取当前可用的发布频道列表"""
        return self._channels.copy() 