from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Integer, Boolean, DateTime, SmallInteger, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from src.core.database import Base

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(PGUUID, primary_key=True, server_default="gen_random_uuid()")
    user_id = Column(PGUUID, ForeignKey("User.id", ondelete="CASCADE"))
    token_hash = Column(String(64), nullable=False)
    device_fingerprint = Column(Text, nullable=False)
    ip = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), nullable=False)
    create_user_id = Column(Text, nullable=False, server_default="current_user")
    update_user_id = Column(Text, nullable=False, server_default="current_user")
    create_time = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP")
    update_time = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP")
    is_deleted = Column(Boolean, default=False)
    remark = Column(Text, default='')
    
    # 关系
    user = relationship("User", backref="sessions") 