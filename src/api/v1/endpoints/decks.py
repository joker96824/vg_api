from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.core.database import get_session
from src.core.schemas.deck import (
    DeckCreate, DeckUpdate, DeckResponse, 
    DeckCardCreate, DeckQueryParams
)
from src.core.services.deck import DeckService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/decks", response_model=DeckResponse, summary="创建卡组")
async def create_deck(
    deck: DeckCreate,
    session: AsyncSession = Depends(get_session)
):
    """创建新卡组"""
    deck_service = DeckService(session)
    return await deck_service.create_deck(deck)


@router.get("/decks/{deck_id}", response_model=DeckResponse, summary="获取卡组详情")
async def get_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """获取指定卡组的详细信息"""
    deck_service = DeckService(session)
    deck = await deck_service.get_deck(deck_id)
    if not deck:
        logger.warning(f"未找到卡组: {deck_id}")
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@router.get("/decks", response_model=List[DeckResponse], summary="获取卡组列表")
async def get_decks(
    user_id: UUID = Query(..., description="用户ID"),
    session: AsyncSession = Depends(get_session)
):
    """获取指定用户的卡组列表"""
    try:
        params = DeckQueryParams(
            user_id=user_id,
            page=1,
            page_size=100
        )
        logger.debug(f"查询参数: {params}")
        
        deck_service = DeckService(session)
        total, decks = await deck_service.get_decks(params)
        logger.debug(f"返回数据: {decks}")
        
        return decks
    except Exception as e:
        logger.error(f"获取卡组列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取卡组列表失败: {str(e)}")


@router.put("/decks/{deck_id}", response_model=DeckResponse, summary="更新卡组")
async def update_deck(
    deck_id: UUID,
    deck: DeckUpdate,
    session: AsyncSession = Depends(get_session)
):
    """更新指定卡组的信息和卡片列表"""
    deck_service = DeckService(session)
    updated_deck = await deck_service.update_deck(deck_id, deck)
    if not updated_deck:
        raise HTTPException(status_code=404, detail="卡组不存在")
    return updated_deck


@router.delete("/decks/{deck_id}", summary="删除卡组")
async def delete_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """删除指定卡组（软删除）"""
    deck_service = DeckService(session)
    if not await deck_service.delete_deck(deck_id):
        raise HTTPException(status_code=404, detail="卡组不存在")
    return {"message": "卡组已删除"}