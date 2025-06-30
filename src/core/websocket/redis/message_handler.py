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
            elif channel == 'room_update':
                await self._handle_room_update(message_data)
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
            
    async def _handle_room_update(self, message_data: Dict[str, Any]) -> None:
        """
        处理房间更新消息
        
        Args:
            message_data: 房间更新消息数据
        """
        try:
            room_id = message_data.get('room_id')
            message_type = message_data.get('message_type', 'room_update')
            battle_id = message_data.get('battle_id')
            
            if room_id:
                logger.info(f"处理房间更新消息: 房间ID={room_id}, 消息类型={message_type}")
                
                # 查找房间中的所有玩家并发送消息
                room_players = await self._get_room_players(room_id)
                if room_players:
                    if message_type == 'game_start' and battle_id:
                        await self._send_game_start_to_room_players(battle_id, room_id, room_players)
                    else:
                        await self._send_to_room_players(room_id, room_players, message_type)
                else:
                    logger.info(f"房间 {room_id} 中没有找到玩家")
            else:
                logger.warning("收到无效的房间更新消息")
                
        except Exception as e:
            logger.error(f"处理房间更新消息时发生错误: {str(e)}")
            
    async def _get_room_players(self, room_id: str) -> list:
        """
        获取房间中的所有玩家ID
        
        Args:
            room_id: 房间ID
            
        Returns:
            list: 玩家ID列表
        """
        try:
            # 这里需要从数据库查询房间玩家信息
            # 由于当前架构限制，我们暂时通过遍历连接来查找房间玩家
            # 在实际应用中，应该维护房间-玩家的映射关系
            
            room_players = []
            for user_id, conn in self.connection_manager.connections.items():
                # 检查用户是否在指定房间中
                # 这里需要根据实际的数据结构来判断
                # 暂时返回所有连接的用户（实际应该查询数据库）
                room_players.append(user_id)
                
            return room_players
            
        except Exception as e:
            logger.error(f"获取房间玩家时发生错误: {str(e)}")
            return []
            
    async def _send_to_room_players(self, room_id: str, player_ids: list, message_type: str) -> None:
        """
        向房间中的所有玩家发送消息
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
            message_type: 消息类型
        """
        try:
            message = {
                "type": message_type,
                "room_id": room_id,
                "timestamp": datetime.utcnow().isoformat()
            }
                
            # 记录开始发送
            logger.info(f"开始向房间 {room_id} 的玩家发送消息: 类型={message.get('type')}")
            
            # 记录接收者列表
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connection_manager.connections:
                    try:
                        websocket = self.connection_manager.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送{message_type}消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送{message_type}消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                else:
                    logger.info(f"用户 {user_id} 不在当前实例")
                    
            # 记录发送结果
            logger.info(
                f"{message_type}消息发送完成: "
                f"房间ID={room_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送消息时发生错误: {str(e)}")
            
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
            
            # 记录当前连接数
            total_connections = len(self.connection_manager.connections)
            logger.info(f"当前连接数: {total_connections}")
            
            # 记录接收者列表
            receivers = []
            failed_receivers = []
            
            for user_id, conn in self.connection_manager.connections.items():
                if exclude_user_id and user_id == exclude_user_id:
                    logger.info(f"排除用户 {user_id} 的广播")
                    continue
                    
                try:
                    # 检查连接状态
                    websocket = conn["websocket"]
                    logger.debug(f"尝试发送消息给用户 {user_id}")
                    await websocket.send_json(message)
                    receivers.append(user_id)
                    logger.debug(f"成功发送消息给用户 {user_id}")
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

    async def _send_game_start_to_room_players(self, battle_id: str, room_id: str, player_ids: list) -> None:
        """
        向房间中的所有玩家发送游戏开始消息
        
        Args:
            battle_id: 对战ID
            room_id: 房间ID
            player_ids: 玩家ID列表
        """
        try:
            message = {
                "type": "game_start",
                "battle_id": battle_id,
                "room_id": room_id,
                "current_game_state": {},  # 默认为空对象
                "timestamp": datetime.utcnow().isoformat()
            }
                
            # 记录开始发送
            logger.info(f"开始向房间 {room_id} 的玩家发送游戏开始消息: 对战ID={battle_id}")
            
            # 记录接收者列表
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connection_manager.connections:
                    try:
                        websocket = self.connection_manager.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送游戏开始消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送游戏开始消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                else:
                    logger.info(f"用户 {user_id} 不在当前实例")
                    
            # 记录发送结果
            logger.info(
                f"游戏开始消息发送完成: "
                f"房间ID={room_id}, 对战ID={battle_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送游戏开始消息时发生错误: {str(e)}") 