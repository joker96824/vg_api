from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.core.deps import get_db
from src.core.auth import get_current_user, require_admin
from src.core.services.match import MatchService
from src.core.utils.logger import APILogger
from src.core.schemas.response import ResponseCode, ErrorResponse
from src.core.schemas.match import (
    MatchResultSuccessResponse, MatchResultResponse,
    ConfirmMatchSuccessResponse, ConfirmMatchResponse,
    MatchStatusSuccessResponse, MatchStatusResponse,
    CleanupResultSuccessResponse, CleanupResultResponse,
    DeleteSuccessResponse, DeleteResponse
)

router = APIRouter()

# 确认匹配请求模型
class ConfirmMatchRequest(BaseModel):
    match_id: str = Field(..., description="匹配ID")
    confirm: bool = Field(..., description="是否确认匹配")

@router.post("/match/join", response_model=MatchResultSuccessResponse, summary="加入匹配队列")
async def join_match_queue(
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """加入匹配队列"""
    try:
        APILogger.log_request(
            "加入匹配队列",
            用户ID=current_user["id"]
        )
        
        # 构建用户信息
        user_info = {
            "id": str(current_user["id"]),
            "nickname": current_user.get("nickname", ""),
            "avatar": current_user.get("avatar", "")
        }
        
        match_service = MatchService(session)
        result = await match_service.join_match_queue(current_user["id"], user_info)
        
        if not result["success"]:
            APILogger.log_warning(
                "加入匹配队列",
                result["message"],
                用户ID=current_user["id"]
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message=result["message"]
                ).dict()
            )
        
        APILogger.log_response(
            "加入匹配队列",
            用户ID=current_user["id"],
            匹配ID=result.get("match_id"),
            房间ID=result.get("room_id"),
            是否匹配成功=result.get("room_id") is not None
        )
        
        return MatchResultSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message=result["message"],
            data=MatchResultResponse(
                match_id=result["match_id"],
                room_id=result.get("room_id"),
                room_name=result.get("room_name"),
                matched_users=result.get("matched_users")
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("加入匹配队列", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"加入匹配队列失败: {str(e)}"
            ).dict()
        )

@router.post("/match/confirm", response_model=ConfirmMatchSuccessResponse, summary="确认或拒绝匹配")
async def confirm_match(
    confirm_request: ConfirmMatchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """确认或拒绝匹配"""
    try:
        APILogger.log_request(
            "确认匹配",
            用户ID=current_user["id"],
            匹配ID=confirm_request.match_id,
            是否确认=confirm_request.confirm
        )
        
        match_service = MatchService(session)
        result = await match_service.confirm_match(
            current_user["id"], 
            confirm_request.match_id, 
            confirm_request.confirm
        )
        
        if not result["success"]:
            APILogger.log_warning(
                "确认匹配",
                result["message"],
                用户ID=current_user["id"],
                匹配ID=confirm_request.match_id
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message=result["message"]
                ).dict()
            )
        
        APILogger.log_response(
            "确认匹配",
            用户ID=current_user["id"],
            匹配ID=confirm_request.match_id,
            是否确认=confirm_request.confirm,
            房间ID=result.get("room_id")
        )
        
        return ConfirmMatchSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message=result["message"],
            data=ConfirmMatchResponse(
                room_id=result.get("room_id"),
                room_name=result.get("room_name")
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("确认匹配", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"确认匹配失败: {str(e)}"
            ).dict()
        )

@router.post("/match/leave", response_model=DeleteSuccessResponse, summary="离开匹配队列")
async def leave_match_queue(
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """离开匹配队列"""
    try:
        APILogger.log_request(
            "离开匹配队列",
            用户ID=current_user["id"]
        )
        
        match_service = MatchService(session)
        result = await match_service.leave_match_queue(current_user["id"])
        
        if not result["success"]:
            APILogger.log_warning(
                "离开匹配队列",
                result["message"],
                用户ID=current_user["id"]
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message=result["message"]
                ).dict()
            )
        
        APILogger.log_response(
            "离开匹配队列",
            用户ID=current_user["id"]
        )
        
        return DeleteSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message=result["message"],
            data=DeleteResponse()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("离开匹配队列", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"离开匹配队列失败: {str(e)}"
            ).dict()
        )

@router.get("/match/status", response_model=MatchStatusSuccessResponse, summary="获取匹配状态")
async def get_match_status(
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取当前用户的匹配状态"""
    try:
        APILogger.log_request(
            "获取匹配状态",
            用户ID=current_user["id"]
        )
        
        match_service = MatchService(session)
        result = await match_service.get_match_status(current_user["id"])
        
        APILogger.log_response(
            "获取匹配状态",
            用户ID=current_user["id"],
            是否在队列中=result.get("in_queue", False),
            队列位置=result.get("position", 0)
        )
        
        return MatchStatusSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取匹配状态成功",
            data=MatchStatusResponse(
                in_queue=result.get("in_queue", False),
                position=result.get("position", 0),
                match_id=result.get("match_id"),
                created_at=result.get("created_at")
            )
        )
        
    except Exception as e:
        APILogger.log_error("获取匹配状态", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取匹配状态失败: {str(e)}"
            ).dict()
        )

@router.post("/match/cleanup", response_model=CleanupResultSuccessResponse, summary="清理匹配队列")
async def cleanup_match_queue(
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """清理匹配队列（管理员功能）"""
    try:
        APILogger.log_request(
            "清理匹配队列",
            管理员ID=current_user["id"]
        )
        
        match_service = MatchService(session)
        result = await match_service.cleanup_match_queue()
        
        if not result["success"]:
            APILogger.log_warning(
                "清理匹配队列",
                result["message"],
                管理员ID=current_user["id"]
            )
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse.create(
                    code=ResponseCode.SERVER_ERROR,
                    message=result["message"]
                ).dict()
            )
        
        APILogger.log_response(
            "清理匹配队列",
            管理员ID=current_user["id"]
        )
        
        return CleanupResultSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message=result["message"],
            data=CleanupResultResponse(
                cleaned_count=result.get("cleaned_count", 0)
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("清理匹配队列", e, 管理员ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"清理匹配队列失败: {str(e)}"
            ).dict()
        )

@router.post("/match/cleanup-expired", response_model=CleanupResultSuccessResponse, summary="清理过期匹配记录")
async def cleanup_expired_matches(
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """清理过期的匹配记录（管理员功能）"""
    try:
        APILogger.log_request(
            "清理过期匹配记录",
            管理员ID=current_user["id"]
        )
        
        match_service = MatchService(session)
        result = await match_service.cleanup_expired_matches()
        
        if not result["success"]:
            APILogger.log_warning(
                "清理过期匹配记录",
                result["message"],
                管理员ID=current_user["id"]
            )
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse.create(
                    code=ResponseCode.SERVER_ERROR,
                    message=result["message"]
                ).dict()
            )
        
        APILogger.log_response(
            "清理过期匹配记录",
            管理员ID=current_user["id"],
            清理数量=result.get("cleaned_count", 0)
        )
        
        return CleanupResultSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message=result["message"],
            data=CleanupResultResponse(
                cleaned_count=result.get("cleaned_count", 0)
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("清理过期匹配记录", e, 管理员ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"清理过期匹配记录失败: {str(e)}"
            ).dict()
        ) 