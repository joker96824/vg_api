from fastapi import APIRouter
from .endpoints import cards, decks, auth, friendship, websocket, rooms
from . import card_import

api_router = APIRouter()

# 注册卡牌相关路由
api_router.include_router(cards.router, tags=["cards"])

# 注册卡组相关路由
api_router.include_router(decks.router, tags=["decks"])

# 注册卡牌导入相关路由
api_router.include_router(card_import.router, prefix="/card_import", tags=["card_import"])

# 注册认证相关路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 注册好友相关路由
api_router.include_router(friendship.router, prefix="/friends", tags=["friends"])

# 注册房间相关路由
api_router.include_router(rooms.router, tags=["rooms"])

# 注册WebSocket路由
api_router.include_router(websocket.router, tags=["websocket"])