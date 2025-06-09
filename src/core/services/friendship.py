from datetime import datetime
from typing import List, Optional
from uuid import UUID
import logging

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.models.friendship import Friendship, FriendRequest
from src.core.models.user import User
from src.core.schemas.friendship import (
    FriendRequestCreate,
    FriendshipCreate, FriendshipUpdate
)

logger = logging.getLogger(__name__)

class FriendshipService:
    """好友关系服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_friend_request(self, request: FriendRequestCreate, sender_id: UUID) -> None:
        """创建好友请求"""
        # 检查是否已经是好友
        existing_friendship = await self.db.execute(
            select(Friendship).where(
                and_(
                    Friendship.user_id == sender_id,
                    Friendship.friend_id == request.receiver_id,
                    Friendship.is_deleted == False
                )
            )
        )
        if existing_friendship.scalar_one_or_none():
            raise ValueError("已经是好友关系")

        # 检查是否有待处理的请求
        existing_request = await self.db.execute(
            select(FriendRequest).where(
                and_(
                    FriendRequest.sender_id == sender_id,
                    FriendRequest.receiver_id == request.receiver_id,
                    FriendRequest.status == "pending",
                    FriendRequest.is_deleted == False
                )
            )
        )
        if existing_request.scalar_one_or_none():
            raise ValueError("已存在待处理的好友请求")

        # 获取发送者和接收者信息
        sender = await self.db.execute(
            select(User).where(User.id == sender_id)
        )
        sender = sender.scalar_one_or_none()
        if not sender:
            raise ValueError("发送者不存在")

        receiver = await self.db.execute(
            select(User).where(User.id == request.receiver_id)
        )
        receiver = receiver.scalar_one_or_none()
        if not receiver:
            raise ValueError("接收者不存在")

        # 创建新请求
        db_request = FriendRequest(
            sender_id=sender_id,
            receiver_id=request.receiver_id,
            message=request.message,
            status="pending",
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        self.db.add(db_request)
        await self.db.commit()

    async def get_friend_requests(self, user_id: UUID) -> List[FriendRequest]:
        """获取好友请求列表"""
        # 构建查询条件
        conditions = [
            FriendRequest.receiver_id == user_id,
            FriendRequest.status == "pending",  # 只获取待处理的请求
            FriendRequest.is_deleted == False
        ]

        # 获取数据
        result = await self.db.execute(
            select(FriendRequest)
            .where(and_(*conditions))
            .order_by(desc(FriendRequest.create_time))
        )
        requests = result.scalars().all()

        # 获取所有相关的用户ID
        user_ids = set()
        for request in requests:
            user_ids.add(request.sender_id)
            user_ids.add(request.receiver_id)

        # 批量获取用户信息
        users_result = await self.db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = {str(user.id): user for user in users_result.scalars().all()}

        # 添加昵称信息
        for request in requests:
            sender = users.get(str(request.sender_id))
            receiver = users.get(str(request.receiver_id))
            if sender:
                request.sender_nickname = sender.nickname
            if receiver:
                request.receiver_nickname = receiver.nickname

        return requests

    async def accept_friend_request(self, request_id: UUID, user_id: UUID) -> None:
        """接受好友请求"""
        # 获取请求
        result = await self.db.execute(
            select(FriendRequest).where(
                and_(
                    FriendRequest.id == request_id,
                    FriendRequest.receiver_id == user_id,
                    FriendRequest.status == "pending",
                    FriendRequest.is_deleted == False
                )
            )
        )
        db_request = result.scalar_one_or_none()
        if not db_request:
            raise ValueError("好友请求不存在或已被处理")

        # 更新状态
        db_request.status = "accepted"
        db_request.is_deleted = True  # 标记为已删除
        db_request.update_time = datetime.now()

        # 创建双向好友关系
        friendship1 = Friendship(
            user_id=db_request.sender_id,
            friend_id=db_request.receiver_id,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        friendship2 = Friendship(
            user_id=db_request.receiver_id,
            friend_id=db_request.sender_id,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        self.db.add_all([friendship1, friendship2])

        await self.db.commit()

    async def reject_friend_request(self, request_id: UUID, user_id: UUID) -> None:
        """拒绝好友请求"""
        # 获取请求
        result = await self.db.execute(
            select(FriendRequest).where(
                and_(
                    FriendRequest.id == request_id,
                    FriendRequest.receiver_id == user_id,
                    FriendRequest.status == "pending",
                    FriendRequest.is_deleted == False
                )
            )
        )
        db_request = result.scalar_one_or_none()
        if not db_request:
            raise ValueError("好友请求不存在或已被处理")

        # 更新状态
        db_request.status = "rejected"
        db_request.is_deleted = True  # 标记为已删除
        db_request.update_time = datetime.now()
        await self.db.commit()

    async def delete_friend_request(self, request_id: UUID, user_id: UUID) -> bool:
        """删除好友请求"""
        result = await self.db.execute(
            select(FriendRequest).where(
                and_(
                    FriendRequest.id == request_id,
                    or_(
                        FriendRequest.sender_id == user_id,
                        FriendRequest.receiver_id == user_id
                    ),
                    FriendRequest.is_deleted == False
                )
            )
        )
        db_request = result.scalar_one_or_none()
        if not db_request:
            return False

        db_request.is_deleted = True
        db_request.update_time = datetime.now()
        await self.db.commit()
        return True

    async def get_friends(self, user_id: UUID, include_blocked: bool = False) -> List[Friendship]:
        """获取好友列表"""
        # 构建查询条件
        conditions = [
            Friendship.user_id == user_id,
            Friendship.is_deleted == False
        ]
        if not include_blocked:
            conditions.append(Friendship.is_blocked == False)

        # 获取数据
        result = await self.db.execute(
            select(Friendship)
            .where(and_(*conditions))
            .order_by(desc(Friendship.update_time))
        )
        friendships = result.scalars().all()

        # 获取所有好友的ID
        friend_ids = [friendship.friend_id for friendship in friendships]

        # 批量获取好友信息
        users_result = await self.db.execute(
            select(User).where(User.id.in_(friend_ids))
        )
        users = {str(user.id): user for user in users_result.scalars().all()}

        # 添加好友昵称和头像信息
        for friendship in friendships:
            friend = users.get(str(friendship.friend_id))
            if friend:
                friendship.friend_nickname = friend.nickname
                friendship.friend_avatar = friend.avatar

        return friendships

    async def update_friendship(
        self, friendship_id: UUID, user_id: UUID, update: FriendshipUpdate
    ) -> Optional[Friendship]:
        """更新好友关系"""
        result = await self.db.execute(
            select(Friendship).where(
                and_(
                    Friendship.id == friendship_id,
                    Friendship.user_id == user_id,
                    Friendship.is_deleted == False
                )
            )
        )
        db_friendship = result.scalar_one_or_none()
        if not db_friendship:
            return None

        # 更新字段
        if update.remark is not None:
            db_friendship.remark = update.remark
        if update.is_blocked is not None:
            db_friendship.is_blocked = update.is_blocked

        db_friendship.update_time = datetime.now()
        await self.db.commit()
        await self.db.refresh(db_friendship)
        return db_friendship

    async def delete_friendship(self, friendship_id: UUID, user_id: UUID) -> bool:
        """删除好友关系"""
        result = await self.db.execute(
            select(Friendship).where(
                and_(
                    Friendship.id == friendship_id,
                    Friendship.user_id == user_id,
                    Friendship.is_deleted == False
                )
            )
        )
        db_friendship = result.scalar_one_or_none()
        if not db_friendship:
            return False

        db_friendship.is_deleted = True
        db_friendship.update_time = datetime.now()
        await self.db.commit()
        return True

    async def delete_friendship_by_friend_id(self, user_id: UUID, friend_id: UUID) -> None:
        """根据好友ID删除好友关系（双向删除）"""
        # 查找当前用户到好友的关系
        result1 = await self.db.execute(
            select(Friendship).where(
                and_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id == friend_id,
                    Friendship.is_deleted == False
                )
            )
        )
        friendship1 = result1.scalar_one_or_none()
        if not friendship1:
            raise ValueError("好友关系不存在")

        # 查找好友到当前用户的关系
        result2 = await self.db.execute(
            select(Friendship).where(
                and_(
                    Friendship.user_id == friend_id,
                    Friendship.friend_id == user_id,
                    Friendship.is_deleted == False
                )
            )
        )
        friendship2 = result2.scalar_one_or_none()
        if not friendship2:
            raise ValueError("好友关系不完整")

        # 标记两条关系为已删除
        friendship1.is_deleted = True
        friendship1.update_time = datetime.now()
        friendship2.is_deleted = True
        friendship2.update_time = datetime.now()

        await self.db.commit()

    async def search_users(self, keyword: str, user_id: UUID) -> List[User]:
        """搜索用户"""
        try:
            # 尝试将关键词转换为UUID
            keyword_uuid = UUID(keyword)
            uuid_match = User.id == keyword_uuid
        except ValueError:
            # 如果转换失败，则不添加UUID匹配条件
            uuid_match = False

        # 构建查询条件
        conditions = [
            or_(
                User.email.ilike(f"%{keyword}%"),
                User.nickname.ilike(f"%{keyword}%"),
                uuid_match
            ),
            User.is_deleted == False,
            User.id != user_id
        ]

        # 获取数据
        result = await self.db.execute(
            select(User)
            .where(and_(*conditions))
            .order_by(desc(User.create_time))
        )
        users = result.scalars().all()
        
        # 将UUID转换为字符串
        for user in users:
            user.id = str(user.id)
            
        return users 