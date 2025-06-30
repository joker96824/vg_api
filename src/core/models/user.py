from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Integer, Boolean, DateTime, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from src.core.database import Base

class User(Base):
    __tablename__ = "User"
    
    id = Column(PGUUID, primary_key=True, server_default="gen_random_uuid()")
    mobile = Column(Text, nullable=True)
    mobile_hash = Column(String(64), nullable=True)
    email = Column(Text, nullable=True)
    email_hash = Column(String(64), nullable=True)
    password_hash = Column(Text, nullable=False)
    nickname = Column(Text, nullable=False)
    avatar = Column(Text)
    level = Column(SmallInteger, default=1)
    status = Column(SmallInteger, default=1)
    last_login_at = Column(DateTime(timezone=True))
    create_user_id = Column(Text, nullable=False, server_default="current_user")
    update_user_id = Column(Text, nullable=False, server_default="current_user")
    create_time = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP")
    update_time = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP")
    is_deleted = Column(Boolean, default=False)
    user_version = Column(Integer, default=1)
    remark = Column(Text, default='')
    
    # 对战相关关系
    created_rooms = relationship("Room", foreign_keys="Room.created_by", back_populates="creator")
    room_players = relationship("RoomPlayer", foreign_keys="RoomPlayer.user_id", back_populates="user")
    battle_actions = relationship("BattleAction", foreign_keys="BattleAction.player_id", back_populates="player")
    won_battles = relationship("Battle", foreign_keys="Battle.winner_id", back_populates="winner")
    
    # 卡组相关关系
    decks = relationship("Deck", back_populates="user") 