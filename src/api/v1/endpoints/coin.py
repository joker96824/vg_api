from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from src.core.redis import get_redis_client
from src.core.services.battle import BattleService
from src.core.database import get_session
from src.core.auth import get_current_user
from src.core.schemas.response import SuccessResponse, ErrorResponse, ResponseCode
from src.core.utils.logger import APILogger
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

class CoinChoiceRequest(BaseModel):
    choice: int

class FirstPlayerRequest(BaseModel):
    first: bool  # True表示胜方先攻，False表示胜方后攻

@router.post("/select")
async def make_coin_choice(
    request: CoinChoiceRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """用户做出猜拳选择"""
    try:
        APILogger.log_request(
            "猜拳选择",
            用户ID=current_user["id"],
            选择=request.choice
        )
        
        # 获取Redis客户端
        redis_client = get_redis_client()
        
        # 创建对战服务
        battle_service = BattleService(session)
        
        # 获取用户当前对战
        battle = await battle_service.get_current_battle_by_user(UUID(current_user["id"]))
        if not battle:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="您当前没有进行中的对战"
                ).dict()
            )
        
        # 检查对战状态
        if battle.status != "coin":
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_STATE,
                    message="当前不在猜拳阶段"
                ).dict()
            )
        
        # 执行选择
        result = await battle_service.make_coin_choice(
            battle.room_id, 
            UUID(current_user["id"]), 
            request.choice, 
            redis_client
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_OPERATION,
                    message=result.get('error', '猜拳选择失败')
                ).dict()
            )
        
        APILogger.log_response(
            "猜拳选择",
            用户ID=current_user["id"],
            对战ID=str(battle.id),
            选择=request.choice,
            结果=result.get("message", "选择成功")
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message=result["message"],
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("猜拳选择", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"猜拳选择失败: {str(e)}"
            ).dict()
        )

@router.post("/first_player")
async def choose_first_player(
    request: FirstPlayerRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """胜方选择先攻后攻"""
    try:
        APILogger.log_request(
            "胜方选择先攻后攻",
            用户ID=current_user["id"],
            选择=request.first
        )
        
        # 获取Redis客户端
        redis_client = get_redis_client()
        
        # 创建对战服务
        battle_service = BattleService(session)
        
        # 获取用户当前对战
        battle = await battle_service.get_current_battle_by_user(UUID(current_user["id"]))
        if not battle:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="您当前没有进行中的对战"
                ).dict()
            )
        
        # 检查对战状态
        if battle.status != "coin":
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_STATE,
                    message="当前不在猜拳阶段"
                ).dict()
            )
        
        # 检查双方是否都已选择
        coin_game_manager = battle_service.coin_game_manager
        if not coin_game_manager:
            # 初始化猜拳管理器
            battle_service._init_coin_managers(redis_client)
            coin_game_manager = battle_service.coin_game_manager
        
        # 获取房间信息
        from src.core.models.room import Room
        from sqlalchemy import select
        room_result = await session.execute(
            select(Room).where(Room.id == battle.room_id)
        )
        room = room_result.scalar_one_or_none()
        if not room:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse.create(
                    code=ResponseCode.NOT_FOUND,
                    message="房间不存在"
                ).dict()
            )
        
        # 获取房间玩家
        from src.core.models.room_player import RoomPlayer
        from sqlalchemy import and_
        players_result = await session.execute(
            select(RoomPlayer)
            .where(
                and_(
                    RoomPlayer.room_id == battle.room_id,
                    RoomPlayer.is_deleted == False
                )
            )
            .order_by(RoomPlayer.player_order)
        )
        room_players = players_result.scalars().all()
        
        if len(room_players) != 2:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_PARAMETER,
                    message="房间玩家数量不正确"
                ).dict()
            )
        
        # 检查双方是否都已选择
        owner_id = room.created_by
        guest_id = None
        for player in room_players:
            if str(room.created_by) != str(player.user_id):
                guest_id = player.user_id
                break
        
        if not guest_id:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_PARAMETER,
                    message="无法确定非房主玩家"
                ).dict()
            )
        
        owner_choice = await coin_game_manager.get_user_choice(battle.room_id, owner_id)
        guest_choice = await coin_game_manager.get_user_choice(battle.room_id, guest_id)
        
        if not owner_choice or not guest_choice:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_STATE,
                    message="双方尚未完成选择"
                ).dict()
            )
        
        # 确定胜者
        mapping = await coin_game_manager.get_mapping(battle.room_id)
        if not mapping:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse.create(
                    code=ResponseCode.INVALID_STATE,
                    message="猜拳映射不存在"
                ).dict()
            )
        
        winner, loser, _ = coin_game_manager._determine_winner(owner_choice, guest_choice, mapping)
        winner_id = owner_id if winner == "owner" else guest_id
        loser_id = guest_id if winner == "owner" else owner_id
        
        # 检查调用者是否为胜者
        if str(winner_id) != current_user["id"]:
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.PERMISSION_DENIED,
                    message="只有胜者可以选择先攻后攻"
                ).dict()
            )
        
        # 确定先攻玩家
        first_player = winner_id if request.first else loser_id
        
        # 更新对战状态
        await battle_service._update_battle_after_coin(battle.room_id, winner_id, first_player)
        
        # 取消超时任务
        await battle_service.coin_timeout_manager.cancel_first_player_timeout(battle.room_id)
        
        APILogger.log_response(
            "胜方选择先攻后攻",
            用户ID=current_user["id"],
            对战ID=str(battle.id),
            选择=request.first,
            先攻玩家=str(first_player)
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="先攻后攻选择成功",
            data={
                "first_player": str(first_player),
                "winner": str(winner_id),
                "first": request.first
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error("胜方选择先攻后攻", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"胜方选择先攻后攻失败: {str(e)}"
            ).dict()
        ) 