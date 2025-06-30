from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base
import uuid

class BattleAction(Base):
    """对战操作记录模型"""
    __tablename__ = "battle_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    battle_id = Column(UUID(as_uuid=True), ForeignKey("battles.id"), nullable=False, comment="对战ID")
    action_sequence = Column(Integer, nullable=False, comment="操作序号，用于回放时确定顺序")
    player_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), nullable=False, comment="操作玩家ID")
    action_type = Column(String(50), nullable=False, comment="操作类型：play_card-出牌, attack-攻击, end_turn-结束回合, draw_card-抽牌等")
    action_data = Column(JSON, nullable=False, default={}, comment="操作数据JSON，包含具体操作信息")
    game_state_after = Column(JSON, default={}, comment="操作后的游戏状态JSON，用于回放")
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, comment="操作时间戳")
    create_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="创建用户ID")
    update_user_id = Column(UUID(as_uuid=True), ForeignKey("User.id"), comment="更新用户ID")
    create_time = Column(DateTime(timezone=True), default=datetime.utcnow, comment="创建时间")
    update_time = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    remark = Column(Text, comment="备注")
    
    # 关系
    battle = relationship("Battle", back_populates="battle_actions")
    player = relationship("User", foreign_keys=[player_id], back_populates="battle_actions")
    
    def __repr__(self):
        return f"<BattleAction(battle_id={self.battle_id}, sequence={self.action_sequence}, type='{self.action_type}')>" 