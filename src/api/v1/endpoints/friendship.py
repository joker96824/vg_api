from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.schemas.friendship import (
    FriendRequestCreate, FriendRequestResponse,
    FriendshipResponse, AcceptRequest, RejectRequest
)
from src.core.services.friendship import FriendshipService
from src.core.auth import get_current_user
from src.core.utils.logger import APILogger

router = APIRouter()

@router.post("/requests")
async def create_friend_request(
    request: FriendRequestCreate = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """发送好友请求"""
    try:
        APILogger.log_request(
            "发送好友请求",
            用户ID=current_user["id"],
            目标用户ID=str(request.target_user_id),
            请求内容=request.dict()
        )
        
        service = FriendshipService(db)
        await service.create_friend_request(request, current_user["id"])
        
        APILogger.log_response(
            "发送好友请求",
            用户ID=current_user["id"],
            操作结果="成功",
            目标用户ID=str(request.target_user_id)
        )
        
        return {"message": "好友请求已发送"}
    except ValueError as e:
        APILogger.log_warning(
            "发送好友请求",
            "请求失败",
            用户ID=current_user["id"],
            目标用户ID=str(request.target_user_id),
            错误信息=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        APILogger.log_error(
            "发送好友请求",
            e,
            用户ID=current_user["id"],
            目标用户ID=str(request.target_user_id)
        )
        raise HTTPException(status_code=500, detail=f"发送好友请求失败: {str(e)}")

@router.get("/requests", response_model=List[FriendRequestResponse])
async def get_friend_requests(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取好友请求列表"""
    try:
        APILogger.log_request(
            "获取好友请求列表",
            用户ID=current_user["id"]
        )
        
        service = FriendshipService(db)
        requests = await service.get_friend_requests(current_user["id"])
        
        APILogger.log_response(
            "获取好友请求列表",
            用户ID=current_user["id"],
            返回记录数=len(requests)
        )
        
        return requests
    except Exception as e:
        APILogger.log_error(
            "获取好友请求列表",
            e,
            用户ID=current_user["id"]
        )
        raise HTTPException(status_code=500, detail=f"获取好友请求列表失败: {str(e)}")

@router.put("/requests/accept")
async def accept_friend_request(
    request: AcceptRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """接受好友请求"""
    try:
        APILogger.log_request(
            "接受好友请求",
            用户ID=current_user["id"],
            请求ID=str(request.request_id)
        )
        
        service = FriendshipService(db)
        await service.accept_friend_request(request.request_id, current_user["id"])
        
        APILogger.log_response(
            "接受好友请求",
            用户ID=current_user["id"],
            操作结果="成功",
            请求ID=str(request.request_id)
        )
        
        return {"message": "已接受好友请求"}
    except ValueError as e:
        APILogger.log_warning(
            "接受好友请求",
            "请求失败",
            用户ID=current_user["id"],
            请求ID=str(request.request_id),
            错误信息=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        APILogger.log_error(
            "接受好友请求",
            e,
            用户ID=current_user["id"],
            请求ID=str(request.request_id)
        )
        raise HTTPException(status_code=500, detail=f"接受好友请求失败: {str(e)}")

@router.put("/requests/reject")
async def reject_friend_request(
    request: RejectRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """拒绝好友请求"""
    try:
        APILogger.log_request(
            "拒绝好友请求",
            用户ID=current_user["id"],
            请求ID=str(request.request_id)
        )
        
        service = FriendshipService(db)
        await service.reject_friend_request(request.request_id, current_user["id"])
        
        APILogger.log_response(
            "拒绝好友请求",
            用户ID=current_user["id"],
            操作结果="成功",
            请求ID=str(request.request_id)
        )
        
        return {"message": "已拒绝好友请求"}
    except ValueError as e:
        APILogger.log_warning(
            "拒绝好友请求",
            "请求失败",
            用户ID=current_user["id"],
            请求ID=str(request.request_id),
            错误信息=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        APILogger.log_error(
            "拒绝好友请求",
            e,
            用户ID=current_user["id"],
            请求ID=str(request.request_id)
        )
        raise HTTPException(status_code=500, detail=f"拒绝好友请求失败: {str(e)}")

@router.get("", response_model=List[FriendshipResponse])
async def get_friends(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取好友列表"""
    try:
        APILogger.log_request(
            "获取好友列表",
            用户ID=current_user["id"]
        )
        
        service = FriendshipService(db)
        friendships = await service.get_friends(current_user["id"])
        
        APILogger.log_response(
            "获取好友列表",
            用户ID=current_user["id"],
            返回记录数=len(friendships)
        )
        
        return friendships
    except Exception as e:
        APILogger.log_error(
            "获取好友列表",
            e,
            用户ID=current_user["id"]
        )
        raise HTTPException(status_code=500, detail=f"获取好友列表失败: {str(e)}")

@router.get("/blocked", response_model=List[FriendshipResponse])
async def get_blocked_friends(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取黑名单列表"""
    try:
        APILogger.log_request(
            "获取黑名单列表",
            用户ID=current_user["id"]
        )
        
        service = FriendshipService(db)
        friendships = await service.get_friends(current_user["id"], include_blocked=True)
        
        APILogger.log_response(
            "获取黑名单列表",
            用户ID=current_user["id"],
            返回记录数=len(friendships)
        )
        
        return friendships
    except Exception as e:
        APILogger.log_error(
            "获取黑名单列表",
            e,
            用户ID=current_user["id"]
        )
        raise HTTPException(status_code=500, detail=f"获取黑名单列表失败: {str(e)}")

@router.put("/{friendship_id}/block", response_model=FriendshipResponse)
async def block_friend(
    friendship_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """将好友拉入黑名单"""
    try:
        APILogger.log_request(
            "拉黑好友",
            用户ID=current_user["id"],
            好友关系ID=str(friendship_id)
        )
        
        service = FriendshipService(db)
        db_friendship = await service.update_friendship(
            friendship_id,
            current_user["id"],
            FriendshipUpdate(is_blocked=True)
        )
        
        if not db_friendship:
            APILogger.log_warning(
                "拉黑好友",
                "好友关系不存在",
                用户ID=current_user["id"],
                好友关系ID=str(friendship_id)
            )
            raise HTTPException(status_code=404, detail="好友关系不存在")
            
        APILogger.log_response(
            "拉黑好友",
            用户ID=current_user["id"],
            操作结果="成功",
            好友关系ID=str(friendship_id),
            好友ID=str(db_friendship.friend_id)
        )
        
        return db_friendship
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error(
            "拉黑好友",
            e,
            用户ID=current_user["id"],
            好友关系ID=str(friendship_id)
        )
        raise HTTPException(status_code=500, detail=f"拉黑好友失败: {str(e)}")

@router.delete("/{friendship_id}/block", response_model=FriendshipResponse)
async def unblock_friend(
    friendship_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """将好友移出黑名单"""
    try:
        APILogger.log_request(
            "取消拉黑好友",
            用户ID=current_user["id"],
            好友关系ID=str(friendship_id)
        )
        
        service = FriendshipService(db)
        db_friendship = await service.update_friendship(
            friendship_id,
            current_user["id"],
            FriendshipUpdate(is_blocked=False)
        )
        
        if not db_friendship:
            APILogger.log_warning(
                "取消拉黑好友",
                "好友关系不存在",
                用户ID=current_user["id"],
                好友关系ID=str(friendship_id)
            )
            raise HTTPException(status_code=404, detail="好友关系不存在")
            
        APILogger.log_response(
            "取消拉黑好友",
            用户ID=current_user["id"],
            操作结果="成功",
            好友关系ID=str(friendship_id),
            好友ID=str(db_friendship.friend_id)
        )
        
        return db_friendship
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error(
            "取消拉黑好友",
            e,
            用户ID=current_user["id"],
            好友关系ID=str(friendship_id)
        )
        raise HTTPException(status_code=500, detail=f"取消拉黑好友失败: {str(e)}")

@router.put("/{friendship_id}/remark", response_model=FriendshipResponse)
async def update_friend_remark(
    friendship_id: UUID,
    remark: str = Query(..., max_length=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """修改好友备注"""
    try:
        APILogger.log_request(
            "修改好友备注",
            用户ID=current_user["id"],
            好友关系ID=str(friendship_id),
            新备注=remark
        )
        
        service = FriendshipService(db)
        db_friendship = await service.update_friendship(
            friendship_id,
            current_user["id"],
            FriendshipUpdate(remark=remark)
        )
        
        if not db_friendship:
            APILogger.log_warning(
                "修改好友备注",
                "好友关系不存在",
                用户ID=current_user["id"],
                好友关系ID=str(friendship_id)
            )
            raise HTTPException(status_code=404, detail="好友关系不存在")
            
        APILogger.log_response(
            "修改好友备注",
            用户ID=current_user["id"],
            操作结果="成功",
            好友关系ID=str(friendship_id),
            好友ID=str(db_friendship.friend_id),
            新备注=remark
        )
        
        return db_friendship
    except HTTPException:
        raise
    except Exception as e:
        APILogger.log_error(
            "修改好友备注",
            e,
            用户ID=current_user["id"],
            好友关系ID=str(friendship_id)
        )
        raise HTTPException(status_code=500, detail=f"修改好友备注失败: {str(e)}")

@router.delete("/{friend_id}")
async def delete_friendship(
    friend_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """删除好友关系"""
    try:
        APILogger.log_request(
            "删除好友",
            用户ID=current_user["id"],
            好友ID=str(friend_id)
        )
        
        service = FriendshipService(db)
        await service.delete_friendship_by_friend_id(current_user["id"], friend_id)
        
        APILogger.log_response(
            "删除好友",
            用户ID=current_user["id"],
            操作结果="成功",
            好友ID=str(friend_id)
        )
        
        return {"message": "好友已删除"}
    except ValueError as e:
        APILogger.log_warning(
            "删除好友",
            "操作失败",
            用户ID=current_user["id"],
            好友ID=str(friend_id),
            错误信息=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        APILogger.log_error(
            "删除好友",
            e,
            用户ID=current_user["id"],
            好友ID=str(friend_id)
        )
        raise HTTPException(status_code=500, detail=f"删除好友失败: {str(e)}") 