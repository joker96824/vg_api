from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.core.database import get_session
from src.core.schemas.deck import (
    DeckCreate, DeckUpdate, DeckResponse, 
    DeckCardCreate, DeckQueryParams
)
from src.core.services.deck import DeckService
from src.core.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/decks", response_model=DeckResponse, summary="创建卡组")
async def create_deck(
    deck: DeckCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """创建新卡组"""
    deck_service = DeckService(session)
    return await deck_service.create_deck(deck, current_user["id"])


@router.get("/decks/{deck_id}", response_model=DeckResponse, summary="获取卡组详情")
async def get_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """获取指定卡组的详细信息"""
    deck_service = DeckService(session)
    deck = await deck_service.get_deck(deck_id)
    if not deck:
        logger.warning(f"未找到卡组: {deck_id}")
        raise HTTPException(status_code=404, detail="Deck not found")
    # 验证是否是卡组所有者
    if str(deck.user_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权访问此卡组")
    return deck


@router.get("/decks", response_model=List[DeckResponse], summary="获取卡组列表")
async def get_decks(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """获取当前用户的卡组列表"""
    try:
        params = DeckQueryParams(
            user_id=current_user["id"],
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
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新指定卡组的信息和卡片列表"""
    deck_service = DeckService(session)
    # 先获取卡组信息
    existing_deck = await deck_service.get_deck(deck_id)
    if not existing_deck:
        raise HTTPException(status_code=404, detail="卡组不存在")
    # 验证是否是卡组所有者
    if str(existing_deck.user_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权修改此卡组")
        
    updated_deck = await deck_service.update_deck(deck_id, deck)
    return updated_deck


@router.delete("/decks/{deck_id}", summary="删除卡组")
async def delete_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """删除指定卡组（软删除）"""
    deck_service = DeckService(session)
    # 先获取卡组信息
    existing_deck = await deck_service.get_deck(deck_id)
    if not existing_deck:
        raise HTTPException(status_code=404, detail="卡组不存在")
    # 验证是否是卡组所有者
    if str(existing_deck.user_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权删除此卡组")
        
    if not await deck_service.delete_deck(deck_id):
        raise HTTPException(status_code=404, detail="卡组不存在")
    return {"message": "卡组已删除"}


@router.patch("/decks/{deck_id}/info", response_model=DeckResponse, summary="更新卡组名称和描述")
async def update_deck_info(
    request: Request,
    deck_id: UUID,
    deck_name: str = Body(None, description="新的卡组名称"),
    deck_description: str = Body(None, description="新的卡组描述"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新卡组的名称和描述"""
    # 记录请求参数
    logger.info("="*50)
    logger.info("更新卡组信息 - 请求参数:")
    logger.info(f"deck_id: {deck_id}")
    logger.info("请求体原始内容:")
    request_body = await request.json()
    logger.info(f"request body: {request_body}")
    logger.info("="*50)
    
    try:
        deck_service = DeckService(session)
        # 先获取卡组信息
        existing_deck = await deck_service.get_deck(deck_id)
        if not existing_deck:
            raise HTTPException(status_code=404, detail="卡组不存在")
        # 验证是否是卡组所有者
        if str(existing_deck.user_id) != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权修改此卡组")
            
        updated_deck = await deck_service.update_deck_info(deck_id, deck_name, deck_description)
        
        # 记录更新结果
        logger.info("更新结果:")
        logger.info(f"更新后的卡组名称: {updated_deck.deck_name}")
        logger.info(f"更新后的卡组描述: {updated_deck.deck_description}")
        logger.info("="*50)
        
        return updated_deck
        
    except Exception as e:
        logger.error(f"更新卡组信息时发生错误 - deck_id: {deck_id}, error: {str(e)}")
        logger.error(f"错误类型: {type(e)}")
        logger.error(f"错误详情: {str(e)}")
        logger.error("="*50)
        raise HTTPException(status_code=500, detail=f"更新卡组信息失败: {str(e)}")


@router.patch("/decks/{deck_id}/preset", response_model=DeckResponse, summary="更新卡组预设值")
async def update_deck_preset(
    deck_id: UUID,
    preset: int = Query(..., description="新的预设值"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新卡组的预设值"""
    deck_service = DeckService(session)
    # 先获取卡组信息
    existing_deck = await deck_service.get_deck(deck_id)
    if not existing_deck:
        raise HTTPException(status_code=404, detail="卡组不存在")
    # 验证是否是卡组所有者
    if str(existing_deck.user_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权修改此卡组")
        
    updated_deck = await deck_service.update_deck_preset(deck_id, preset)
    return updated_deck


@router.post("/decks/{deck_id}/copy", response_model=DeckResponse, summary="复制卡组")
async def copy_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """复制指定卡组"""
    deck_service = DeckService(session)
    new_deck = await deck_service.copy_deck(current_user["id"], deck_id)
    if not new_deck:
        raise HTTPException(status_code=404, detail="原卡组不存在")
    return new_deck