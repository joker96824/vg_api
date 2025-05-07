from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
import enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, UniqueConstraint, Enum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from .database import Base


class CardType(str, enum.Enum):
    NORMAL = "normal"  # 普通单位
    TRIGGER = "trigger"  # 触发单位
    G_UNIT = "g_unit"  # G单位
    ORDER = "order"  # 指令卡
    MARKER = "marker"  # 标记

class TriggerType(str, enum.Enum):
    NONE = "none"  # 无触发
    CRITICAL = "critical"  # 暴击
    FRONT = "front"  # 前卫
    HEAL = "heal"  # 治疗
    DRAW = "draw"  # 抽卡
    STAND = "stand"  # 起立

class Card(Base):
    """卡牌基本信息表"""
    __tablename__ = "card"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    card_code: Mapped[str] = mapped_column(Text, nullable=False, index=True, comment="卡牌代码")
    card_link: Mapped[str] = mapped_column(Text, nullable=False, comment="卡牌链接")
    card_number: Mapped[Optional[str]] = mapped_column(Text, unique=True, comment="卡牌编号")
    card_rarity: Mapped[Optional[str]] = mapped_column(Text, comment="卡牌罕贵度")
    name_cn: Mapped[Optional[str]] = mapped_column(Text, index=True, comment="中文名称")
    name_jp: Mapped[Optional[str]] = mapped_column(Text, index=True, comment="日文名称")
    nation: Mapped[Optional[str]] = mapped_column(Text, comment="所属国家")
    clan: Mapped[Optional[str]] = mapped_column(Text, comment="所属种族")
    grade: Mapped[Optional[int]] = mapped_column(Integer, comment="等级")
    skill: Mapped[Optional[str]] = mapped_column(Text, comment="技能")
    card_power: Mapped[Optional[int]] = mapped_column(Integer, comment="力量值")
    shield: Mapped[Optional[int]] = mapped_column(Integer, comment="护盾值")
    critical: Mapped[Optional[int]] = mapped_column(Integer, comment="暴击值")
    special_mark: Mapped[Optional[str]] = mapped_column(Text, comment="特殊标识")
    card_type: Mapped[Optional[str]] = mapped_column(Text, comment="卡片类型")
    trigger_type: Mapped[Optional[str]] = mapped_column(Text, comment="触发类型")
    ability: Mapped[Optional[str]] = mapped_column(Text, comment="能力描述")
    card_alias: Mapped[Optional[str]] = mapped_column(Text, comment="卡牌别称")
    card_group: Mapped[Optional[str]] = mapped_column(Text, comment="所属集团")
    ability_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, comment="卡牌技能效果JSON数据")
    create_user_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="current_user", comment="创建用户")
    update_user_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="current_user", comment="更新用户")
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True, comment="更新时间")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否删除")
    card_version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    remark: Mapped[str] = mapped_column(Text, server_default="", comment="备注信息")

    # 关系
    rarity_infos: Mapped[List["CardRarity"]] = relationship("CardRarity", back_populates="card", cascade="all, delete-orphan")


class CardRarity(Base):
    """卡牌稀有度信息表"""
    __tablename__ = "cardrarity"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    card_id: Mapped[UUID] = mapped_column(PGUUID, ForeignKey("card.id", ondelete="CASCADE"), index=True)
    pack_name: Mapped[Optional[str]] = mapped_column(Text, index=True, comment="卡包名称")
    card_number: Mapped[Optional[str]] = mapped_column(Text, comment="卡包内编号")
    release_info: Mapped[Optional[str]] = mapped_column(Text, comment="收录信息")
    quote: Mapped[Optional[str]] = mapped_column(Text, comment="卡牌台词")
    illustrator: Mapped[Optional[str]] = mapped_column(Text, index=True, comment="绘师")
    image_url: Mapped[Optional[str]] = mapped_column(Text, comment="卡牌图片URL")
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    card: Mapped["Card"] = relationship("Card", back_populates="rarity_infos")

    # 唯一约束
    __table_args__ = (
        UniqueConstraint("pack_name", "card_number", name="uix_card_rarity_pack_number"),
    ) 