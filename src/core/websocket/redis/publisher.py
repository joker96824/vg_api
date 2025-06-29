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
            'private': 'websocket_private',
            'room_update': 'room_update'
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

    async def publish_room_update(self, room_id: str) -> None:
        """
        发布房间更新消息
        
        Args:
            room_id: 房间ID
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布房间更新消息: 房间ID={room_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['room_update'],
                json.dumps({
                    'room_id': room_id
                })
            )
            logger.info(f"房间更新消息已发布到 Redis: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发布房间更新消息时发生错误: {str(e)}")
            raise

    async def publish_room_user_update(self, room_id: str) -> None:
        """
        发布房间玩家变化消息
        
        Args:
            room_id: 房间ID
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布房间玩家变化消息: 房间ID={room_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['room_update'],
                json.dumps({
                    'room_id': room_id,
                    'message_type': 'room_user_update'
                })
            )
            logger.info(f"房间玩家变化消息已发布到 Redis: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发布房间玩家变化消息时发生错误: {str(e)}")
            raise

    async def publish_room_info_update(self, room_id: str) -> None:
        """
        发布房间信息变化消息
        
        Args:
            room_id: 房间ID
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布房间信息变化消息: 房间ID={room_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['room_update'],
                json.dumps({
                    'room_id': room_id,
                    'message_type': 'room_info_update'
                })
            )
            logger.info(f"房间信息变化消息已发布到 Redis: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发布房间信息变化消息时发生错误: {str(e)}")
            raise

    async def publish_room_dissolved(self, room_id: str) -> None:
        """
        发布房间解散消息
        
        Args:
            room_id: 房间ID
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布房间解散消息: 房间ID={room_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['room_update'],
                json.dumps({
                    'room_id': room_id,
                    'message_type': 'room_dissolved'
                })
            )
            logger.info(f"房间解散消息已发布到 Redis: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发布房间解散消息时发生错误: {str(e)}")
            raise

    async def publish_game_loading(self, room_id: str) -> None:
        """
        发布游戏加载消息
        
        Args:
            room_id: 房间ID
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布游戏加载消息: 房间ID={room_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['room_update'],
                json.dumps({
                    'room_id': room_id,
                    'message_type': 'game_loading'
                })
            )
            logger.info(f"游戏加载消息已发布到 Redis: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发布游戏加载消息时发生错误: {str(e)}")
            raise

    async def publish_room_kicked(self, room_id: str, target_user_id: str) -> None:
        """
        发布房间踢出消息
        
        Args:
            room_id: 房间ID
            target_user_id: 被踢出的用户ID
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布房间踢出消息: 房间ID={room_id}, 目标用户ID={target_user_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['private'],
                json.dumps({
                    'target_user_id': target_user_id,
                    'message': {
                        'type': 'room_kicked',
                        'room_id': room_id,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                })
            )
            logger.info(f"房间踢出消息已发布到 Redis: 房间ID={room_id}, 目标用户ID={target_user_id}")
            
        except Exception as e:
            logger.error(f"发布房间踢出消息时发生错误: {str(e)}")
            raise

    async def publish_match_success(self, user_id: str, match_data: Dict[str, Any]) -> None:
        """
        发布匹配成功消息
        
        Args:
            user_id: 用户ID
            match_data: 匹配数据，包含房间信息等
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布匹配成功消息: 用户ID={user_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['private'],
                json.dumps({
                    'target_user_id': user_id,
                    'message': {
                        'type': 'match_success',
                        'data': match_data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                })
            )
            logger.info(f"匹配成功消息已发布到 Redis: 用户ID={user_id}")
            
        except Exception as e:
            logger.error(f"发布匹配成功消息时发生错误: {str(e)}")
            raise

    async def publish_match_confirmation(self, user_id: str, match_data: Dict[str, Any]) -> None:
        """
        发布匹配确认消息
        
        Args:
            user_id: 用户ID
            match_data: 匹配数据，包含match_id和matched_users等
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布匹配确认消息: 用户ID={user_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['private'],
                json.dumps({
                    'target_user_id': user_id,
                    'message': {
                        'type': 'match_confirmation',
                        'data': match_data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                })
            )
            logger.info(f"匹配确认消息已发布到 Redis: 用户ID={user_id}")
            
        except Exception as e:
            logger.error(f"发布匹配确认消息时发生错误: {str(e)}")
            raise

    async def publish_match_timeout(self, user_id: str, timeout_data: Dict[str, Any]) -> None:
        """
        发布匹配超时消息
        
        Args:
            user_id: 用户ID
            timeout_data: 超时数据，包含超时消息等
        """
        try:
            # 发布消息到 Redis
            logger.info(f"发布匹配超时消息: 用户ID={user_id}")
            
            # 使用同步方式发布消息
            self.connection.redis.publish(
                self._channels['private'],
                json.dumps({
                    'target_user_id': user_id,
                    'message': {
                        'type': 'match_timeout',
                        'data': timeout_data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                })
            )
            logger.info(f"匹配超时消息已发布到 Redis: 用户ID={user_id}")
            
        except Exception as e:
            logger.error(f"发布匹配超时消息时发生错误: {str(e)}")
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