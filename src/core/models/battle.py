from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base
import uuid

class Battle(Base):
    """对战记录模型"""
    __tablename__ = "battles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, comment="房间ID")
    battle_type = Column(String(20), nullable=False, default="casual", comment="对战类型：ranked-排位, casual-休闲, friendly-友谊赛")
    status = Column(String(20), nullable=False, default="active", comment="对战状态：active-进行中, finished-已结束, cancelled-已取消")
    winner_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="获胜者ID")
    start_time = Column(DateTime(timezone=True), default=datetime.utcnow, comment="开始时间")
    end_time = Column(DateTime(timezone=True), comment="结束时间")
    duration_seconds = Column(Integer, comment="对战时长（秒）")
    current_game_state = Column(JSON, default={}, comment="当前游戏状态JSON，用于断线重连")
    create_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="创建用户ID")
    update_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="更新用户ID")
    create_time = Column(DateTime(timezone=True), default=datetime.utcnow, comment="创建时间")
    update_time = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    remark = Column(Text, comment="备注")
    
    # 关系
    room = relationship("Room", back_populates="battles")
    winner = relationship("User", foreign_keys=[winner_id], back_populates="won_battles")
    battle_actions = relationship("BattleAction", back_populates="battle", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Battle(id={self.id}, room_id={self.room_id}, status='{self.status}')>" 