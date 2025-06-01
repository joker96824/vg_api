from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.core.database import get_session
from src.core.schemas.card import (
    CardQueryParams,
    CardSuccessResponse, CardListSuccessResponse,
    ErrorResponse, ResponseCode,
    CardListResponse, CardIdsRequest,
    UpdateCardAbilityRequest, SuccessResponse
)
from src.core.services.card import CardService
from src.core.auth import get_current_user
from src.core.utils.logger import APILogger

router = APIRouter()

@router.get("/cards", response_model=CardListSuccessResponse)
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

        return CardListSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取卡牌列表成功",
            data=CardListResponse(total=total, items=cards)
        )
    except Exception as e:
        APILogger.log_error("获取卡牌列表", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取卡牌列表失败: {str(e)}"
            ).dict()
        )

@router.post("/cards/batch", response_model=CardListSuccessResponse)
async def get_cards_by_ids(
    data: CardIdsRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    批量获取卡牌信息
    """
    try:
        APILogger.log_request(
            "批量获取卡牌",
            卡牌ID列表=data.card_ids
        )

        card_service = CardService(session)
        cards = await card_service.get_cards_by_ids(data.card_ids)
        
        if not cards:
            APILogger.log_warning(
                "批量获取卡牌",
                "未找到卡牌",
                卡牌ID列表=data.card_ids
            )
            return CardListSuccessResponse.create(
                code=ResponseCode.SUCCESS,
                message="未找到卡牌",
                data=CardListResponse(total=0, items=[])
            )

        APILogger.log_response(
            "批量获取卡牌",
            返回记录数=len(cards)
        )

        return CardListSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取卡牌成功",
            data=CardListResponse(total=len(cards), items=cards)
        )
    except Exception as e:
        APILogger.log_error("批量获取卡牌", e, 卡牌ID列表=data.card_ids)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取卡牌失败: {str(e)}"
            ).dict()
        )

@router.get("/cards/code/{card_code}", response_model=CardSuccessResponse)
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
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡牌不存在"
                ).dict()
            )

        APILogger.log_response(
            "根据编号查询卡牌",
            **APILogger.format_card_info(card)
        )

        return CardSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取卡牌成功",
            data=card
        )
    except Exception as e:
        APILogger.log_error("根据编号查询卡牌", e, 卡牌编号=card_code)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"查询卡牌失败: {str(e)}"
            ).dict()
        )

@router.put("/cards/abilities", response_model=SuccessResponse[Dict[str, Any]])
async def update_card_ability(
    request: Request,
    data: UpdateCardAbilityRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新卡牌能力内容"""
    try:
        # 检查权限
        if current_user.get("level", 1) < 5:
            APILogger.log_warning(
                "更新卡牌能力",
                "权限不足",
                用户ID=current_user["id"],
                当前等级=current_user.get("level", 1)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="需要管理员权限"
                ).dict()
            )

        APILogger.log_request(
            "更新卡牌能力",
            操作者ID=current_user["id"],
            目标ID=data.id,
            IP=request.client.host
        )
        
        card_service = CardService(db)
        result = await card_service.update_card_ability(
            ability_id=data.id,
            ability=data.ability,
            operator_id=current_user["id"],
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "更新卡牌能力",
            操作者ID=current_user["id"],
            目标ID=data.id,
            操作结果="成功"
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="卡牌能力修改成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "更新卡牌能力",
            "操作失败",
            操作者ID=current_user["id"],
            目标ID=data.id,
            错误信息=str(e)
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )
    except Exception as e:
        APILogger.log_error("更新卡牌能力", e, 操作者ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"更新卡牌能力失败: {str(e)}"
            ).dict()
        ) 