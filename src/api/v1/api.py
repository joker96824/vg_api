from fastapi import APIRouter
from .endpoints import cards

api_router = APIRouter()

# 注册卡牌相关路由
api_router.include_router(cards.router, tags=["cards"])