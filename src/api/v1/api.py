from fastapi import APIRouter
from .endpoints import cards, decks, auth
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