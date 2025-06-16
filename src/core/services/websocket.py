from typing import Dict, Any, Optional
import logging
from datetime import datetime
from fastapi import WebSocket
from jose import jwt, JWTError
import os
from src.core.websocket.connection_manager import ConnectionManager
from src.core.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

logger = logging.getLogger(__name__)

class WebSocketService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.manager = ConnectionManager()
        logger.info("WebSocket 服务初始化")
        self._start_heartbeat()
        self._start_redis_subscriber()
        logger.info("WebSocket 服务初始化完成")
        
    def _start_heartbeat(self):
        """启动心跳检测"""
        logger.info("启动心跳检测")
        asyncio.create_task(self.manager.start_heartbeat())
        
    def _start_redis_subscriber(self):
        """启动 Redis 订阅"""
        logger.info("启动 Redis 订阅")
        asyncio.create_task(self.manager.start_redis_subscriber())
        
    async def handle_connect(self, websocket: WebSocket) -> None:
        """
        处理新的WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
        """
        try:
            await websocket.accept()
            await self.manager.send_message(websocket, {
                "type": "system_notification",
                "content": "连接成功，请发送认证消息",
                "timestamp": datetime.utcnow().isoformat()
            })
            logger.info("新的WebSocket连接已建立")
        except Exception as e:
            logger.error(f"处理连接时发生错误: {str(e)}")
            raise
            
    async def handle_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """
        处理接收到的消息
        
        Args:
            websocket: WebSocket连接对象
            message: 接收到的消息
        """
        try:
            message_type = message.get("type")
            if not message_type:
                await self._send_error(websocket, "消息类型不能为空")
                return
                
            # 更新活动时间
            self.manager.update_activity(websocket)
            
            # 根据消息类型处理
            if message_type == "auth":
                await self._handle_auth(websocket, message)
            elif message_type == "chat":
                await self._handle_chat(websocket, message)
            elif message_type == "ping":
                await self._handle_ping(websocket)
            elif message_type == "pong":
                # 处理心跳响应，只需要更新活动时间
                self.manager.update_activity(websocket)
            else:
                await self._send_error(websocket, f"未知的消息类型: {message_type}")
                
        except Exception as e:
            logger.error(f"处理消息时发生错误: {str(e)}")
            await self._send_error(websocket, str(e))
            
    async def handle_disconnect(self, websocket: WebSocket) -> None:
        """
        处理连接断开
        
        Args:
            websocket: WebSocket连接对象
        """
        try:
            user_id = await self.manager.disconnect(websocket)
            if user_id:
                logger.info(f"用户 {user_id} 已断开连接")
        except Exception as e:
            logger.error(f"处理断开连接时发生错误: {str(e)}")
            
    async def _handle_auth(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """
        处理认证消息
        
        Args:
            websocket: WebSocket连接对象
            message: 认证消息
        """
        token = message.get("token")
        if not token:
            await self._send_error(websocket, "未提供token")
            return
            
        try:
            # 验证token
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET_KEY', 'your-secret-key'),
                algorithms=[os.getenv('JWT_ALGORITHM', 'HS256')]
            )
            
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("无效的token")
                
            # 获取用户信息
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("用户不存在")
                
            # 存储连接信息
            await self.manager.connect(websocket, str(user_id))
            
            # 发送认证成功消息
            await self.manager.send_message(websocket, {
                "type": "auth_success",
                "message": "认证成功",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"用户 {user_id} 认证成功")
            
        except (JWTError, ValueError) as e:
            await self._send_error(websocket, str(e))
            
    async def _handle_chat(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """
        处理聊天消息
        
        Args:
            websocket: WebSocket连接对象
            message: 聊天消息
        """
        try:
            # 获取发送者信息
            sender_id = self.manager.get_user_id(websocket)
            if not sender_id:
                await self._send_error(websocket, "未认证的连接")
                return
                
            # 获取发送者详细信息
            stmt = select(User).where(User.id == sender_id)
            result = await self.session.execute(stmt)
            sender = result.scalar_one_or_none()
            if not sender:
                await self._send_error(websocket, "发送者不存在")
                return

            # 构建消息内容
            chat_message = {
                "type": "chat",
                "sender_id": str(sender_id),
                "sender_name": sender.nickname,
                "sender_avatar": sender.avatar,
                "content": message.get("content", ""),
                "timestamp": datetime.now().isoformat()
            }
            
            # 如果有接收者，发送私聊消息
            if "receiver_id" in message:
                receiver_id = message["receiver_id"]
                # 检查接收者是否在线
                if not self.manager.is_user_online(receiver_id):
                    await self._send_error(websocket, "接收者不在线")
                    return
                    
                # 发送私聊消息
                await self.manager.send_message(
                    self.manager.connections[receiver_id]["websocket"],
                    chat_message
                )
                # 同时发送给发送者（回显）
                await self.manager.send_message(
                    sender_id,
                    chat_message
                )
            else:
                # 广播消息给所有在线用户
                await self.manager.broadcast(chat_message)
                
            # 更新活动时间
            self.manager.update_activity(websocket)
            
        except Exception as e:
            logger.error(f"处理聊天消息失败: {str(e)}")
            await self._send_error(websocket, "处理消息失败")
            
    async def _handle_ping(self, websocket: WebSocket) -> None:
        """
        处理心跳消息
        
        Args:
            websocket: WebSocket连接对象
        """
        await self.manager.send_message(websocket, {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """
        发送错误消息
        
        Args:
            websocket: WebSocket连接对象
            message: 错误消息
        """
        await self.manager.send_message(websocket, {
            "type": "error",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    async def send_system_notification(self, content: str, level: str = "info", target_user_id: Optional[str] = None) -> None:
        """
        发送系统通知
        
        Args:
            content: 通知内容
            level: 通知级别
            target_user_id: 目标用户ID，不指定则广播
        """
        message = {
            "type": "system_notification",
            "content": content,
            "level": level,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if target_user_id:
            if target_user_id in self.manager.connections:
                await self.manager.send_message(
                    self.manager.connections[target_user_id]["websocket"],
                    message
                )
        else:
            await self.manager.broadcast(message)
            
    def get_connection_stats(self) -> Dict[str, int]:
        """
        获取连接统计信息
        
        Returns:
            Dict[str, int]: 统计信息
        """
        return {
            "total_connections": self.manager.get_connection_count(),
            "total_users": self.manager.get_user_count()
        } 