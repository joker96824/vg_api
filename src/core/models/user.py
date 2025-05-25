from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Integer, Boolean, DateTime, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
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