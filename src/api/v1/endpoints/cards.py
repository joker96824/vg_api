from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.core.database import get_session
from src.core.schemas.card import CardResponse, CardQueryParams
from src.core.services.card import CardService
from src.core.auth import get_current_user
from src.core.utils.logger import APILogger

router = APIRouter()

@router.get("/cards", response_model=List[CardResponse])
async def get_cards(
    params: CardQueryParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """
    查询卡牌列表
    """
    try:
        APILogger.log_request(
            "获取卡牌列表",
            用户ID=current_user["id"],
            查询参数=params.dict()
        )

        card_service = CardService(session)
        cards, total = await card_service.get_cards(params)

        APILogger.log_response(
            "获取卡牌列表",
            总记录数=total,
            返回记录数=len(cards)
        )

        return cards
    except Exception as e:
        APILogger.log_error("获取卡牌列表", e, 用户ID=current_user["id"])
        raise HTTPException(status_code=500, detail=f"获取卡牌列表失败: {str(e)}")

@router.get("/cards/{card_id}", response_model=List[CardResponse])
async def get_card_by_id(
    card_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    根据ID查询卡牌，支持多个ID（用逗号分隔）
    """
    try:
        APILogger.log_request(
            "根据ID查询卡牌",
            卡牌ID=card_id
        )

        # 将逗号分隔的字符串转换为UUID列表
        try:
            card_ids = [UUID(id.strip()) for id in card_id.split(",")]
        except ValueError:
            APILogger.log_warning(
                "根据ID查询卡牌",
                "无效的卡牌ID格式",
                卡牌ID=card_id
            )
            raise HTTPException(status_code=400, detail="Invalid card ID format")

        card_service = CardService(session)
        cards = await card_service.get_cards_by_ids(card_ids)
        
        if not cards:
            APILogger.log_warning(
                "根据ID查询卡牌",
                "未找到卡牌",
                卡牌ID=card_id
            )
            raise HTTPException(status_code=404, detail="Cards not found")

        APILogger.log_response(
            "根据ID查询卡牌",
            找到卡牌数=len(cards),
            卡牌ID=card_id
        )

        return cards
    except Exception as e:
        APILogger.log_error("根据ID查询卡牌", e, 卡牌ID=card_id)
        raise HTTPException(status_code=500, detail=f"查询卡牌失败: {str(e)}")

@router.get("/cards/code/{card_code}", response_model=CardResponse)
async def get_card_by_code(
    card_code: str,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """
    根据卡牌编号查询卡牌
    """
    try:
        APILogger.log_request(
            "根据编号查询卡牌",
            用户ID=current_user["id"],
            卡牌编号=card_code
        )

        card_service = CardService(session)
        card = await card_service.get_card_by_code(card_code)
        
        if not card:
            APILogger.log_warning(
                "根据编号查询卡牌",
                "未找到卡牌",
                卡牌编号=card_code
            )
            raise HTTPException(status_code=404, detail="Card not found")

        APILogger.log_response(
            "根据编号查询卡牌",
            **APILogger.format_card_info(card)
        )

        return card
    except Exception as e:
        APILogger.log_error("根据编号查询卡牌", e, 卡牌编号=card_code)
        raise HTTPException(status_code=500, detail=f"查询卡牌失败: {str(e)}") 