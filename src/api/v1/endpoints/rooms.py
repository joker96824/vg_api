from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from src.core.deps import get_db
from src.core.schemas.room import (
    RoomCreate, RoomUpdate, RoomInDB, 
    RoomPlayerCreate, RoomPlayerUpdate,
    RoomQueryParams, RoomPlayerQueryParams,
    RoomSuccessResponse, RoomListSuccessResponse,
    RoomPlayerSuccessResponse, RoomPlayerListSuccessResponse,
    RoomPlayersSuccessResponse, UserRoomStatusSuccessResponse,
    DeleteSuccessResponse, DeleteResponse,
    ResponseCode, ErrorResponse, RoomCreateRequest,
    KickPlayerRequest
)
from src.core.services.room import RoomService, RoomPlayerService
from src.core.auth import get_current_user
from src.core.utils.logger import APILogger
from pydantic import BaseModel, Field
from src.core.models.room import Room

router = APIRouter()

# 加入房间请求模型
class JoinRoomRequest(BaseModel):
    pass_word: str = None

# 改变玩家状态请求模型
class ChangePlayerStatusRequest(BaseModel):
    status: str = Field(..., description="玩家状态：waiting-等待, ready-准备")


@router.post("/rooms", response_model=RoomSuccessResponse, summary="创建房间")
async def create_room(
    room_request: RoomCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """创建新房间"""
    try:
        APILogger.log_request(
            "创建房间",
            用户ID=current_user["id"],
            房间信息=room_request.dict()
        )
        
        # 创建房间配置
        room_data = RoomCreate(
            room_name=room_request.room_name,
            room_type=room_request.room_type,
            status="waiting",
            max_players=2,
            current_players=0,
            game_mode="standard",
            game_settings=room_request.game_settings,
            pass_word=room_request.pass_word,
            remark=room_request.remark
        )
        
        room_service = RoomService(session)
        result = await room_service.create_room(room_data, current_user["id"])
        
        APILogger.log_response(
            "创建房间",
            房间ID=str(result.id),
            房间名称=result.room_name
        )
        
        return RoomSuccessResponse.create(
            code=ResponseCode.CREATE_SUCCESS,
            message="房间创建成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("创建房间", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"创建房间失败: {str(e)}"
            ).dict()
        )


@router.get("/rooms", response_model=RoomListSuccessResponse, summary="获取房间列表")
async def get_rooms(
    key_word: str = Query(None, description="房间名称关键词，支持模糊匹配"),
    friend_room: bool = Query(False, description="是否只显示好友的房间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取房间列表"""
    try:
        params = RoomQueryParams(
            key_word=key_word,
            friend_room=friend_room,
            page=page,
            page_size=page_size
        )
        
        APILogger.log_request(
            "获取房间列表",
            用户ID=current_user["id"],
            查询参数=params.dict()
        )
        
        room_service = RoomService(session)
        total, rooms = await room_service.get_rooms(params, current_user["id"])
        
        APILogger.log_response(
            "获取房间列表",
            总记录数=total,
            返回记录数=len(rooms)
        )
        
        return RoomListSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取房间列表成功",
            data={
                "total": total,
                "items": rooms
            }
        )
    except Exception as e:
        APILogger.log_error("获取房间列表", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取房间列表失败: {str(e)}"
            ).dict()
        )


@router.get("/rooms/my-status", response_model=UserRoomStatusSuccessResponse, summary="检查用户房间状态")
async def check_user_room_status(
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """检查当前用户是否在房间中且未删除"""
    try:
        APILogger.log_request(
            "检查用户房间状态",
            用户ID=current_user["id"]
        )
        
        room_service = RoomService(session)
        result = await room_service.check_user_room_status(current_user["id"])
        
        APILogger.log_response(
            "检查用户房间状态",
            用户ID=current_user["id"],
            是否在房间中=result["in_room"],
            房间ID=result.get("room_id"),
            房间名称=result.get("room_name")
        )
        
        return UserRoomStatusSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="检查用户房间状态成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("检查用户房间状态", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"检查用户房间状态失败: {str(e)}"
            ).dict()
        )


