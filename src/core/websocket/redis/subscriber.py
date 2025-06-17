from typing import Dict, Any, Optional, Callable, Awaitable
import logging
import asyncio
import json
from .connection import RedisConnection

logger = logging.getLogger(__name__)

class RedisSubscriber:
    """Redis订阅器类"""
    
    def __init__(self, connection: RedisConnection, message_handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        初始化订阅器
        
        Args:
            connection: Redis连接实例
            message_handler: 消息处理回调函数
        """
        self.connection = connection
        self.message_handler = message_handler
        self._sub_task: Optional[asyncio.Task] = None
        self._channels = ['websocket_broadcast', 'websocket_private']
        
    async def start(self):
        """启动订阅任务"""
        if self._sub_task is None:
            logger.info("启动 Redis 订阅任务")
            self._sub_task = asyncio.create_task(self._sub_loop())
            
    async def stop(self):
        """停止订阅任务"""
        if self._sub_task:
            logger.info("停止 Redis 订阅任务")
            self._sub_task.cancel()
            self._sub_task = None
            
    async def _sub_loop(self):
        """订阅循环"""
        try:
            logger.info(f"开始订阅 Redis 频道: {', '.join(self._channels)}")
            # 订阅频道
            self.connection.pubsub.subscribe(*self._channels)
            logger.info("Redis 订阅成功")
            
            while True:
                try:
                    message = self.connection.pubsub.get_message(ignore_subscribe_messages=True)
                    
                    if message and message['type'] == 'message':
                        logger.info(f"收到 Redis 消息: {message['data']}")
                        # 添加频道信息到消息数据中
                        data = {
                            'channel': message['channel'],
                            'data': json.loads(message['data'])
                        }
                        await self.message_handler(data)
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    logger.info("Redis 订阅任务被取消")
                    break
                except Exception as e:
                    logger.error(f"处理 Redis 消息时发生错误: {str(e)}")
        except Exception as e:
            logger.error(f"Redis 订阅失败: {str(e)}")
            raise
            
    def add_channel(self, channel: str):
        """
        添加订阅频道
        
        Args:
            channel: 频道名称
        """
        if channel not in self._channels:
            self._channels.append(channel)
            if self._sub_task:
                self.connection.pubsub.subscribe(channel)
                logger.info(f"添加订阅频道: {channel}")
                
    def remove_channel(self, channel: str):
        """
        移除订阅频道
        
        Args:
            channel: 频道名称
        """
        if channel in self._channels:
            self._channels.remove(channel)
            if self._sub_task:
                self.connection.pubsub.unsubscribe(channel)
                logger.info(f"移除订阅频道: {channel}")
                
    @property
    def channels(self) -> list[str]:
        """获取当前订阅的频道列表"""
        return self._channels.copy() 