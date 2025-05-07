from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

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

@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card_by_id(
    card_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    根据ID查询卡牌
    """
    logger.debug(f"收到ID查询请求: {card_id}")

    card_service = CardService(session)
    card = await card_service.get_card_by_id(card_id)
    
    if not card:
        logger.warning(f"未找到卡牌: {card_id}")
        raise HTTPException(status_code=404, detail="Card not found")

    logger.debug(f"查询结果: {card}")

    return card

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