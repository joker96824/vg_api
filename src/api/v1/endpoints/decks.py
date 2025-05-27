from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.schemas.deck import (
    DeckCreate, DeckUpdate, DeckInDB, 
    DeckCardCreate, DeckQueryParams,
    DeckSuccessResponse, DeckListSuccessResponse,
    DeckCardSuccessResponse, DeckCardListSuccessResponse,
    DeleteSuccessResponse, DeleteResponse,
    ResponseCode, ErrorResponse
)
from src.core.services.deck import DeckService
from src.core.auth import get_current_user
from src.core.utils.logger import APILogger

router = APIRouter()


@router.post("/decks", response_model=DeckSuccessResponse, summary="创建卡组")
async def create_deck(
    deck: DeckCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """创建新卡组"""
    try:
        APILogger.log_request(
            "创建卡组",
            用户ID=current_user["id"],
            卡组信息=deck.dict()
        )
        
        deck_service = DeckService(session)
        result = await deck_service.create_deck(deck, current_user["id"])
        
        APILogger.log_response(
            "创建卡组",
            卡组ID=str(result.id),
            卡组名称=result.deck_name
        )
        
        return DeckSuccessResponse.create(
            code=ResponseCode.CREATE_SUCCESS,
            message="卡组创建成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("创建卡组", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"创建卡组失败: {str(e)}"
            ).dict()
        )


@router.get("/decks/{deck_id}", response_model=DeckSuccessResponse, summary="获取卡组详情")
async def get_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """获取指定卡组的详细信息"""
    try:
        APILogger.log_request(
            "获取卡组详情",
            用户ID=current_user["id"],
            卡组ID=str(deck_id)
        )
        
        deck_service = DeckService(session)
        deck = await deck_service.get_deck(deck_id)
        
        if not deck:
            APILogger.log_warning(
                "获取卡组详情",
                "未找到卡组",
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡组不存在"
                ).dict()
            )
            
        # 验证是否是卡组所有者
        if str(deck.user_id) != current_user["id"]:
            APILogger.log_warning(
                "获取卡组详情",
                "无权访问卡组",
                用户ID=current_user["id"],
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权访问此卡组"
                ).dict()
            )
            
        APILogger.log_response(
            "获取卡组详情",
            卡组ID=str(deck.id),
            卡组名称=deck.deck_name
        )
        
        return DeckSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取卡组详情成功",
            data=deck
        )
    except Exception as e:
        APILogger.log_error("获取卡组详情", e, 用户ID=current_user["id"], 卡组ID=str(deck_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取卡组详情失败: {str(e)}"
            ).dict()
        )


@router.get("/decks", response_model=DeckListSuccessResponse, summary="获取卡组列表")
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
        
        APILogger.log_request(
            "获取卡组列表",
            用户ID=current_user["id"],
            查询参数=params.dict()
        )
        
        deck_service = DeckService(session)
        total, decks = await deck_service.get_decks(params)
        
        APILogger.log_response(
            "获取卡组列表",
            总记录数=total,
            返回记录数=len(decks)
        )
        
        return DeckListSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取卡组列表成功",
            data={
                "total": total,
                "items": decks
            }
        )
    except Exception as e:
        APILogger.log_error("获取卡组列表", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取卡组列表失败: {str(e)}"
            ).dict()
        )


