from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import Boolean, String, Integer, Text, ForeignKey, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base


class Deck(Base):
    """用户卡组表"""
    __tablename__ = "deck"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"), nullable=False, index=True)
    deck_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    deck_description: Mapped[Optional[str]] = mapped_column(Text)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    preset:  Mapped[int] = mapped_column(Integer, default=-1)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deck_version: Mapped[int] = mapped_column(Integer, default=1)
    remark: Mapped[str] = mapped_column(Text, default="")

    # 关系定义
    user = relationship("User", back_populates="decks")
    deck_cards = relationship("DeckCard", back_populates="deck", cascade="all, delete-orphan")
    room_players = relationship("RoomPlayer", back_populates="deck")

    def __repr__(self):
        return f"<Deck(id={self.id}, deck_name='{self.deck_name}')>"


class DeckCard(Base):
    """卡组卡片关联表"""
    __tablename__ = "deckcard"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    deck_id: Mapped[UUID] = mapped_column(ForeignKey("deck.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("card.id", ondelete="CASCADE"), nullable=False, index=True)
    image: Mapped[str] = mapped_column(String, default="other/Back")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    deck_zone: Mapped[str] = mapped_column(String, default="main")
    position: Mapped[Optional[int]] = mapped_column(Integer)
    create_time: Mapped[datetime] = mapped_column(server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    remark: Mapped[str] = mapped_column(Text, default="")

    # 关系定义
    deck = relationship("Deck", back_populates="deck_cards")
    card = relationship("Card", back_populates="deck_cards")

    def __repr__(self):
        return f"<DeckCard(id={self.id}, deck_id={self.deck_id}, card_id={self.card_id})>" 