@router.get("/rooms/{room_id}", response_model=RoomSuccessResponse, summary="获取房间详情")
async def get_room(
    room_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取指定房间的详细信息"""
    try:
        APILogger.log_request(
            "获取房间详情",
            用户ID=current_user["id"],
            房间ID=str(room_id)
        )
        
        room_service = RoomService(session)
        room = await room_service.get_room(room_id)
        
        if not room:
            APILogger.log_warning(
                "获取房间详情",
                "未找到房间",
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="房间不存在"
                ).dict()
            )
            
        APILogger.log_response(
            "获取房间详情",
            房间ID=str(room.id),
            房间名称=room.room_name
        )
        
        return RoomSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取房间详情成功",
            data=room
        )
    except Exception as e:
        APILogger.log_error("获取房间详情", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取房间详情失败: {str(e)}"
            ).dict()
        )


@router.put("/rooms/{room_id}", response_model=RoomSuccessResponse, summary="更新房间")
async def update_room(
    room_id: UUID,
    room: RoomUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """更新指定房间的信息"""
    try:
        APILogger.log_request(
            "更新房间",
            用户ID=current_user["id"],
            房间ID=str(room_id),
            更新信息=room.dict()
        )
        
        room_service = RoomService(session)
        # 先获取房间信息
        existing_room = await room_service.get_room(room_id)
        if not existing_room:
            APILogger.log_warning(
                "更新房间",
                "房间不存在",
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="房间不存在"
                ).dict()
            )
            
        # 验证是否是房间创建者
        if str(existing_room.created_by) != current_user["id"]:
            APILogger.log_warning(
                "更新房间",
                "无权更新房间",
                用户ID=current_user["id"],
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权更新此房间"
                ).dict()
            )
            
        result = await room_service.update_room(room_id, room)
        
        APILogger.log_response(
            "更新房间",
            房间ID=str(result.id),
            房间名称=result.room_name
        )
        
        return RoomSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="房间更新成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("更新房间", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"更新房间失败: {str(e)}"
            ).dict()
        )


@router.delete("/rooms/{room_id}", response_model=DeleteSuccessResponse, summary="删除房间")
async def delete_room(
    room_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """删除指定房间"""
    try:
        APILogger.log_request(
            "删除房间",
            用户ID=current_user["id"],
            房间ID=str(room_id)
        )
        
        room_service = RoomService(session)
        # 先获取房间信息
        existing_room = await room_service.get_room(room_id)
        if not existing_room:
            APILogger.log_warning(
                "删除房间",
                "房间不存在",
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="房间不存在"
                ).dict()
            )
            
        # 验证是否是房间创建者
        if str(existing_room.created_by) != current_user["id"]:
            APILogger.log_warning(
                "删除房间",
                "无权删除房间",
                用户ID=current_user["id"],
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="无权删除此房间"
                ).dict()
            )
            
        success = await room_service.delete_room(room_id)
        
        if not success:
            APILogger.log_warning(
                "删除房间",
                "删除失败",
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse.create(
                    code=ResponseCode.SERVER_ERROR,
                    message="删除房间失败"
                ).dict()
            )
            
        APILogger.log_response(
            "删除房间",
            房间ID=str(room_id)
        )
        
        return DeleteSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="房间删除成功",
            data=DeleteResponse()
        )
    except Exception as e:
        APILogger.log_error("删除房间", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"删除房间失败: {str(e)}"
            ).dict()
        )


@router.post("/rooms/{room_id}/join", response_model=RoomPlayerSuccessResponse, summary="加入房间")
async def join_room(
    room_id: UUID,
    room_request: JoinRoomRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """加入指定房间"""
    try:
        APILogger.log_request(
            "加入房间",
            用户ID=current_user["id"],
            房间ID=str(room_id),
            是否提供密码=room_request.pass_word is not None
        )
        
        room_service = RoomService(session)
        result = await room_service.join_room(room_id, current_user["id"], room_request.pass_word)
        
        if not result:
            APILogger.log_warning(
                "加入房间",
                "加入失败",
                房间ID=str(room_id),
                用户ID=current_user["id"]
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message="加入房间失败"
                ).dict()
            )
            
        APILogger.log_response(
            "加入房间",
            房间ID=str(room_id),
            用户ID=current_user["id"],
            玩家顺序=result.player_order
        )
        
        return RoomPlayerSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="加入房间成功",
            data=result
        )
    except ValueError as e:
        APILogger.log_warning(
            "加入房间",
            str(e),
            房间ID=str(room_id),
            用户ID=current_user["id"]
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )
    except Exception as e:
        APILogger.log_error("加入房间", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"加入房间失败: {str(e)}"
            ).dict()
        )


@router.post("/rooms/{room_id}/leave", response_model=DeleteSuccessResponse, summary="离开房间")
async def leave_room(
    room_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """离开指定房间"""
    try:
        APILogger.log_request(
            "离开房间",
            用户ID=current_user["id"],
            房间ID=str(room_id)
        )
        
        room_service = RoomService(session)
        success = await room_service.leave_room(room_id, current_user["id"])
        
        if not success:
            APILogger.log_warning(
                "离开房间",
                "离开失败",
                房间ID=str(room_id),
                用户ID=current_user["id"]
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message="离开房间失败"
                ).dict()
            )
            
        APILogger.log_response(
            "离开房间",
            房间ID=str(room_id),
            用户ID=current_user["id"]
        )
        
        return DeleteSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="离开房间成功",
            data=DeleteResponse()
        )
    except Exception as e:
        APILogger.log_error("离开房间", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"离开房间失败: {str(e)}"
            ).dict()
        )


@router.post("/rooms/{room_id}/kick", response_model=DeleteSuccessResponse, summary="踢出房间玩家")
async def kick_player(
    room_id: UUID,
    kick_request: KickPlayerRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """踢出房间玩家（仅房主可操作）"""
    try:
        APILogger.log_request(
            "踢出房间玩家",
            房主ID=current_user["id"],
            房间ID=str(room_id),
            目标用户ID=str(kick_request.target_user_id)
        )
        
        room_service = RoomService(session)
        result = await room_service.kick_player(room_id, current_user["id"], kick_request.target_user_id)
        
        if not result:
            APILogger.log_warning(
                "踢出房间玩家",
                "踢出失败",
                房主ID=current_user["id"],
                房间ID=str(room_id),
                目标用户ID=str(kick_request.target_user_id)
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message="踢出玩家失败"
                ).dict()
            )
        
        APILogger.log_response(
            "踢出房间玩家",
            房主ID=current_user["id"],
            房间ID=str(room_id),
            目标用户ID=str(kick_request.target_user_id)
        )
        
        return DeleteSuccessResponse.create(
            code=ResponseCode.DELETE_SUCCESS,
            message="踢出玩家成功",
            data=DeleteResponse()
        )
    except HTTPException:
        raise
    except ValueError as e:
        APILogger.log_error("踢出房间玩家", e, 房主ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )
    except Exception as e:
        APILogger.log_error("踢出房间玩家", e, 房主ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"踢出玩家失败: {str(e)}"
            ).dict()
        )


@router.put("/rooms/{room_id}/player/status", response_model=RoomPlayerSuccessResponse, summary="改变房间玩家状态")
async def change_player_status(
    room_id: UUID,
    status_request: ChangePlayerStatusRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """改变房间玩家状态（waiting/ready）"""
    try:
        APILogger.log_request(
            "改变玩家状态",
            用户ID=current_user["id"],
            房间ID=str(room_id),
            新状态=status_request.status
        )
        
        room_service = RoomService(session)
        result = await room_service.change_player_status(room_id, current_user["id"], status_request.status)
        
        if not result:
            APILogger.log_warning(
                "改变玩家状态",
                "改变失败",
                房间ID=str(room_id),
                用户ID=current_user["id"]
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message="改变玩家状态失败"
                ).dict()
            )
        
        APILogger.log_response(
            "改变玩家状态",
            房间ID=str(room_id),
            用户ID=current_user["id"],
            新状态=status_request.status
        )
        
        return RoomPlayerSuccessResponse.create(
            code=ResponseCode.UPDATE_SUCCESS,
            message="改变玩家状态成功",
            data=result
        )
    except ValueError as e:
        APILogger.log_warning(
            "改变玩家状态",
            str(e),
            房间ID=str(room_id),
            用户ID=current_user["id"]
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )
    except Exception as e:
        APILogger.log_error("改变玩家状态", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"改变玩家状态失败: {str(e)}"
            ).dict()
        )


@router.get("/rooms/{room_id}/players", response_model=RoomPlayersSuccessResponse, summary="获取房间玩家信息")
async def get_room_players(
    room_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取指定房间的玩家详细信息"""
    try:
        APILogger.log_request(
            "获取房间玩家信息",
            用户ID=current_user["id"],
            房间ID=str(room_id)
        )
        
        room_service = RoomService(session)
        result = await room_service.get_room_players_info(room_id)
        
        if not result:
            APILogger.log_warning(
                "获取房间玩家信息",
                "房间不存在",
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="房间不存在"
                ).dict()
            )
            
        APILogger.log_response(
            "获取房间玩家信息",
            房间ID=str(room_id),
            房间名称=result["room_name"],
            玩家数量=result["total_players"]
        )
        
        return RoomPlayersSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取房间玩家信息成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("获取房间玩家信息", e, 用户ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取房间玩家信息失败: {str(e)}"
            ).dict()
        )


