from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base
import uuid

class Room(Base):
    """房间模型"""
    __tablename__ = "rooms"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_name = Column(String(100), nullable=False, comment="房间名称")
    room_type = Column(String(20), nullable=False, default="public", comment="房间类型：public-公开, private-私密, ranked-排位")
    status = Column(String(20), nullable=False, default="waiting", comment="房间状态：waiting-等待中, loading-加载中, gaming-游戏中, finished-已结束")
    max_players = Column(Integer, nullable=False, default=2, comment="最大玩家数")
    current_players = Column(Integer, nullable=False, default=0, comment="当前玩家数")
    game_mode = Column(String(50), default="standard", comment="游戏模式：standard-标准, draft-轮抽, sealed-现开")
    game_settings = Column(JSON, default={}, comment="游戏设置JSON，包含时间限制、规则等")
    pass_word = Column(String(100), nullable=True, comment="房间密码，私密房间使用")
    created_by = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="创建者ID")
    create_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="创建用户ID")
    update_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="更新用户ID")
    create_time = Column(DateTime(timezone=True), default=datetime.utcnow, comment="创建时间")
    update_time = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    remark = Column(Text, comment="备注")
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_rooms")
    room_players = relationship("RoomPlayer", back_populates="room", cascade="all, delete-orphan")
    battles = relationship("Battle", back_populates="room", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Room(id={self.id}, name='{self.room_name}', status='{self.status}')>" 