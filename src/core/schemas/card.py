from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from fastapi import Query
from .response import ResponseCode, SuccessResponse, ErrorResponse

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


class CardAbilityBase(BaseModel):
    """卡牌能力基础模型"""
    ability_desc: str = Field(..., description="能力描述")
    ability: Dict[str, Any] = Field(default_factory=dict, description="能力JSON数据")


class CardAbilityCreate(CardAbilityBase):
    """创建卡牌能力模型"""
    card_id: UUID = Field(..., description="关联的卡牌ID")


class CardAbilityUpdate(CardAbilityBase):
    """更新卡牌能力模型"""
    pass


class CardAbilityInDB(CardAbilityBase):
    """数据库中的卡牌能力模型"""
    id: UUID = Field(..., description="主键ID")
    card_id: UUID = Field(..., description="关联的卡牌ID")
    create_user_id: str = Field(..., description="创建用户")
    update_user_id: str = Field(..., description="更新用户")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True

class CardBase(BaseModel):
    """卡牌基础模型"""
    card_code: str = Field(..., description="卡牌代码")
    card_link: str = Field(..., description="卡牌链接")
    card_number: Optional[str] = Field(None, description="卡牌编号")
    card_rarity: Optional[str] = Field(None, description="卡牌罕贵度")
    name_cn: str = Field(..., description="中文名称")
    name_jp: Optional[str] = Field(None, description="日文名称")
    nation: Optional[str] = Field(None, description="所属国家")
    clan: Optional[str] = Field(None, description="所属种族")
    grade: Optional[int] = Field(None, description="等级")
    skill: Optional[str] = Field(None, description="技能")
    card_power: Optional[int] = Field(None, description="力量值")
    shield: Optional[int] = Field(None, description="护盾值")
    critical: Optional[int] = Field(None, description="暴击值")
    special_mark: Optional[str] = Field(None, description="特殊标识")
    card_type: Optional[str] = Field(None, description="卡片类型")
    trigger_type: Optional[str] = Field(None, description="触发类型")
    ability: Optional[str] = Field(None, description="能力描述")
    card_alias: Optional[str] = Field(None, description="卡牌别称")
    card_group: Optional[str] = Field(None, description="所属集团")
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
    ability_infos: List[CardAbilityInDB] = Field(default_factory=list, description="效果信息列表")

    class Config:
        from_attributes = True



class CardRarityResponse(BaseModel):
    id: UUID
    pack_name: Optional[str] = None
    card_number: Optional[str] = None
    release_info: Optional[str] = None
    quote: Optional[str] = None
    illustrator: Optional[str] = None
    image_url: Optional[str] = None

class CardListResponse(BaseModel):
    """卡牌列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[CardInDB] = Field(..., description="卡牌列表")

# 具体响应类型
CardSuccessResponse = SuccessResponse[CardInDB]
CardListSuccessResponse = SuccessResponse[CardListResponse]

class CardQueryParams(BaseModel):
    """卡牌查询参数"""
    keyword: Optional[str] = Field(None, description="关键词搜索（搜索范围：卡牌编号、中文名称、日文名称、国家、势力、技能、卡牌描述、备注）")
    nation: Optional[str] = Field(None, description="国家")
    clan: Optional[str] = Field(None, description="势力")
    grade: Optional[int] = Field(None, description="等级")
    skill: Optional[str] = Field(None, description="技能关键词")
    ability: Optional[str] = Field(None, description="能力描述关键词")
    card_power_min: Optional[int] = Field(None, description="力量值最小值")
    card_power_max: Optional[int] = Field(None, description="力量值最大值")
    shield: Optional[int] = Field(None, description="护盾值")
    special_mark: Optional[str] = Field(None, description="特殊标记")
    card_type: Optional[str] = Field(None, description="卡牌类型")
    trigger_type: Optional[str] = Field(None, description="触发类型")
    package: Optional[str] = Field(None, description="卡包名称")
    page: int = Field(1, description="页码")
    page_size: int = Field(20, description="每页数量")

    class Config:
        json_schema_extra = {
            "example": {
                "keyword": "基元",
                "nation": "圣域联合王国",
                "clan": "皇家骑士团",
                "grade": 3,
                "skill": "支援",
                "ability": "支援",
                "card_power_min": 5000,
                "card_power_max": 10000,
                "shield": 0,
                "special_mark": "双判",
                "card_type": "单位",
                "trigger_type": "暴击",
                "package": "BT01",
                "page": 1,
                "page_size": 20
            }
        }

class CardIdsRequest(BaseModel):
    """批量获取卡牌请求模型"""
    card_ids: List[str] = Field(..., description="卡牌ID列表", min_items=1, max_items=100)

class CardAbilityResponse(BaseModel):
    id: UUID
    ability_desc: str
    ability: Dict[str, Any] = Field(default_factory=dict)

class UpdateCardAbilityRequest(BaseModel):
    """更新卡牌能力请求模型"""
    id: str = Field(..., description="卡牌能力ID")
    ability: Dict[str, Any] = Field(..., description="卡牌能力内容") 