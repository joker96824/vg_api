from typing import Dict, Any, Optional
import logging
from datetime import datetime
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from src.core.models.room import Room
from src.core.models.room_player import RoomPlayer
from src.core.websocket.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

class RoomMessageHandler:
    """房间WebSocket消息处理器"""
    
    def __init__(self, connection_manager: ConnectionManager, session: AsyncSession):
        """
        初始化房间消息处理器
        
        Args:
            connection_manager: WebSocket连接管理器
            session: 数据库会话
        """
        self.connection_manager = connection_manager
        self.session = session
        
    async def handle_room_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """
        处理房间相关的WebSocket消息
        
        Args:
            websocket: WebSocket连接对象
            message: 接收到的消息
        """
        try:
            message_type = message.get("type")
            if not message_type:
                await self._send_error(websocket, "消息类型不能为空")
                return
                
            # 根据消息类型处理
            if message_type == "get_room_info":
                await self._handle_get_room_info(websocket, message)
            elif message_type == "room_user_update":
                await self._handle_room_user_update(websocket, message)
            elif message_type == "room_info_update":
                await self._handle_room_info_update(websocket, message)
            elif message_type == "room_dissolved":
                await self._handle_room_dissolved(websocket, message)
            else:
                await self._send_error(websocket, f"未知的房间消息类型: {message_type}")
                
        except Exception as e:
            logger.error(f"处理房间消息时发生错误: {str(e)}")
            await self._send_error(websocket, str(e))
            
    async def _handle_get_room_info(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """处理获取房间信息消息"""
        try:
            room_id = message.get("room_id")
            user_id = self.connection_manager.get_user_id(websocket)
            
            if not room_id:
                await self._send_error(websocket, "房间ID不能为空")
                return
                
            if not user_id:
                await self._send_error(websocket, "用户未认证")
                return
                
            # 获取房间信息
            room = await self._get_room(room_id)
            if not room:
                await self._send_error(websocket, "房间不存在")
                return
                
            # 获取房间玩家信息
            room_players = await self._get_room_players(room_id)
            
            # 发送房间信息
            await self.connection_manager.send_message(websocket, {
                "type": "room_info",
                "room_id": str(room_id),
                "room_name": room.room_name,
                "room_type": room.room_type,
                "status": room.status,
                "max_players": room.max_players,
                "current_players": room.current_players,
                "players": room_players,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"处理获取房间信息消息时发生错误: {str(e)}")
            await self._send_error(websocket, str(e))
            
    async def _handle_room_user_update(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """处理房间玩家变化消息"""
        try:
            room_id = message.get("room_id")
            user_id = self.connection_manager.get_user_id(websocket)
            
            if not room_id:
                await self._send_error(websocket, "房间ID不能为空")
                return
                
            if not user_id:
                await self._send_error(websocket, "用户未认证")
                return
                
            # 获取房间玩家信息
            room_players = await self._get_room_players(room_id)
            
            # 发送房间玩家更新消息
            await self.connection_manager.send_message(websocket, {
                "type": "room_user_update",
                "room_id": str(room_id),
                "players": room_players,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"处理房间玩家变化消息时发生错误: {str(e)}")
            await self._send_error(websocket, str(e))
            
    async def _handle_room_info_update(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """处理房间信息变化消息"""
        try:
            room_id = message.get("room_id")
            user_id = self.connection_manager.get_user_id(websocket)
            
            if not room_id:
                await self._send_error(websocket, "房间ID不能为空")
                return
                
            if not user_id:
                await self._send_error(websocket, "用户未认证")
                return
                
            # 获取房间信息
            room = await self._get_room(room_id)
            if not room:
                await self._send_error(websocket, "房间不存在")
                return
                
            # 发送房间信息更新消息
            await self.connection_manager.send_message(websocket, {
                "type": "room_info_update",
                "room_id": str(room_id),
                "room_name": room.room_name,
                "room_type": room.room_type,
                "status": room.status,
                "max_players": room.max_players,
                "current_players": room.current_players,
                "game_mode": room.game_mode,
                "game_settings": room.game_settings,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"处理房间信息变化消息时发生错误: {str(e)}")
            await self._send_error(websocket, str(e))
            
    async def _handle_room_dissolved(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """处理房间解散消息"""
        try:
            room_id = message.get("room_id")
            user_id = self.connection_manager.get_user_id(websocket)
            
            if not room_id:
                await self._send_error(websocket, "房间ID不能为空")
                return
                
            if not user_id:
                await self._send_error(websocket, "用户未认证")
                return
                
            # 发送房间解散消息
            await self.connection_manager.send_message(websocket, {
                "type": "room_dissolved",
                "room_id": str(room_id),
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"处理房间解散消息时发生错误: {str(e)}")
            await self._send_error(websocket, str(e))
            
    async def _get_room(self, room_id: str) -> Optional[Room]:
        """获取房间信息"""
        try:
            result = await self.session.execute(
                select(Room)
                .where(
                    and_(
                        Room.id == room_id,
                        Room.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取房间信息时发生错误: {str(e)}")
            return None
            
    async def _get_room_players(self, room_id: str) -> list:
        """获取房间中的所有玩家信息"""
        try:
            result = await self.session.execute(
                select(RoomPlayer)
                .where(
                    and_(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
                .order_by(RoomPlayer.player_order)
            )
            room_players = result.scalars().all()
            
            # 转换为字典格式
            players = []
            for player in room_players:
                players.append({
                    "user_id": str(player.user_id),
                    "player_order": player.player_order,
                    "status": player.status,
                    "join_time": player.join_time.isoformat() if player.join_time else None
                })
                
            return players
            
        except Exception as e:
            logger.error(f"获取房间玩家列表时发生错误: {str(e)}")
            return []
            
    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """发送错误消息"""
        await self.connection_manager.send_message(websocket, {
            "type": "error",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }) 