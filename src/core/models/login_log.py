from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Integer, Boolean, DateTime, SmallInteger, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from src.core.database import Base

class LoginLog(Base):
    __tablename__ = "login_logs"
    
    id = Column(PGUUID, primary_key=True, server_default="gen_random_uuid()")
    user_id = Column(PGUUID, ForeignKey("User.id", ondelete="CASCADE"))
    login_type = Column(SmallInteger, nullable=False)
    ip = Column(Text, nullable=False)
    device_info = Column(JSONB, default={})
    status = Column(SmallInteger, nullable=False)
    create_user_id = Column(Text, nullable=False, server_default="current_user")
    update_user_id = Column(Text, nullable=False, server_default="current_user")
    create_time = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP")
    update_time = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP")
    is_deleted = Column(Boolean, default=False)
    remark = Column(Text, default='')
    
    # 关系
    user = relationship("User", backref="login_logs") 