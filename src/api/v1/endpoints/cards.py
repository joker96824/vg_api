from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from uuid import UUID

from src.core.database import get_session
from src.core.schemas.card import CardResponse, CardQueryParams
from src.core.services.card import CardService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/cards", response_model=List[CardResponse])
async def get_cards(
    params: CardQueryParams = Depends(),
    session: AsyncSession = Depends(get_session)
):
    """
    查询卡牌列表
    """
    logger.debug(f"收到查询请求: {params}")

    card_service = CardService(session)
    cards, total = await card_service.get_cards(params)

    logger.debug(f"查询结果: {cards}")

    return cards

@router.get("/cards/{card_id}", response_model=List[CardResponse])
async def get_card_by_id(
    card_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    根据ID查询卡牌，支持多个ID（用逗号分隔）
    """
    logger.debug(f"收到ID查询请求: {card_id}")

    # 将逗号分隔的字符串转换为UUID列表
    try:
        card_ids = [UUID(id.strip()) for id in card_id.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid card ID format")

    card_service = CardService(session)
    cards = await card_service.get_cards_by_ids(card_ids)
    
    if not cards:
        logger.warning(f"未找到卡牌: {card_id}")
        raise HTTPException(status_code=404, detail="Cards not found")

    logger.debug(f"查询结果: {cards}")

    return cards

@router.get("/cards/code/{card_code}", response_model=CardResponse)
async def get_card_by_code(
    card_code: str,
    session: AsyncSession = Depends(get_session)
):
    """
    根据卡牌编号查询卡牌
    """
    logger.debug(f"收到编号查询请求: {card_code}")

    card_service = CardService(session)
    card = await card_service.get_card_by_code(card_code)
    
    if not card:
        logger.warning(f"未找到卡牌: {card_code}")
        raise HTTPException(status_code=404, detail="Card not found")

    logger.debug(f"查询结果: {card}")

    return card 