@router.put("/decks/{deck_id}", response_model=DeckSuccessResponse, summary="更新卡组")
async def update_deck(
    deck_id: UUID,
    deck: DeckUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新指定卡组的信息和卡片列表"""
    try:
        APILogger.log_request(
            "更新卡组",
            用户ID=current_user["id"],
            卡组ID=str(deck_id),
            更新信息=deck.dict()
        )
        
        deck_service = DeckService(session)
        # 先获取卡组信息
        existing_deck = await deck_service.get_deck(deck_id)
        if not existing_deck:
            APILogger.log_warning(
                "更新卡组",
                "未找到卡组",
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡组不存在"
                ).dict()
            )
            
        # 验证是否是卡组所有者
        if str(existing_deck.user_id) != current_user["id"]:
            APILogger.log_warning(
                "更新卡组",
                "无权修改卡组",
                用户ID=current_user["id"],
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权修改此卡组"
                ).dict()
            )
            
        updated_deck = await deck_service.update_deck(deck_id, deck)
        
        APILogger.log_response(
            "更新卡组",
            卡组ID=str(updated_deck.id),
            卡组名称=updated_deck.deck_name
        )
        
        return DeckSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="卡组更新成功",
            data=updated_deck
        )
    except Exception as e:
        APILogger.log_error("更新卡组", e, 用户ID=current_user["id"], 卡组ID=str(deck_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"更新卡组失败: {str(e)}"
            ).dict()
        )


@router.delete("/decks/{deck_id}", response_model=DeleteSuccessResponse, summary="删除卡组")
async def delete_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """删除指定卡组（软删除）"""
    try:
        APILogger.log_request(
            "删除卡组",
            用户ID=current_user["id"],
            卡组ID=str(deck_id)
        )
        
        deck_service = DeckService(session)
        # 先获取卡组信息
        existing_deck = await deck_service.get_deck(deck_id)
        if not existing_deck:
            APILogger.log_warning(
                "删除卡组",
                "未找到卡组",
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡组不存在"
                ).dict()
            )
            
        # 验证是否是卡组所有者
        if str(existing_deck.user_id) != current_user["id"]:
            APILogger.log_warning(
                "删除卡组",
                "无权删除卡组",
                用户ID=current_user["id"],
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权删除此卡组"
                ).dict()
            )
            
        if not await deck_service.delete_deck(deck_id):
            APILogger.log_warning(
                "删除卡组",
                "删除失败",
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡组不存在"
                ).dict()
            )
            
        APILogger.log_response(
            "删除卡组",
            卡组ID=str(deck_id),
            操作结果="成功"
        )
        
        return DeleteSuccessResponse.create(
            code=ResponseCode.DELETE_SUCCESS,
            message="卡组删除成功",
            data=DeleteResponse()
        )
    except Exception as e:
        APILogger.log_error("删除卡组", e, 用户ID=current_user["id"], 卡组ID=str(deck_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"删除卡组失败: {str(e)}"
            ).dict()
        )


@router.patch("/decks/{deck_id}/info", response_model=DeckSuccessResponse, summary="更新卡组名称和描述")
async def update_deck_info(
    request: Request,
    deck_id: UUID,
    deck_name: str = Body(None, description="新的卡组名称"),
    deck_description: str = Body(None, description="新的卡组描述"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新卡组的名称和描述"""
    try:
        request_body = await request.json()
        APILogger.log_request(
            "更新卡组信息",
            用户ID=current_user["id"],
            卡组ID=str(deck_id),
            请求参数=request_body
        )
        
        deck_service = DeckService(session)
        # 先获取卡组信息
        existing_deck = await deck_service.get_deck(deck_id)
        if not existing_deck:
            APILogger.log_warning(
                "更新卡组信息",
                "未找到卡组",
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡组不存在"
                ).dict()
            )
            
        # 验证是否是卡组所有者
        if str(existing_deck.user_id) != current_user["id"]:
            APILogger.log_warning(
                "更新卡组信息",
                "无权修改卡组",
                用户ID=current_user["id"],
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权修改此卡组"
                ).dict()
            )
            
        updated_deck = await deck_service.update_deck_info(deck_id, deck_name, deck_description)
        
        APILogger.log_response(
            "更新卡组信息",
            卡组ID=str(updated_deck.id),
            卡组名称=updated_deck.deck_name,
            卡组描述=updated_deck.deck_description
        )
        
        return DeckSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="卡组信息更新成功",
            data=updated_deck
        )
    except Exception as e:
        APILogger.log_error("更新卡组信息", e, 用户ID=current_user["id"], 卡组ID=str(deck_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"更新卡组信息失败: {str(e)}"
            ).dict()
        )


@router.patch("/decks/{deck_id}/preset", response_model=DeckSuccessResponse, summary="更新卡组预设值")
async def update_deck_preset(
    deck_id: UUID,
    preset: int = Query(..., description="新的预设值"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """更新卡组的预设值"""
    try:
        APILogger.log_request(
            "更新卡组预设值",
            用户ID=current_user["id"],
            卡组ID=str(deck_id),
            预设值=preset
        )
        
        deck_service = DeckService(session)
        # 先获取卡组信息
        existing_deck = await deck_service.get_deck(deck_id)
        if not existing_deck:
            APILogger.log_warning(
                "更新卡组预设值",
                "未找到卡组",
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="卡组不存在"
                ).dict()
            )
            
        # 验证是否是卡组所有者
        if str(existing_deck.user_id) != current_user["id"]:
            APILogger.log_warning(
                "更新卡组预设值",
                "无权修改卡组",
                用户ID=current_user["id"],
                卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权修改此卡组"
                ).dict()
            )
            
        updated_deck = await deck_service.update_deck_preset(deck_id, preset)
        
        APILogger.log_response(
            "更新卡组预设值",
            卡组ID=str(updated_deck.id),
            预设值=updated_deck.preset
        )
        
        return DeckSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="卡组预设值更新成功",
            data=updated_deck
        )
    except Exception as e:
        APILogger.log_error("更新卡组预设值", e, 用户ID=current_user["id"], 卡组ID=str(deck_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"更新卡组预设值失败: {str(e)}"
            ).dict()
        )


@router.post("/decks/{deck_id}/copy", response_model=DeckSuccessResponse, summary="复制卡组")
async def copy_deck(
    deck_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """复制指定卡组"""
    try:
        APILogger.log_request(
            "复制卡组",
            用户ID=current_user["id"],
            原卡组ID=str(deck_id)
        )
        
        deck_service = DeckService(session)
        new_deck = await deck_service.copy_deck(current_user["id"], deck_id)
        
        if not new_deck:
            APILogger.log_warning(
                "复制卡组",
                "原卡组不存在",
                原卡组ID=str(deck_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="原卡组不存在"
                ).dict()
            )
            
        APILogger.log_response(
            "复制卡组",
            原卡组ID=str(deck_id),
            新卡组ID=str(new_deck.id),
            新卡组名称=new_deck.deck_name
        )
        
        return DeckSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="卡组复制成功",
            data=new_deck
        )
    except Exception as e:
        APILogger.log_error("复制卡组", e, 用户ID=current_user["id"], 原卡组ID=str(deck_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"复制卡组失败: {str(e)}"
            ).dict()
        )