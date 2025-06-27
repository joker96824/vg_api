from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from .response import ResponseCode, SuccessResponse, ErrorResponse

# 匹配状态响应模型
class MatchStatusResponse(BaseModel):
    """匹配状态响应模型"""
    in_queue: bool = Field(..., description="是否在匹配队列中")
    position: int = Field(0, description="队列位置")
    match_id: Optional[str] = Field(None, description="匹配ID")
    created_at: Optional[datetime] = Field(None, description="加入队列时间")

# 匹配结果响应模型
class MatchResultResponse(BaseModel):
    """匹配结果响应模型"""
    match_id: str = Field(..., description="匹配ID")
    room_id: Optional[str] = Field(None, description="房间ID")
    room_name: Optional[str] = Field(None, description="房间名称")
    matched_users: Optional[List[Dict[str, Any]]] = Field(None, description="匹配到的用户列表，包含user_id、nickname、avatar")

# 匹配用户信息模型
class MatchedUserInfo(BaseModel):
    """匹配用户信息模型"""
    user_id: str = Field(..., description="用户ID")
    nickname: str = Field(..., description="用户昵称")
    avatar: Optional[str] = Field(None, description="用户头像")

# 确认匹配响应模型
class ConfirmMatchResponse(BaseModel):
    """确认匹配响应模型"""
    room_id: Optional[str] = Field(None, description="房间ID")
    room_name: Optional[str] = Field(None, description="房间名称")

# 清理结果响应模型
class CleanupResultResponse(BaseModel):
    """清理结果响应模型"""
    cleaned_count: int = Field(0, description="清理的记录数量")

# 删除操作响应模型
class DeleteResponse(BaseModel):
    """删除操作响应模型"""
    pass

# 定义具体的响应类型
MatchStatusSuccessResponse = SuccessResponse[MatchStatusResponse]
MatchResultSuccessResponse = SuccessResponse[MatchResultResponse]
ConfirmMatchSuccessResponse = SuccessResponse[ConfirmMatchResponse]
CleanupResultSuccessResponse = SuccessResponse[CleanupResultResponse]
DeleteSuccessResponse = SuccessResponse[DeleteResponse] 