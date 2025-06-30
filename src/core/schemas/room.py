from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from .response import ResponseCode, SuccessResponse, ErrorResponse

# 删除操作响应模型
class DeleteResponse(BaseModel):
    """删除操作响应模型"""
    pass

# RoomPlayer 相关模型
class RoomPlayerBase(BaseModel):
    """房间玩家基础模型"""
    player_order: int = Field(..., description="玩家顺序，1为房主")
    status: str = Field("ready", description="玩家状态：ready-准备, playing-游戏中, disconnected-断线, finished-已完成")
    deck_id: Optional[UUID] = Field(None, description="使用的卡组ID")
    remark: str = Field("", description="备注信息")

class RoomPlayerCreate(RoomPlayerBase):
    """创建房间玩家请求模型"""
    room_id: UUID = Field(..., description="房间ID")
    user_id: UUID = Field(..., description="用户ID")

class RoomPlayerUpdate(RoomPlayerBase):
    """更新房间玩家请求模型"""
    player_order: Optional[int] = Field(None, description="玩家顺序，1为房主")
    status: Optional[str] = Field(None, description="玩家状态")
    deck_id: Optional[UUID] = Field(None, description="使用的卡组ID")

class RoomPlayerInDB(RoomPlayerBase):
    """数据库中的房间玩家模型"""
    id: UUID = Field(..., description="主键ID")
    room_id: UUID = Field(..., description="房间ID")
    user_id: UUID = Field(..., description="用户ID")
    join_time: datetime = Field(..., description="加入时间")
    leave_time: Optional[datetime] = Field(None, description="离开时间")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(False, description="是否删除")

    class Config:
        from_attributes = True

class RoomPlayerResponse(RoomPlayerInDB):
    """房间玩家响应模型"""
    user: Optional[Dict[str, Any]] = Field(None, description="用户信息")
    deck: Optional[Dict[str, Any]] = Field(None, description="卡组信息")

class RoomPlayerDetailResponse(BaseModel):
    """房间玩家详细信息响应模型"""
    id: UUID = Field(..., description="玩家记录ID")
    room_id: UUID = Field(..., description="房间ID")
    user_id: UUID = Field(..., description="用户ID")
    player_order: int = Field(..., description="玩家顺序")
    status: str = Field(..., description="玩家状态")
    deck_id: Optional[UUID] = Field(None, description="使用的卡组ID")
    join_time: datetime = Field(..., description="加入时间")
    leave_time: Optional[datetime] = Field(None, description="离开时间")
    remark: str = Field(..., description="备注信息")
    user_info: Optional[Dict[str, Any]] = Field(None, description="用户信息")
    deck_info: Optional[Dict[str, Any]] = Field(None, description="卡组信息")

    class Config:
        from_attributes = True

# 查询参数模型
class RoomQueryParams(BaseModel):
    """房间查询参数模型"""
    key_word: Optional[str] = Field(None, description="房间名称关键词，支持模糊匹配")
    friend_room: bool = Field(False, description="是否只显示好友的房间")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")

class RoomPlayerQueryParams(BaseModel):
    """房间玩家查询参数模型"""
    room_id: Optional[UUID] = Field(None, description="房间ID")
    user_id: Optional[UUID] = Field(None, description="用户ID")
    status: Optional[str] = Field(None, description="玩家状态")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")

# Room 相关模型
class RoomBase(BaseModel):
    """房间基础模型"""
    room_name: str = Field(..., description="房间名称")
    room_type: str = Field("public", description="房间类型：public-公开, private-私密, ranked-排位")
    status: str = Field("waiting", description="房间状态：waiting-等待中, playing-游戏中, finished-已结束")
    max_players: int = Field(2, ge=2, le=4, description="最大玩家数")
    current_players: int = Field(0, ge=0, description="当前玩家数")
    game_mode: str = Field("standard", description="游戏模式：standard-标准, draft-轮抽, sealed-现开")
    game_settings: Dict[str, Any] = Field(default_factory=dict, description="游戏设置JSON，包含时间限制、规则等")
    pass_word: Optional[str] = Field(None, description="房间密码，私密房间使用")
    remark: str = Field("", description="备注信息")

class RoomCreateRequest(BaseModel):
    """创建房间请求模型"""
    room_name: str = Field(..., description="房间名称")
    room_type: str = Field("public", description="房间类型：public-公开, private-私密, ranked-排位")
    game_settings: Dict[str, Any] = Field(default_factory=dict, description="游戏设置JSON，包含时间限制、规则等")
    pass_word: Optional[str] = Field(None, description="房间密码，私密房间使用")
    remark: str = Field("", description="备注信息")

class RoomCreate(RoomBase):
    """创建房间请求模型"""
    pass

class RoomUpdate(RoomBase):
    """更新房间请求模型"""
    room_name: Optional[str] = Field(None, description="房间名称")
    room_type: Optional[str] = Field(None, description="房间类型")
    status: Optional[str] = Field(None, description="房间状态")
    max_players: Optional[int] = Field(None, ge=2, le=4, description="最大玩家数")
    current_players: Optional[int] = Field(None, ge=0, description="当前玩家数")
    game_mode: Optional[str] = Field(None, description="游戏模式")
    game_settings: Optional[Dict[str, Any]] = Field(None, description="游戏设置JSON")

class RoomInDB(RoomBase):
    """数据库中的房间模型"""
    id: UUID = Field(..., description="主键ID")
    created_by: UUID = Field(..., description="创建者ID")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(False, description="是否删除")
    room_players: List[RoomPlayerInDB] = Field(default_factory=list, description="房间玩家列表")

    class Config:
        from_attributes = True

class RoomResponse(RoomInDB):
    """房间响应模型"""
    creator: Optional[Dict[str, Any]] = Field(None, description="创建者信息")

# 响应模型
class RoomListResponse(BaseModel):
    """房间列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[RoomInDB] = Field(..., description="房间列表")

class RoomPlayerListResponse(BaseModel):
    """房间玩家列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[RoomPlayerInDB] = Field(..., description="房间玩家列表")

class RoomPlayersResponse(BaseModel):
    """房间玩家信息响应模型"""
    room_id: UUID = Field(..., description="房间ID")
    room_name: str = Field(..., description="房间名称")
    total_players: int = Field(..., description="总玩家数")
    max_players: int = Field(..., description="最大玩家数")
    players: List[RoomPlayerDetailResponse] = Field(..., description="玩家列表")

class UserRoomStatusResponse(BaseModel):
    """用户房间状态响应模型"""
    in_room: bool = Field(..., description="是否在房间中")
    room_id: Optional[UUID] = Field(None, description="房间ID")
    room_name: Optional[str] = Field(None, description="房间名称")
    player_order: Optional[int] = Field(None, description="玩家顺序")
    status: Optional[str] = Field(None, description="玩家状态")
    join_time: Optional[datetime] = Field(None, description="加入时间")

# 定义具体的响应类型
RoomSuccessResponse = SuccessResponse[RoomInDB]
RoomListSuccessResponse = SuccessResponse[RoomListResponse]
RoomPlayerSuccessResponse = SuccessResponse[RoomPlayerInDB]
RoomPlayerListSuccessResponse = SuccessResponse[RoomPlayerListResponse]
RoomPlayersSuccessResponse = SuccessResponse[RoomPlayersResponse]
UserRoomStatusSuccessResponse = SuccessResponse[UserRoomStatusResponse]
DeleteSuccessResponse = SuccessResponse[DeleteResponse]

# 踢出房间请求模型
class KickPlayerRequest(BaseModel):
    target_user_id: UUID = Field(..., description="被踢出的用户ID") 