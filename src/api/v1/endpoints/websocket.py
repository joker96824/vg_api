from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
from src.core.services.websocket import WebSocketService
from src.core.deps import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    async for session in get_db():
        service = WebSocketService(session)
        
        try:
            # 处理连接
            await service.handle_connect(websocket)
            
            # 处理消息循环
            while True:
                try:
                    # 接收消息
                    message = await websocket.receive_json()
                    logger.info(f"收到消息: {message}")
                    
                    # 处理消息
                    await service.handle_message(websocket, message)
                    
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
        break  # 确保只使用一次数据库会话 