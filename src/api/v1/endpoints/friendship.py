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

router = APIRouter()

@router.post("/requests")
async def create_friend_request(
    request: FriendRequestCreate = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """发送好友请求"""
    service = FriendshipService(db)
    try:
        await service.create_friend_request(request, current_user["id"])
        return {"message": "好友请求已发送"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求格式错误: {str(e)}")

@router.get("/requests", response_model=List[FriendRequestResponse])
async def get_friend_requests(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取好友请求列表"""
    service = FriendshipService(db)
    requests = await service.get_friend_requests(current_user["id"])
    return requests

@router.put("/requests/accept")
async def accept_friend_request(
    request: AcceptRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """接受好友请求"""
    service = FriendshipService(db)
    try:
        await service.accept_friend_request(request.request_id, current_user["id"])
        return {"message": "已接受好友请求"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/requests/reject")
async def reject_friend_request(
    request: RejectRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """拒绝好友请求"""
    service = FriendshipService(db)
    try:
        await service.reject_friend_request(request.request_id, current_user["id"])
        return {"message": "已拒绝好友请求"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[FriendshipResponse])
async def get_friends(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取好友列表"""
    service = FriendshipService(db)
    friendships = await service.get_friends(current_user["id"])
    return friendships

@router.get("/blocked", response_model=List[FriendshipResponse])
async def get_blocked_friends(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """获取黑名单列表"""
    service = FriendshipService(db)
    friendships = await service.get_friends(current_user["id"], include_blocked=True)
    return friendships

@router.put("/{friendship_id}/block", response_model=FriendshipResponse)
async def block_friend(
    friendship_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """将好友拉入黑名单"""
    service = FriendshipService(db)
    db_friendship = await service.update_friendship(
        friendship_id,
        current_user["id"],
        FriendshipUpdate(is_blocked=True)
    )
    if not db_friendship:
        raise HTTPException(status_code=404, detail="好友关系不存在")
    return db_friendship

@router.delete("/{friendship_id}/block", response_model=FriendshipResponse)
async def unblock_friend(
    friendship_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """将好友移出黑名单"""
    service = FriendshipService(db)
    db_friendship = await service.update_friendship(
        friendship_id,
        current_user["id"],
        FriendshipUpdate(is_blocked=False)
    )
    if not db_friendship:
        raise HTTPException(status_code=404, detail="好友关系不存在")
    return db_friendship

@router.put("/{friendship_id}/remark", response_model=FriendshipResponse)
async def update_friend_remark(
    friendship_id: UUID,
    remark: str = Query(..., max_length=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """修改好友备注"""
    service = FriendshipService(db)
    db_friendship = await service.update_friendship(
        friendship_id,
        current_user["id"],
        FriendshipUpdate(remark=remark)
    )
    if not db_friendship:
        raise HTTPException(status_code=404, detail="好友关系不存在")
    return db_friendship

@router.delete("/{friend_id}")
async def delete_friendship(
    friend_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """删除好友关系"""
    service = FriendshipService(db)
    try:
        await service.delete_friendship_by_friend_id(current_user["id"], friend_id)
        return {"message": "好友已删除"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) 