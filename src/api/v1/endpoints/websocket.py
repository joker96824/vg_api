from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import logging
from src.core.websocket.websocket_service import WebSocketService
from src.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.services.auth import AuthService
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_session)):
    """WebSocket连接端点"""
    service = WebSocketService(db)
    auth_service = AuthService(db)
    
    try:
        # 处理连接
        await service.handle_connect(websocket)
        
        # 处理消息循环
        while True:
            try:
                # 接收消息
                data = await websocket.receive_json()
                logger.info(f"收到消息: {data}")
                
                # 处理消息
                await service.handle_message(websocket, data)
                
                # 如果是认证消息，检查会话状态
                if data.get("type") == "auth":
                    token = data.get("token")
                    if token:
                        # 检查会话状态
                        session_status = await auth_service.check_session(
                            user_id=data.get("user_id"),
                            token=token
                        )
                        
                        # 如果会话需要刷新，发送刷新通知
                        if session_status.get("needs_refresh"):
                            await service.send_system_notification(
                                content="您的会话即将过期，请刷新token",
                                level="warning",
                                target_user_id=data.get("user_id")
                            )
                
            except WebSocketDisconnect:
                logger.info("WebSocket连接断开")
                await service.handle_disconnect(websocket)
                break
            except Exception as e:
                logger.error(f"处理消息时发生错误: {str(e)}")
                await service.handle_disconnect(websocket)
                break
                
    except Exception as e:
        logger.error(f"WebSocket连接处理时发生错误: {str(e)}")
    finally:
        await service.handle_disconnect(websocket) 