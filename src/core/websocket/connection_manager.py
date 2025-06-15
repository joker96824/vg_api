from typing import Dict, Any, Optional, List
from fastapi import WebSocket
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        添加新的WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            user_id: 用户ID
        """
        try:
            self.connections[user_id] = {
                "websocket": websocket,
                "authenticated_at": datetime.utcnow(),
                "last_activity": datetime.utcnow()
            }
            logger.info(f"用户 {user_id} 已连接")
        except Exception as e:
            logger.error(f"添加连接时发生错误: {str(e)}")
            raise
            
    async def disconnect(self, websocket: WebSocket) -> Optional[str]:
        """
        移除WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            
        Returns:
            Optional[str]: 被断开连接的用户ID
        """
        try:
            for user_id, conn in self.connections.items():
                if conn["websocket"] == websocket:
                    del self.connections[user_id]
                    logger.info(f"用户 {user_id} 已断开连接")
                    return user_id
            return None
        except Exception as e:
            logger.error(f"断开连接时发生错误: {str(e)}")
            raise
            
    def is_authenticated(self, websocket: WebSocket) -> bool:
        """
        检查WebSocket连接是否已认证
        
        Args:
            websocket: WebSocket连接对象
            
        Returns:
            bool: 是否已认证
        """
        return any(conn["websocket"] == websocket for conn in self.connections.values())
        
    def get_user_id(self, websocket: WebSocket) -> Optional[str]:
        """
        获取WebSocket连接对应的用户ID
        
        Args:
            websocket: WebSocket连接对象
            
        Returns:
            Optional[str]: 用户ID
        """
        for user_id, conn in self.connections.items():
            if conn["websocket"] == websocket:
                return user_id
        return None
        
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]) -> bool:
        """
        发送消息到指定的WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            message: 要发送的消息
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"发送消息时发生错误: {str(e)}")
            return False
            
    async def broadcast(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None) -> None:
        """
        广播消息给所有连接的客户端
        
        Args:
            message: 要广播的消息
            exclude_user_id: 要排除的用户ID
        """
        try:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
                
            for user_id, conn in self.connections.items():
                if exclude_user_id and user_id == exclude_user_id:
                    continue
                    
                try:
                    await conn["websocket"].send_json(message)
                except Exception as e:
                    logger.error(f"广播消息给用户 {user_id} 时发生错误: {str(e)}")
                    
            logger.info(f"广播消息成功: {message}")
        except Exception as e:
            logger.error(f"广播消息时发生错误: {str(e)}")
            
    def get_connection_count(self) -> int:
        """
        获取当前连接数
        
        Returns:
            int: 连接数
        """
        return len(self.connections)
        
    def get_user_count(self) -> int:
        """
        获取当前在线用户数
        
        Returns:
            int: 用户数
        """
        return len(self.connections)
        
    def update_activity(self, websocket: WebSocket) -> None:
        """
        更新连接的最后活动时间
        
        Args:
            websocket: WebSocket连接对象
        """
        for conn in self.connections.values():
            if conn["websocket"] == websocket:
                conn["last_activity"] = datetime.utcnow()
                break 