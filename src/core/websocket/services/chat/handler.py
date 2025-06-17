from typing import Dict, Any, Optional, Tuple
from fastapi import WebSocket
from datetime import datetime
import logging
from sqlalchemy import select
from src.core.models.user import User
from src.core.websocket.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

class ChatMessageHandler:
    """聊天消息处理器类"""
    
    def __init__(self, connection_manager: ConnectionManager, session):
        """
        初始化聊天消息处理器
        
        Args:
            connection_manager: WebSocket连接管理器实例
            session: 数据库会话
        """
        self.manager = connection_manager
        self.session = session
        
    async def handle_message(self, websocket: WebSocket, message: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        处理聊天消息
        
        Args:
            websocket: WebSocket连接对象
            message: 聊天消息
            
        Returns:
            Tuple[bool, Optional[Dict[str, Any]], Optional[str]]: 
                - 处理是否成功
                - 处理后的消息内容
                - 错误信息（如果有）
        """
        try:
            # 获取发送者信息
            sender_id = self.manager.get_user_id(websocket)
            if not sender_id:
                return False, None, "未认证的连接"
                
            # 获取发送者详细信息
            sender = await self._get_user_info(sender_id)
            if not sender:
                return False, None, "发送者不存在"

            # 构建消息内容
            chat_message = await self._build_chat_message(sender_id, sender, message)
            
            # 判断消息类型（私聊/广播）
            is_private = "receiver_id" in message
            receiver_id = message.get("receiver_id") if is_private else None
            
            return True, chat_message, receiver_id
            
        except Exception as e:
            logger.error(f"处理聊天消息失败: {str(e)}")
            return False, None, "处理消息失败"
            
    async def _get_user_info(self, user_id: str) -> Optional[User]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[User]: 用户信息
        """
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
            
    async def _build_chat_message(self, sender_id: str, sender: User, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建聊天消息
        
        Args:
            sender_id: 发送者ID
            sender: 发送者信息
            message: 原始消息
            
        Returns:
            Dict[str, Any]: 构建好的聊天消息
        """
        return {
            "type": "chat",
            "sender_id": str(sender_id),
            "sender_name": sender.nickname,
            "sender_avatar": sender.avatar,
            "content": message.get("content", ""),
            "timestamp": datetime.now().isoformat()
        }
        
    async def _process_message_sending(self, websocket: WebSocket, chat_message: Dict[str, Any], original_message: Dict[str, Any]) -> None:
        """
        处理消息发送
        
        Args:
            websocket: WebSocket连接对象
            chat_message: 构建好的聊天消息
            original_message: 原始消息
        """
        try:
            # 如果有接收者，发送私聊消息
            if "receiver_id" in original_message:
                receiver_id = original_message["receiver_id"]
                # 发送私聊消息
                success = await self.manager.send_private_message(receiver_id, chat_message)
                if not success:
                    await self._send_error(websocket, "发送私聊消息失败")
                    return
                    
                # 同时发送给发送者（回显）
                await self.manager.send_message(websocket, chat_message)
            else:
                # 广播消息给所有在线用户
                await self.manager.broadcast(chat_message)
                
        except Exception as e:
            logger.error(f"处理消息发送失败: {str(e)}")
            raise
            
    async def _send_error(self, websocket: WebSocket, error_message: str) -> None:
        """
        发送错误消息
        
        Args:
            websocket: WebSocket连接对象
            error_message: 错误消息
        """
        try:
            await self.manager.send_message(websocket, {
                "type": "error",
                "content": error_message,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"发送错误消息失败: {str(e)}") 