from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class CardRarityBase(BaseModel):
    """卡牌稀有度基础模型"""
    pack_name: Optional[str] = Field(None, description="卡包名称")
    card_number: Optional[str] = Field(None, description="卡包内编号")
    release_info: Optional[str] = Field(None, description="收录信息")
    quote: Optional[str] = Field(None, description="卡牌台词")
    illustrator: Optional[str] = Field(None, description="绘师")
    image_url: Optional[str] = Field(None, description="卡牌图片URL")

class CardRarityCreate(CardRarityBase):
    """创建卡牌稀有度模型"""
    card_id: UUID = Field(..., description="关联的卡牌ID")

class CardRarityUpdate(CardRarityBase):
    """更新卡牌稀有度模型"""
    pass

class CardRarityInDB(CardRarityBase):
    """数据库中的卡牌稀有度模型"""
    id: UUID = Field(..., description="主键ID")
    card_id: UUID = Field(..., description="关联的卡牌ID")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True

class CardBase(BaseModel):
    """卡牌基础模型"""
    card_code: str = Field(..., description="卡牌编号")
    name_cn: str = Field(..., description="中文名称")
    name_en: Optional[str] = Field(None, description="英文名称")
    card_type: str = Field(..., description="卡牌类型")
    trigger_type: Optional[str] = Field(None, description="触发类型")
    card_power: Optional[int] = Field(None, description="力量值")
    grade: Optional[int] = Field(None, description="等级")
    race: Optional[str] = Field(None, description="种族")
    nation: Optional[str] = Field(None, description="国家")
    clan: Optional[str] = Field(None, description="势力")
    skill: Optional[str] = Field(None, description="技能描述")
    flavor_text: Optional[str] = Field(None, description="卡牌描述")
    image_url: Optional[str] = Field(None, description="图片URL")
    card_thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    card_updated_at: Optional[datetime] = Field(None, description="更新时间")

class CardCreate(CardBase):
    """创建卡牌模型"""
    pass

class CardUpdate(CardBase):
    """更新卡牌模型"""
    pass

class CardInDB(CardBase):
    """数据库中的卡牌模型"""
    id: UUID = Field(..., description="主键ID")
    create_user_id: str = Field(..., description="创建用户")
    update_user_id: str = Field(..., description="更新用户")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    is_deleted: bool = Field(..., description="是否删除")
    card_version: int = Field(..., description="版本号")
    remark: str = Field(..., description="备注信息")
    rarity_infos: List[CardRarityInDB] = Field(default_factory=list, description="稀有度信息列表")

    class Config:
        from_attributes = True

class CardResponse(CardInDB):
    """卡牌响应模型"""
    pass

class CardListResponse(BaseModel):
    """卡牌列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[CardResponse] = Field(..., description="卡牌列表")

class CardQueryParams(BaseModel):
    """卡牌查询参数"""
    card_code: Optional[str] = Field(None, description="卡牌编号")
    name_cn: Optional[str] = Field(None, description="中文名称")
    name_en: Optional[str] = Field(None, description="英文名称")
    card_type: Optional[str] = Field(None, description="卡牌类型")
    trigger_type: Optional[str] = Field(None, description="触发类型")
    grade: Optional[int] = Field(None, description="等级")
    race: Optional[str] = Field(None, description="种族")
    nation: Optional[str] = Field(None, description="国家")
    clan: Optional[str] = Field(None, description="势力")
    page: int = Field(1, description="页码")
    page_size: int = Field(20, description="每页数量") 