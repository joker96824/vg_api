from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from .response import ResponseCode, SuccessResponse, ErrorResponse

# 删除操作响应模型
class DeleteResponse(BaseModel):
    """删除操作响应模型"""
    pass

# DeckCard 相关模型
class DeckCardBase(BaseModel):
    """卡组卡片基础模型"""
    card_id: UUID = Field(..., description="卡片ID")
    image: str = Field(..., description="图片链接")
    quantity: int = Field(1, ge=1, le=4, description="卡片数量(1-4)")
    deck_zone: str = Field("main", description="卡牌所在区域: main(主轴)/trigger(触发区)/gzone(G区)/etc")
    position: Optional[int] = Field(None, description="在卡组中的位置")
    remark: str = Field("", description="备注信息")

class DeckCardCreate(DeckCardBase):
    """创建卡组卡片请求模型"""
    deck_id: UUID = Field(..., description="卡组ID")

class DeckCardUpdate(DeckCardBase):
    """更新卡组卡片请求模型"""
    card_id: Optional[UUID] = Field(None, description="卡片ID")
    quantity: Optional[int] = Field(None, ge=1, le=4, description="卡片数量(1-4)")

class DeckCardInDB(DeckCardBase):
    """数据库中的卡组卡片模型"""
    id: UUID = Field(..., description="主键ID")
    deck_id: UUID = Field(..., description="卡组ID")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(False, description="是否删除")

    class Config:
        from_attributes = True

class DeckCardResponse(DeckCardInDB):
    """卡组卡片响应模型"""
    card: Optional[Dict[str, Any]] = Field(None, description="卡片信息")

# 查询参数模型
class DeckQueryParams(BaseModel):
    """卡组查询参数模型"""
    user_id: UUID = Field(..., description="用户ID")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(100, ge=1, le=100, description="每页数量")

class DeckCardQueryParams(BaseModel):
    """卡组卡片查询参数模型"""
    deck_id: Optional[UUID] = Field(None, description="卡组ID")
    card_id: Optional[UUID] = Field(None, description="卡片ID")
    image: str = Field(..., description="图片链接")
    deck_zone: Optional[str] = Field(None, description="卡牌所在区域")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量") 

# Deck 相关模型
class DeckBase(BaseModel):
    """卡组基础模型"""
    deck_name: str = Field(..., description="卡组名称")
    deck_description: Optional[str] = Field(None, description="卡组描述")
    is_valid: bool = Field(False, description="卡组合规")
    is_public: bool = Field(False, description="是否公开")
    is_official: bool = Field(False, description="是否官方卡组")
    preset: int = Field(-1, description="预设卡组")
    deck_version: int = Field(1, description="版本号")
    remark: str = Field("", description="备注信息")

class DeckCreate(DeckBase):
    """创建卡组请求模型"""
    pass

class DeckUpdate(DeckBase):
    """更新卡组请求模型"""
    deck_name: Optional[str] = Field(None, description="卡组名称")
    deck_version: Optional[int] = Field(None, description="版本号")
    deck_cards: List[DeckCardCreate] = Field(default_factory=list, description="卡组卡牌列表")

class DeckInDB(DeckBase):
    """数据库中的卡组模型"""
    id: UUID = Field(..., description="主键ID")
    user_id: UUID = Field(..., description="用户ID")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(False, description="是否删除")
    deck_cards: List[DeckCardInDB] = Field(default_factory=list, description="卡组卡牌列表")

    class Config:
        from_attributes = True

class DeckResponse(DeckInDB):
    """卡组响应模型"""
    pass

# 修改 DeckResponse 相关模型
class DeckListResponse(BaseModel):
    """卡组列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[DeckInDB] = Field(..., description="卡组列表")

# 定义具体的响应类型
DeckSuccessResponse = SuccessResponse[DeckInDB]
DeckListSuccessResponse = SuccessResponse[DeckListResponse]
DeckCardSuccessResponse = SuccessResponse[DeckCardInDB]
DeckCardListSuccessResponse = SuccessResponse[List[DeckCardInDB]]
DeleteSuccessResponse = SuccessResponse[DeleteResponse]

class DeckValidityResponse(BaseModel):
    """卡组合规性检查响应模型"""
    is_valid: bool = Field(..., description="是否合规")
    problems: List[str] = Field(default_factory=list, description="问题列表")

class DeckValiditySuccessResponse(BaseModel):
    """卡组合规性检查成功响应模型"""
    success: bool = Field(..., description="是否成功")
    code: str = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: DeckValidityResponse = Field(..., description="响应数据")

