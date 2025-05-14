from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.deck import Deck, DeckCard
from ..schemas.deck import DeckCreate, DeckUpdate, DeckCardCreate, DeckCardUpdate, DeckQueryParams, DeckCardQueryParams

logger = logging.getLogger(__name__)

class DeckService:
    """卡组服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_deck(self, deck: DeckCreate) -> Deck:
        """创建卡组"""
        db_deck = Deck(
            user_id=deck.user_id,
            deck_name=deck.deck_name,
            deck_description=deck.deck_description,
            is_public=deck.is_public,
            is_official=deck.is_official,
            format_type=deck.format_type,
            deck_version=deck.deck_version,
            remark=deck.remark
        )
        self.db.add(db_deck)
        await self.db.commit()
        await self.db.refresh(db_deck)
        return db_deck

    async def get_deck(self, deck_id: UUID) -> Optional[Deck]:
        """获取卡组详情"""
        result = await self.db.execute(
            select(Deck)
            .options(selectinload(Deck.deck_cards))
            .where(
                and_(
                    Deck.id == deck_id,
                    Deck.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_decks(self, params: DeckQueryParams) -> tuple[int, List[Deck]]:
        """获取卡组列表"""
        # 构建查询条件
        conditions = [
            Deck.is_deleted == False,
            Deck.user_id == params.user_id
        ]

        # 计算总数
        total = await self.db.scalar(
            select(func.count()).select_from(Deck).where(and_(*conditions))
        )
        logger.debug(f"查询总数: {total}")

        # 获取分页数据
        result = await self.db.execute(
            select(Deck)
            .options(selectinload(Deck.deck_cards))  # 预加载关系
            .where(and_(*conditions))
            .order_by(desc(Deck.create_time))
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        decks = result.scalars().all()
        logger.debug(f"查询结果: {decks}")

        return total, decks

    async def update_deck(self, deck_id: UUID, deck: DeckUpdate, deck_cards: List[DeckCardCreate]) -> Optional[Deck]:
        """更新卡组及其卡片列表"""
        db_deck = await self.get_deck(deck_id)
        if not db_deck:
            return None

        # 更新卡组基本信息
        update_data = deck.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_deck, field, value)

        # 删除原有的卡片
        for card in db_deck.deck_cards:
            card.is_deleted = True
            card.update_time = datetime.now()

        # 添加新的卡片
        for card_data in deck_cards:
            db_deck_card = DeckCard(
                deck_id=deck_id,
                card_id=card_data.card_id,
                card_rarity_id=card_data.card_rarity_id,
                quantity=card_data.quantity,
                deck_zone=card_data.deck_zone,
                position=card_data.position,
                remark=card_data.remark
            )
            self.db.add(db_deck_card)

        db_deck.update_time = datetime.now()
        await self.db.commit()
        await self.db.refresh(db_deck)
        return db_deck

    async def delete_deck(self, deck_id: UUID) -> bool:
        """删除卡组（软删除）"""
        db_deck = await self.get_deck(deck_id)
        if not db_deck:
            return False

        db_deck.is_deleted = True
        db_deck.update_time = datetime.now()
        await self.db.commit()
        return True


class DeckCardService:
    """卡组卡片服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_deck_card(self, deck_card: DeckCardCreate) -> DeckCard:
        """创建卡组卡片"""
        db_deck_card = DeckCard(
            deck_id=deck_card.deck_id,
            card_id=deck_card.card_id,
            card_rarity_id=deck_card.card_rarity_id,
            quantity=deck_card.quantity,
            deck_zone=deck_card.deck_zone,
            position=deck_card.position,
            remark=deck_card.remark
        )
        self.db.add(db_deck_card)
        await self.db.commit()
        await self.db.refresh(db_deck_card)
        return db_deck_card

    async def get_deck_card(self, deck_card_id: UUID) -> Optional[DeckCard]:
        """获取卡组卡片详情"""
        result = await self.db.execute(
            select(DeckCard).where(
                and_(
                    DeckCard.id == deck_card_id,
                    DeckCard.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_deck_cards(self, params: DeckCardQueryParams) -> tuple[int, List[DeckCard]]:
        """获取卡组卡片列表"""
        # 构建查询条件
        conditions = [DeckCard.is_deleted == False]
        if params.deck_id:
            conditions.append(DeckCard.deck_id == params.deck_id)
        if params.card_id:
            conditions.append(DeckCard.card_id == params.card_id)
        if params.card_rarity_id:
            conditions.append(DeckCard.card_rarity_id == params.card_rarity_id)
        if params.deck_zone:
            conditions.append(DeckCard.deck_zone == params.deck_zone)

        # 计算总数
        total = await self.db.scalar(
            select(func.count()).select_from(DeckCard).where(and_(*conditions))
        )

        # 获取分页数据
        result = await self.db.execute(
            select(DeckCard)
            .where(and_(*conditions))
            .order_by(DeckCard.position)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        deck_cards = result.scalars().all()

        return total, deck_cards

    async def update_deck_card(self, deck_card_id: UUID, deck_card: DeckCardUpdate) -> Optional[DeckCard]:
        """更新卡组卡片"""
        db_deck_card = await self.get_deck_card(deck_card_id)
        if not db_deck_card:
            return None

        update_data = deck_card.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_deck_card, field, value)

        db_deck_card.update_time = datetime.now()
        await self.db.commit()
        await self.db.refresh(db_deck_card)
        return db_deck_card

    async def delete_deck_card(self, deck_card_id: UUID) -> bool:
        """删除卡组卡片（软删除）"""
        db_deck_card = await self.get_deck_card(deck_card_id)
        if not db_deck_card:
            return False

        db_deck_card.is_deleted = True
        db_deck_card.update_time = datetime.now()
        await self.db.commit()
        return True