@router.post("/rooms/{room_id}/loading", response_model=DeleteSuccessResponse, summary="开始游戏加载")
async def start_game_loading(
    room_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """开始游戏加载（仅房主可操作）"""
    try:
        APILogger.log_request(
            "开始游戏加载",
            房主ID=current_user["id"],
            房间ID=str(room_id)
        )
        
        room_service = RoomService(session)
        result = await room_service.start_game_loading(room_id, current_user["id"])
        
        if not result:
            APILogger.log_warning(
                "开始游戏加载",
                "开始失败",
                房主ID=current_user["id"],
                房间ID=str(room_id)
            )
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message="开始游戏加载失败"
                ).dict()
            )
        
        APILogger.log_response(
            "开始游戏加载",
            房主ID=current_user["id"],
            房间ID=str(room_id)
        )
        
        return DeleteSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="游戏加载开始成功",
            data=DeleteResponse()
        )
    except ValueError as e:
        APILogger.log_warning(
            "开始游戏加载",
            str(e),
            房主ID=current_user["id"],
            房间ID=str(room_id)
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )
    except Exception as e:
        APILogger.log_error("开始游戏加载", e, 房主ID=current_user["id"], 房间ID=str(room_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"开始游戏加载失败: {str(e)}"
            ).dict()
        ) 