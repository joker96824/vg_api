from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.services.battle import BattleService
from src.core.schemas.response import SuccessResponse, ErrorResponse, ResponseCode
from src.core.auth import get_current_user
from src.core.utils.logger import APILogger
from src.core.services.room import RoomService

router = APIRouter()


@router.post("/battles/current/state", summary="查询当前用户对战游戏状态")
async def query_current_battle_state(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """查询当前用户的对战游戏状态（自动获取当前对战）"""
    try:
        APILogger.log_request(
            "查询当前用户对战游戏状态",
            用户ID=current_user["id"]
        )
        
        battle_service = BattleService(session)
        
        # 获取用户当前对战
        current_battle = await battle_service.get_current_battle_by_user(UUID(current_user["id"]))
        
        if not current_battle:
            # 检查用户是否在房间中
            room_service = RoomService(session)
            room_status = await room_service.check_user_room_status(UUID(current_user["id"]))
            
            if room_status["in_room"]:
                # 用户在房间中但没有进行中的对战
                APILogger.log_warning(
                    "查询当前用户对战游戏状态",
                    "用户在房间中但没有进行中的对战",
                    用户ID=current_user["id"],
                    房间ID=room_status["room_id"],
                    房间状态=room_status["status"]
                )
                raise HTTPException(
                    status_code=404,
                    detail=ErrorResponse.create(
                        code=ResponseCode.NOT_FOUND,
                        message=f"您在房间中但游戏尚未开始或已结束（房间状态：{room_status['status']}）"
                    ).dict()
                )
            else:
                # 用户不在任何房间中
                APILogger.log_warning(
                    "查询当前用户对战游戏状态",
                    "用户没有进行中的对战",
                    用户ID=current_user["id"]
                )
                raise HTTPException(
                    status_code=404,
                    detail=ErrorResponse.create(
                        code=ResponseCode.NOT_FOUND,
                        message="您当前没有进行中的对战"
                    ).dict()
                )
        
        # 获取游戏状态
        game_state = await battle_service.get_game_state(current_battle.id)
        
        if not game_state:
            APILogger.log_warning(
                "查询当前用户对战游戏状态",
                "游戏状态不存在",
                用户ID=current_user["id"],
                对战ID=str(current_battle.id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="游戏状态不存在"
                ).dict()
            )
        
        # 验证用户是否在对战中
        player1_id = game_state.get("player1_id")
        player2_id = game_state.get("player2_id")
        current_user_id = str(current_user["id"])
        
        if current_user_id not in [player1_id, player2_id]:
            APILogger.log_warning(
                "查询当前用户对战游戏状态",
                "用户不在对战中",
                用户ID=current_user["id"],
                对战ID=str(current_battle.id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.PERMISSION_DENIED,
                    message="您不在此对战中"
                ).dict()
            )
        
        # 暂时发送全部游戏状态内容
        # 后续可以根据用户身份处理数据（如隐藏对手卡牌信息等）
        
        APILogger.log_response(
            "查询当前用户对战游戏状态",
            用户ID=current_user["id"],
            对战ID=str(current_battle.id)
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="查询游戏状态成功",
            data={
                "battle_id": str(current_battle.id),
                "room_id": str(current_battle.room_id),
                "battle_type": current_battle.battle_type,
                "status": current_battle.status,
                "game_state": game_state
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("查询当前用户对战游戏状态", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"查询游戏状态失败: {str(e)}"
            ).dict()
        )


@router.post("/battles/{battle_id}/state", summary="查询对战游戏状态")
async def query_battle_state(
    battle_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """查询对战游戏状态（根据当前用户返回相应的状态）"""
    try:
        APILogger.log_request(
            "查询对战游戏状态",
            用户ID=current_user["id"],
            对战ID=str(battle_id)
        )
        
        battle_service = BattleService(session)
        
        # 获取游戏状态
        game_state = await battle_service.get_game_state(battle_id)
        
        if not game_state:
            APILogger.log_warning(
                "查询对战游戏状态",
                "游戏状态不存在",
                用户ID=current_user["id"],
                对战ID=str(battle_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="游戏状态不存在"
                ).dict()
            )
        
        # 验证用户是否在对战中
        player1_id = game_state.get("player1_id")
        player2_id = game_state.get("player2_id")
        current_user_id = str(current_user["id"])
        
        if current_user_id not in [player1_id, player2_id]:
            APILogger.log_warning(
                "查询对战游戏状态",
                "用户不在对战中",
                用户ID=current_user["id"],
                对战ID=str(battle_id)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.PERMISSION_DENIED,
                    message="您不在此对战中"
                ).dict()
            )
        
        # 暂时发送全部游戏状态内容
        # 后续可以根据用户身份处理数据（如隐藏对手卡牌信息等）
        
        APILogger.log_response(
            "查询对战游戏状态",
            用户ID=current_user["id"],
            对战ID=str(battle_id)
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="查询游戏状态成功",
            data=game_state
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("查询对战游戏状态", e, 用户ID=current_user["id"], 对战ID=str(battle_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"查询游戏状态失败: {str(e)}"
            ).dict()
        )


@router.get("/battles/{battle_id}", summary="获取对战详情")
async def get_battle(
    battle_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """获取对战详情"""
    try:
        APILogger.log_request(
            "获取对战详情",
            用户ID=current_user["id"],
            对战ID=str(battle_id)
        )
        
        battle_service = BattleService(session)
        battle = await battle_service.get_battle(battle_id)
        
        if not battle:
            APILogger.log_warning(
                "获取对战详情",
                "对战不存在",
                用户ID=current_user["id"],
                对战ID=str(battle_id)
            )
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="对战不存在"
                ).dict()
            )
        
        APILogger.log_response(
            "获取对战详情",
            用户ID=current_user["id"],
            对战ID=str(battle_id)
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取对战详情成功",
            data={
                "id": str(battle.id),
                "room_id": str(battle.room_id),
                "battle_type": battle.battle_type,
                "status": battle.status,
                "start_time": battle.start_time.isoformat() if battle.start_time else None,
                "end_time": battle.end_time.isoformat() if battle.end_time else None,
                "duration_seconds": battle.duration_seconds,
                "winner_id": str(battle.winner_id) if battle.winner_id else None,
                "create_time": battle.create_time.isoformat(),
                "update_time": battle.update_time.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("获取对战详情", e, 用户ID=current_user["id"], 对战ID=str(battle_id))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取对战详情失败: {str(e)}"
            ).dict()
        ) 