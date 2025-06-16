from typing import Dict, Any, Optional, List
from fastapi import WebSocket
from datetime import datetime, timedelta
import logging
import asyncio
import json
import redis
from config.settings import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        self.connection_timeout = 120  # 连接超时时间（秒）
        self._heartbeat_task = None
        self._redis_sub_task = None
        
        # 初始化 Redis 连接
        try:
            logger.info("初始化 Redis 连接")
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # 测试连接
            self.redis.ping()
            logger.info("Redis 连接成功")
            
            # 初始化 pubsub
            self.pubsub = self.redis.pubsub()
            logger.info("Redis pubsub 初始化成功")
        except Exception as e:
            logger.error(f"Redis 连接初始化失败: {str(e)}")
            raise
        
    async def start_heartbeat(self):
        """启动心跳检测任务"""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
    async def start_redis_subscriber(self):
        """启动 Redis 订阅任务"""
        if self._redis_sub_task is None:
            logger.info("启动 Redis 订阅任务")
            self._redis_sub_task = asyncio.create_task(self._redis_sub_loop())
            
    async def stop_redis_subscriber(self):
        """停止 Redis 订阅任务"""
        if self._redis_sub_task:
            logger.info("停止 Redis 订阅任务")
            self._redis_sub_task.cancel()
            self._redis_sub_task = None
            
    async def _redis_sub_loop(self):
        """Redis 订阅循环"""
        try:
            logger.info("开始订阅 Redis 频道: websocket_broadcast")
            # 使用同步方式订阅
            self.pubsub.subscribe('websocket_broadcast')
            logger.info("Redis 订阅成功")
            
            while True:
                try:
                    # 使用同步方式获取消息
                    message = self.pubsub.get_message(ignore_subscribe_messages=True)
                    
                    if message and message['type'] == 'message':
                        logger.info(f"收到 Redis 消息: {message['data']}")
                        data = json.loads(message['data'])
                        await self._handle_redis_message(data)
                    # 使用 asyncio.sleep 而不是直接 sleep
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    logger.info("Redis 订阅任务被取消")
                    break
                except Exception as e:
                    logger.error(f"处理 Redis 消息时发生错误: {str(e)}")
        except Exception as e:
            logger.error(f"Redis 订阅失败: {str(e)}")
            raise
                
    async def _handle_redis_message(self, data: Dict[str, Any]):
        """处理从 Redis 接收到的消息"""
        try:
            message = data.get('message')
            exclude_user_id = data.get('exclude_user_id')
            
            if message:
                logger.info(f"处理 Redis 消息: 类型={message.get('type')}, 内容={message.get('content', '')}, 排除用户={exclude_user_id}")
                # 在本地广播消息
                await self._local_broadcast(message, exclude_user_id)
            else:
                logger.warning("收到空的 Redis 消息")
        except Exception as e:
            logger.error(f"处理 Redis 消息时发生错误: {str(e)}")
            
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
            
            # 使用同步方式发布消息
            self.redis.publish('websocket_broadcast', json.dumps({
                'message': message,
                'exclude_user_id': exclude_user_id
            }))
            logger.info("消息已发布到 Redis")
            
        except Exception as e:
            logger.error(f"广播消息时发生错误: {str(e)}")
            
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