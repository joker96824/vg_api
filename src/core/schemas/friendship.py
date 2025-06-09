from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class FriendRequestBase(BaseModel):
    """好友请求基础模型"""
    message: Optional[str] = Field(None, max_length=255, description="好友请求附言")

class FriendRequestCreate(FriendRequestBase):
    """创建好友请求"""
    receiver_id: UUID = Field(..., description="接收者ID")

class AcceptRequest(BaseModel):
    """接受好友请求"""
    request_id: UUID = Field(..., description="请求ID")

class RejectRequest(BaseModel):
    """拒绝好友请求"""
    request_id: UUID = Field(..., description="请求ID")

class FriendRequestInDB(FriendRequestBase):
    """数据库中的好友请求"""
    id: UUID = Field(..., description="主键ID")
    sender_id: UUID = Field(..., description="发送者ID")
    receiver_id: UUID = Field(..., description="接收者ID")
    status: str = Field(..., description="请求状态")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(False, description="是否删除")

    class Config:
        from_attributes = True

class FriendRequestResponse(FriendRequestInDB):
    """好友请求响应"""
    sender_nickname: str = Field(..., description="发送者昵称")
    receiver_nickname: str = Field(..., description="接收者昵称")

class FriendshipBase(BaseModel):
    """好友关系基础模型"""
    remark: Optional[str] = Field(None, max_length=50, description="好友备注")
    is_blocked: bool = Field(False, description="是否拉入黑名单")

class FriendshipCreate(FriendshipBase):
    """创建好友关系"""
    friend_id: UUID = Field(..., description="好友ID")

class FriendshipUpdate(FriendshipBase):
    """更新好友关系"""
    pass

class FriendshipInDB(FriendshipBase):
    """数据库中的好友关系"""
    id: UUID = Field(..., description="主键ID")
    user_id: UUID = Field(..., description="用户ID")
    friend_id: UUID = Field(..., description="好友ID")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(False, description="是否删除")

    class Config:
        from_attributes = True

class FriendshipResponse(FriendshipInDB):
    """好友关系响应"""
    friend_nickname: str = Field(..., description="好友昵称")
    friend_avatar: Optional[str] = Field(None, description="好友头像")

class FriendSearchParams(BaseModel):
    """好友搜索参数"""
    keyword: str = Field(..., description="搜索关键词")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")

class FriendRequestQueryParams(BaseModel):
    """好友请求查询参数"""
    status: Optional[str] = Field(None, description="请求状态")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")

class FriendshipQueryParams(BaseModel):
    """好友关系查询参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量") 