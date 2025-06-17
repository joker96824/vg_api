from typing import Dict, Any, Optional, Callable, Awaitable
import logging
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class RedisMessageHandler:
    """Redis消息处理器类"""
    
    def __init__(self, connection_manager):
        """
        初始化消息处理器
        
        Args:
            connection_manager: WebSocket连接管理器实例
        """
        self.connection_manager = connection_manager
        
    async def handle_message(self, data: Dict[str, Any]) -> None:
        """
        处理从Redis接收到的消息
        
        Args:
            data: 消息数据，包含channel和data字段
        """
        try:
            # 获取消息来源频道
            channel = data.get('channel')
            message_data = data.get('data', {})
            
            if channel == 'websocket_broadcast':
                await self._handle_broadcast(message_data)
            elif channel == 'websocket_private':
                await self._handle_private(message_data)
            else:
                logger.warning(f"收到未知频道的消息: {channel}")
                
        except Exception as e:
            logger.error(f"处理Redis消息时发生错误: {str(e)}")
            
    async def _handle_broadcast(self, message_data: Dict[str, Any]) -> None:
        """
        处理广播消息
        
        Args:
            message_data: 广播消息数据
        """
        try:
            message = message_data.get('message')
            exclude_user_id = message_data.get('exclude_user_id')
            
            if message:
                logger.info(f"处理广播消息: 类型={message.get('type')}, 内容={message.get('content', '')}, 排除用户={exclude_user_id}")
                await self._local_broadcast(message, exclude_user_id)
            else:
                logger.warning("收到空的广播消息")
                
        except Exception as e:
            logger.error(f"处理广播消息时发生错误: {str(e)}")
            
    async def _handle_private(self, message_data: Dict[str, Any]) -> None:
        """
        处理私聊消息
        
        Args:
            message_data: 私聊消息数据
        """
        try:
            target_user_id = message_data.get('target_user_id')
            message = message_data.get('message')
            
            if target_user_id and message:
                logger.info(f"处理私聊消息: 目标用户={target_user_id}, 类型={message.get('type')}")
                if target_user_id in self.connection_manager.connections:
                    await self.connection_manager.send_message(
                        self.connection_manager.connections[target_user_id]["websocket"],
                        message
                    )
                    logger.info(f"私聊消息已发送给用户 {target_user_id}")
                else:
                    logger.info(f"用户 {target_user_id} 不在当前实例")
            else:
                logger.warning("收到无效的私聊消息")
                
        except Exception as e:
            logger.error(f"处理私聊消息时发生错误: {str(e)}")
            
    async def _local_broadcast(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None) -> None:
        """
        在本地广播消息
        
        Args:
            message: 要广播的消息
            exclude_user_id: 要排除的用户ID
        """
        try:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
                
            # 记录开始广播
            logger.info(f"开始本地广播消息: {message.get('type')} - {message.get('content', '')}")
            
            # 记录接收者列表
            receivers = []
            failed_receivers = []
            
            for user_id, conn in self.connection_manager.connections.items():
                if exclude_user_id and user_id == exclude_user_id:
                    logger.info(f"排除用户 {user_id} 的广播")
                    continue
                    
                try:
                    await conn["websocket"].send_json(message)
                    receivers.append(user_id)
                except Exception as e:
                    logger.error(f"广播消息给用户 {user_id} 时发生错误: {str(e)}")
                    failed_receivers.append(user_id)
                    
            # 记录广播结果
            logger.info(
                f"本地广播消息完成: "
                f"类型={message.get('type')}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"本地广播消息时发生错误: {str(e)}") 