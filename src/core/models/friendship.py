from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.database import Base

class Friendship(Base):
    """好友关系模型"""
    __tablename__ = "friendships"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"))
    friend_id: Mapped[UUID] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    remark: Mapped[str | None] = mapped_column(String(50))
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

class FriendRequest(Base):
    """好友请求模型"""
    __tablename__ = "friend_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"))
    receiver_id: Mapped[UUID] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"))
    message: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False) 