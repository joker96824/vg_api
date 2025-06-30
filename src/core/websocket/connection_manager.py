from typing import Dict, Any, Optional, List
from fastapi import WebSocket
from datetime import datetime, timedelta
import logging
import asyncio
import json
from .redis import RedisConnection, RedisSubscriber, RedisPublisher, RedisMessageHandler

logger = logging.getLogger(__name__)

class ConnectionManager:
    _instance: Optional['ConnectionManager'] = None
    
    def __new__(cls):
        """单例模式，确保整个应用只有一个ConnectionManager实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化连接管理器"""
        if self._initialized:
            return
            
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        self.connection_timeout = 120  # 连接超时时间（秒）
        self._heartbeat_task = None
        
        # 使用Redis连接管理器
        self.redis_connection = RedisConnection()
        # 创建Redis消息处理器
        self.redis_message_handler = RedisMessageHandler(self)
        # 创建Redis订阅器
        self.redis_subscriber = RedisSubscriber(
            self.redis_connection,
            self.redis_message_handler.handle_message
        )
        # 创建Redis发布器
        self.redis_publisher = RedisPublisher(self.redis_connection)
        
        self._initialized = True
        logger.info("ConnectionManager 单例初始化完成")
        
    async def start_heartbeat(self):
        """启动心跳检测任务"""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
    async def start_redis_subscriber(self):
        """启动 Redis 订阅任务"""
        await self.redis_subscriber.start()
            
    async def stop_redis_subscriber(self):
        """停止 Redis 订阅任务"""
        await self.redis_subscriber.stop()
            
    async def _heartbeat_loop(self):
        """心跳检测循环"""
        while True:
            try:
                await self._check_connections()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检测时发生错误: {str(e)}")
                
    async def _check_connections(self):
        """检查并清理超时连接"""
        now = datetime.utcnow()
        to_remove = []
        
        for user_id, conn in self.connections.items():
            # 检查最后活动时间
            if (now - conn["last_activity"]).total_seconds() > self.connection_timeout:
                to_remove.append(user_id)
                continue
                
            # 发送心跳包
            try:
                await self.send_message(conn["websocket"], {
                    "type": "ping",
                    "timestamp": now.isoformat()
                })
            except Exception as e:
                logger.error(f"发送心跳包给用户 {user_id} 时发生错误: {str(e)}")
                to_remove.append(user_id)
                
        # 清理超时连接
        for user_id in to_remove:
            try:
                websocket = self.connections[user_id]["websocket"]
                await websocket.close()
                del self.connections[user_id]
                logger.info(f"清理超时连接: 用户 {user_id}")
            except Exception as e:
                logger.error(f"清理连接时发生错误: {str(e)}")
                
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
            
    async def send_private_message(self, target_user_id: str, message: Dict[str, Any]) -> bool:
        """
        发送私聊消息给指定用户
        
        Args:
            target_user_id: 目标用户ID
            message: 要发送的消息
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查目标用户是否在当前实例
            if target_user_id in self.connections:
                # 用户在当前实例，直接发送
                logger.info(f"用户 {target_user_id} 在当前实例，直接发送消息")
                return await self.send_message(
                    self.connections[target_user_id]["websocket"],
                    message
                )
            else:
                # 用户不在当前实例，通过Redis发送
                logger.info(f"用户 {target_user_id} 不在当前实例，通过Redis发送消息")
                await self.redis_publisher.publish_private(target_user_id, message)
                return True
                
        except Exception as e:
            logger.error(f"发送私聊消息时发生错误: {str(e)}")
            return False
            
    async def send_room_update(self, room_id: str) -> bool:
        """
        发送房间更新消息给房间中的所有玩家
        
        Args:
            room_id: 房间ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 先尝试在当前实例中查找房间玩家并发送
            room_players = await self._get_room_players_in_instance(room_id)
            
            if room_players:
                # 在当前实例中找到房间玩家，直接发送
                logger.info(f"房间 {room_id} 的玩家在当前实例，直接发送消息")
                await self._send_to_room_players_local(room_id, room_players)
                return True
            else:
                # 房间玩家不在当前实例，通过Redis广播
                logger.info(f"房间 {room_id} 的玩家不在当前实例，通过Redis广播消息")
                await self.redis_publisher.publish_room_update(room_id)
                return True
                
        except Exception as e:
            logger.error(f"发送房间更新消息时发生错误: {str(e)}")
            return False

    async def send_room_user_update(self, room_id: str) -> bool:
        """
        发送房间玩家变化消息给房间中的所有玩家
        
        Args:
            room_id: 房间ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 先尝试在当前实例中查找房间玩家并发送
            room_players = await self._get_room_players_in_instance(room_id)
            
            if room_players:
                # 在当前实例中找到房间玩家，直接发送
                logger.info(f"房间 {room_id} 的玩家在当前实例，直接发送玩家变化消息")
                await self._send_room_user_update_local(room_id, room_players)
                return True
            else:
                # 房间玩家不在当前实例，通过Redis广播
                logger.info(f"房间 {room_id} 的玩家不在当前实例，通过Redis广播玩家变化消息")
                await self.redis_publisher.publish_room_user_update(room_id)
                return True
                
        except Exception as e:
            logger.error(f"发送房间玩家变化消息时发生错误: {str(e)}")
            return False

    async def send_room_info_update(self, room_id: str) -> bool:
        """
        发送房间信息变化消息给房间中的所有玩家
        
        Args:
            room_id: 房间ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 先尝试在当前实例中查找房间玩家并发送
            room_players = await self._get_room_players_in_instance(room_id)
            
            if room_players:
                # 在当前实例中找到房间玩家，直接发送
                logger.info(f"房间 {room_id} 的玩家在当前实例，直接发送信息变化消息")
                await self._send_room_info_update_local(room_id, room_players)
                return True
            else:
                # 房间玩家不在当前实例，通过Redis广播
                logger.info(f"房间 {room_id} 的玩家不在当前实例，通过Redis广播信息变化消息")
                await self.redis_publisher.publish_room_info_update(room_id)
                return True
                
        except Exception as e:
            logger.error(f"发送房间信息变化消息时发生错误: {str(e)}")
            return False

    async def send_room_dissolved(self, room_id: str) -> bool:
        """
        发送房间解散消息给房间中的所有玩家
        
        Args:
            room_id: 房间ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 先尝试在当前实例中查找房间玩家并发送
            room_players = await self._get_room_players_in_instance(room_id)
            
            if room_players:
                # 在当前实例中找到房间玩家，直接发送
                logger.info(f"房间 {room_id} 的玩家在当前实例，直接发送解散消息")
                await self._send_room_dissolved_local(room_id, room_players)
                return True
            else:
                # 房间玩家不在当前实例，通过Redis广播
                logger.info(f"房间 {room_id} 的玩家不在当前实例，通过Redis广播解散消息")
                await self.redis_publisher.publish_room_dissolved(room_id)
                return True
                
        except Exception as e:
            logger.error(f"发送房间解散消息时发生错误: {str(e)}")
            return False

    async def send_game_loading(self, room_id: str) -> bool:
        """
        发送游戏加载消息给房间中的所有玩家
        
        Args:
            room_id: 房间ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 先尝试在当前实例中查找房间玩家并发送
            room_players = await self._get_room_players_in_instance(room_id)
            
            if room_players:
                # 在当前实例中找到房间玩家，直接发送
                logger.info(f"房间 {room_id} 的玩家在当前实例，直接发送游戏加载消息")
                await self._send_game_loading_local(room_id, room_players)
                return True
            else:
                # 房间玩家不在当前实例，通过Redis广播
                logger.info(f"房间 {room_id} 的玩家不在当前实例，通过Redis广播游戏加载消息")
                await self.redis_publisher.publish_game_loading(room_id)
                return True
                
        except Exception as e:
            logger.error(f"发送游戏加载消息时发生错误: {str(e)}")
            return False

    async def send_game_start(self, battle_id: str, room_id: str) -> bool:
        """
        发送游戏开始消息给房间中的所有玩家
        
        Args:
            battle_id: 对战ID
            room_id: 房间ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 先尝试在当前实例中查找房间玩家并发送
            room_players = await self._get_room_players_in_instance(room_id)
            
            if room_players:
                # 在当前实例中找到房间玩家，直接发送
                logger.info(f"房间 {room_id} 的玩家在当前实例，直接发送游戏开始消息")
                await self._send_game_start_local(battle_id, room_id, room_players)
                return True
            else:
                # 房间玩家不在当前实例，通过Redis广播
                logger.info(f"房间 {room_id} 的玩家不在当前实例，通过Redis广播游戏开始消息")
                await self.redis_publisher.publish_game_start(battle_id, room_id)
                return True
                
        except Exception as e:
            logger.error(f"发送游戏开始消息时发生错误: {str(e)}")
            return False

    async def send_room_kicked(self, room_id: str, target_user_id: str) -> bool:
        """
        发送房间踢出消息给指定的用户
        
        Args:
            room_id: 房间ID
            target_user_id: 被踢出的用户ID
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查目标用户是否在当前实例
            if target_user_id in self.connections:
                # 用户在当前实例，直接发送
                logger.info(f"被踢出用户 {target_user_id} 在当前实例，直接发送踢出消息")
                message = {
                    "type": "room_kicked",
                    "room_id": room_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                return await self.send_message(
                    self.connections[target_user_id]["websocket"],
                    message
                )
            else:
                # 用户不在当前实例，通过Redis发送
                logger.info(f"被踢出用户 {target_user_id} 不在当前实例，通过Redis发送踢出消息")
                await self.redis_publisher.publish_room_kicked(room_id, target_user_id)
                return True
                
        except Exception as e:
            logger.error(f"发送房间踢出消息时发生错误: {str(e)}")
            return False

    async def send_match_success(self, user_id: str, match_data: Dict[str, Any]) -> bool:
        """
        发送匹配成功消息给指定用户
        
        Args:
            user_id: 用户ID
            match_data: 匹配数据，包含房间信息等
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查目标用户是否在当前实例
            if user_id in self.connections:
                # 用户在当前实例，直接发送
                logger.info(f"匹配成功用户 {user_id} 在当前实例，直接发送匹配成功消息")
                message = {
                    "type": "match_success",
                    "data": match_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                return await self.send_message(
                    self.connections[user_id]["websocket"],
                    message
                )
            else:
                # 用户不在当前实例，通过Redis发送
                logger.info(f"匹配成功用户 {user_id} 不在当前实例，通过Redis发送匹配成功消息")
                await self.redis_publisher.publish_match_success(user_id, match_data)
                return True
                
        except Exception as e:
            logger.error(f"发送匹配成功消息时发生错误: {str(e)}")
            return False
    
    async def send_match_confirmation(self, user_id: str, match_data: Dict[str, Any]) -> bool:
        """
        发送匹配确认通知给指定用户
        
        Args:
            user_id: 用户ID
            match_data: 匹配数据，包含match_id和matched_users等
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查目标用户是否在当前实例
            if user_id in self.connections:
                # 用户在当前实例，直接发送
                logger.info(f"匹配确认用户 {user_id} 在当前实例，直接发送匹配确认消息")
                message = {
                    "type": "match_confirmation",
                    "data": match_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                return await self.send_message(
                    self.connections[user_id]["websocket"],
                    message
                )
            else:
                # 用户不在当前实例，通过Redis发送
                logger.info(f"匹配确认用户 {user_id} 不在当前实例，通过Redis发送匹配确认消息")
                await self.redis_publisher.publish_match_confirmation(user_id, match_data)
                return True
                
        except Exception as e:
            logger.error(f"发送匹配确认消息时发生错误: {str(e)}")
            return False
    
    async def send_match_timeout(self, user_id: str, timeout_data: Dict[str, Any]) -> bool:
        """
        发送匹配超时通知给指定用户
        
        Args:
            user_id: 用户ID
            timeout_data: 超时数据，包含超时消息等
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查目标用户是否在当前实例
            if user_id in self.connections:
                # 用户在当前实例，直接发送
                logger.info(f"匹配超时用户 {user_id} 在当前实例，直接发送匹配超时消息")
                message = {
                    "type": "match_timeout",
                    "data": timeout_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                return await self.send_message(
                    self.connections[user_id]["websocket"],
                    message
                )
            else:
                # 用户不在当前实例，通过Redis发送
                logger.info(f"匹配超时用户 {user_id} 不在当前实例，通过Redis发送匹配超时消息")
                await self.redis_publisher.publish_match_timeout(user_id, timeout_data)
                return True
                
        except Exception as e:
            logger.error(f"发送匹配超时消息时发生错误: {str(e)}")
            return False
            
    async def _get_room_players_in_instance(self, room_id: str) -> list:
        """
        获取当前实例中指定房间的玩家ID列表
        
        Args:
            room_id: 房间ID
            
        Returns:
            list: 玩家ID列表
        """
        # 这里需要根据实际的数据结构来查询房间玩家
        # 暂时返回空列表，实际应该查询数据库或内存中的房间-玩家映射
        return []
        
    async def _send_to_room_players_local(self, room_id: str, player_ids: list) -> None:
        """
        在当前实例中向房间玩家发送消息
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
        """
        try:
            message = {
                "type": "room_update",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"开始向房间 {room_id} 的玩家发送消息: 类型={message.get('type')}")
            
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connections:
                    try:
                        websocket = self.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送房间更新消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送房间更新消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                        
            logger.info(
                f"房间更新消息发送完成: "
                f"房间ID={room_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送消息时发生错误: {str(e)}")
            
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

    async def _handle_redis_message(self, data: Dict[str, Any]):
        """处理从 Redis 接收到的消息"""
        await self.redis_message_handler.handle_message(data)
            
    async def _local_broadcast(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None):
        """在本地广播消息"""
        try:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
                
            # 记录开始广播
            logger.info(f"开始本地广播消息: {message.get('type')} - {message.get('content', '')}")
            
            # 记录接收者列表
            receivers = []
            failed_receivers = []
            
            for user_id, conn in self.connections.items():
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
                
            # 发布消息到 Redis
            logger.info(f"发布消息到 Redis: 类型={message.get('type')}, 内容={message.get('content', '')}, 排除用户={exclude_user_id}")
            
            # 使用Redis发布器发布消息
            await self.redis_publisher.publish_broadcast(message, exclude_user_id)
            logger.info("消息已发布到 Redis")
            
        except Exception as e:
            logger.error(f"广播消息时发生错误: {str(e)}")

    async def _send_room_user_update_local(self, room_id: str, player_ids: list) -> None:
        """
        在当前实例中向房间玩家发送玩家变化消息
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
        """
        try:
            message = {
                "type": "room_user_update",
                "room_id": room_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"开始向房间 {room_id} 的玩家发送玩家变化消息")
            
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connections:
                    try:
                        websocket = self.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送房间玩家变化消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送房间玩家变化消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                        
            logger.info(
                f"房间玩家变化消息发送完成: "
                f"房间ID={room_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送玩家变化消息时发生错误: {str(e)}")

    async def _send_room_info_update_local(self, room_id: str, player_ids: list) -> None:
        """
        在当前实例中向房间玩家发送信息变化消息
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
        """
        try:
            message = {
                "type": "room_info_update",
                "room_id": room_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"开始向房间 {room_id} 的玩家发送信息变化消息")
            
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connections:
                    try:
                        websocket = self.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送房间信息变化消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送房间信息变化消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                        
            logger.info(
                f"房间信息变化消息发送完成: "
                f"房间ID={room_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送信息变化消息时发生错误: {str(e)}")

    async def _send_room_dissolved_local(self, room_id: str, player_ids: list) -> None:
        """
        在当前实例中向房间玩家发送解散消息
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
        """
        try:
            message = {
                "type": "room_dissolved",
                "room_id": room_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"开始向房间 {room_id} 的玩家发送解散消息")
            
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connections:
                    try:
                        websocket = self.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送房间解散消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送房间解散消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                        
            logger.info(
                f"房间解散消息发送完成: "
                f"房间ID={room_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送解散消息时发生错误: {str(e)}")

    async def _send_game_loading_local(self, room_id: str, player_ids: list) -> None:
        """
        在当前实例中向房间玩家发送游戏加载消息
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
        """
        try:
            message = {
                "type": "game_loading",
                "room_id": room_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"开始向房间 {room_id} 的玩家发送游戏加载消息")
            
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connections:
                    try:
                        websocket = self.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送游戏加载消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送游戏加载消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                        
            logger.info(
                f"游戏加载消息发送完成: "
                f"房间ID={room_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送游戏加载消息时发生错误: {str(e)}")

    async def _send_game_start_local(self, battle_id: str, room_id: str, player_ids: list) -> None:
        """
        在当前实例中向房间玩家发送游戏开始消息
        
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
            
            logger.info(f"开始向房间 {room_id} 的玩家发送游戏开始消息")
            
            receivers = []
            failed_receivers = []
            
            for user_id in player_ids:
                if user_id in self.connections:
                    try:
                        websocket = self.connections[user_id]["websocket"]
                        await websocket.send_json(message)
                        receivers.append(user_id)
                        logger.debug(f"成功发送游戏开始消息给用户 {user_id}")
                    except Exception as e:
                        logger.error(f"发送游戏开始消息给用户 {user_id} 时发生错误: {str(e)}")
                        failed_receivers.append(user_id)
                        
            logger.info(
                f"游戏开始消息发送完成: "
                f"房间ID={room_id}, 对战ID={battle_id}, "
                f"成功发送给 {len(receivers)} 个用户: {', '.join(receivers)}, "
                f"失败 {len(failed_receivers)} 个用户: {', '.join(failed_receivers) if failed_receivers else '无'}"
            )
            
        except Exception as e:
            logger.error(f"向房间玩家发送游戏开始消息时发生错误: {str(e)}") 