from fastapi import APIRouter
from .endpoints import cards, decks

api_router = APIRouter()

# 注册卡牌相关路由
api_router.include_router(cards.router, tags=["cards"])

# 注册卡组相关路由
api_router.include_router(decks.router, tags=["decks"])