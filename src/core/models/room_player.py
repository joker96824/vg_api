from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base
import uuid

class RoomPlayer(Base):
    """房间玩家模型"""
    __tablename__ = "room_players"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, comment="房间ID")
    user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), nullable=False, comment="用户ID")
    player_order = Column(Integer, nullable=False, comment="玩家顺序，1为房主")
    status = Column(String(20), nullable=False, default="ready", comment="玩家状态：ready-准备, playing-游戏中, disconnected-断线, finished-已完成")
    deck_id = Column(UUID(as_uuid=True), ForeignKey("deck.id"), comment="使用的卡组ID")
    join_time = Column(DateTime(timezone=True), default=datetime.utcnow, comment="加入时间")
    leave_time = Column(DateTime(timezone=True), comment="离开时间")
    create_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="创建用户ID")
    update_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="更新用户ID")
    create_time = Column(DateTime(timezone=True), default=datetime.utcnow, comment="创建时间")
    update_time = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    remark = Column(Text, comment="备注")
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('room_id', 'user_id', name='uq_room_player'),
    )
    
    # 关系
    room = relationship("Room", back_populates="room_players")
    user = relationship("User", foreign_keys=[user_id], back_populates="room_players")
    deck = relationship("Deck", foreign_keys=[deck_id], back_populates="room_players")
    
    def __repr__(self):
        return f"<RoomPlayer(room_id={self.room_id}, user_id={self.user_id}, order={self.player_order})>" 