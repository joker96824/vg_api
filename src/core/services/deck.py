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

    async def create_deck(self, deck: DeckCreate, user_id: UUID) -> Deck:
        """创建卡组"""
        db_deck = Deck(
            user_id=user_id,
            deck_name=deck.deck_name,
            deck_description=deck.deck_description,
            is_public=deck.is_public,
            is_official=deck.is_official,
            preset=deck.preset,
            deck_version=deck.deck_version,
            remark=deck.remark
        )
        self.db.add(db_deck)
        await self.db.commit()
        
        # 重新查询以加载关系
        result = await self.db.execute(
            select(Deck)
            .options(selectinload(Deck.deck_cards))
            .where(Deck.id == db_deck.id)
        )
        db_deck = result.scalar_one()
        
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

    async def update_deck(self, deck_id: UUID, deck: DeckUpdate) -> Optional[Deck]:
        """更新卡组及其卡片列表"""
        db_deck = await self.get_deck(deck_id)
        if not db_deck:
            return None
        # 更新卡组基本信息
        update_data = deck.model_dump(exclude_unset=True, exclude={'deck_cards'})
        for field, value in update_data.items():
            setattr(db_deck, field, value)

        # 直接删除原有的卡片
        for card in db_deck.deck_cards:
            await self.db.delete(card)

        # 添加新的卡片
        for card_data in deck.deck_cards:
            db_deck_card = DeckCard(
                deck_id=deck_id,
                card_id=card_data.card_id,
                image=card_data.image,
                quantity=card_data.quantity,
                deck_zone=card_data.deck_zone,
                position=card_data.position,
                remark=card_data.remark
            )
            self.db.add(db_deck_card)
        print("--------------------------------")
        print(f"添加新的卡片: {deck.deck_cards}")
        print("--------------------------------")
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

    async def update_deck_info(self, deck_id: UUID, deck_name: Optional[str] = None, deck_description: Optional[str] = None) -> Optional[Deck]:
        """更新卡组名称和描述"""
        logger.info("="*50)
        logger.info("DeckService.update_deck_info - 开始处理:")
        logger.info(f"deck_id: {deck_id}")
        logger.info(f"deck_name: {deck_name}")
        logger.info(f"deck_description: {deck_description}")
        logger.info(f"deck_name type: {type(deck_name)}")
        logger.info(f"deck_description type: {type(deck_description)}")
        
        try:
            db_deck = await self.get_deck(deck_id)
            if not db_deck:
                logger.warning(f"卡组不存在 - deck_id: {deck_id}")
                return None
                
            logger.info("找到卡组，当前信息:")
            logger.info(f"当前名称: {db_deck.deck_name}")
            logger.info(f"当前描述: {db_deck.deck_description}")
            
            # 记录更新前的值
            old_name = db_deck.deck_name
            old_description = db_deck.deck_description
            
            if deck_name is not None:
                db_deck.deck_name = deck_name
                logger.info(f"更新名称: {old_name} -> {deck_name}")
            if deck_description is not None:
                db_deck.deck_description = deck_description
                logger.info(f"更新描述: {old_description} -> {deck_description}")
                
            db_deck.update_time = datetime.now()
            
            await self.db.commit()
            await self.db.refresh(db_deck)
            
            logger.info("更新后的卡组信息:")
            logger.info(f"新名称: {db_deck.deck_name}")
            logger.info(f"新描述: {db_deck.deck_description}")
            logger.info("="*50)
            
            return db_deck
            
        except Exception as e:
            logger.error(f"更新卡组信息时发生错误 - deck_id: {deck_id}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {str(e)}")
            logger.error("="*50)
            raise

    async def update_deck_preset(self, deck_id: UUID, preset: int) -> Optional[Deck]:
        """更新卡组预设值"""
        db_deck = await self.get_deck(deck_id)
        if not db_deck:
            return None
            
        db_deck.preset = preset
        db_deck.update_time = datetime.now()
        
        await self.db.commit()
        await self.db.refresh(db_deck)
        return db_deck

    async def copy_deck(self, user_id: UUID, deck_id: UUID) -> Optional[Deck]:
        """复制卡组
        Args:
            user_id: 新卡组的所有者ID
            deck_id: 要复制的卡组ID
        Returns:
            新创建的卡组对象，如果原卡组不存在则返回None
        """
        # 获取原卡组信息
        original_deck = await self.get_deck(deck_id)
        if not original_deck:
            return None

        # 创建新卡组
        new_deck = Deck(
            user_id=user_id,
            deck_name=f"{original_deck.deck_name} (复制)",
            deck_description=original_deck.deck_description,
            is_public=original_deck.is_public,
            is_official=original_deck.is_official,
            preset=original_deck.preset,
            deck_version=original_deck.deck_version,
            remark=original_deck.remark
        )
        self.db.add(new_deck)
        await self.db.commit()
        await self.db.refresh(new_deck)

        # 复制卡组卡片
        for original_card in original_deck.deck_cards:
            new_card = DeckCard(
                deck_id=new_deck.id,
                card_id=original_card.card_id,
                image=original_card.image,
                quantity=original_card.quantity,
                deck_zone=original_card.deck_zone,
                position=original_card.position,
                remark=original_card.remark
            )
            self.db.add(new_card)

        await self.db.commit()
        
        # 重新查询以加载关系
        result = await self.db.execute(
            select(Deck)
            .options(selectinload(Deck.deck_cards))
            .where(Deck.id == new_deck.id)
        )
        new_deck = result.scalar_one()
        
        return new_deck

class DeckCardService:
    """卡组卡片服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_deck_card(self, deck_card: DeckCardCreate) -> DeckCard:
        """创建卡组卡片"""
        db_deck_card = DeckCard(
            deck_id=deck_card.deck_id,
            card_id=deck_card.card_id,
            image=deck_card.image,
            quantity=deck_card.quantity,
            deck_zone=deck_card.deck_zone,
            position=deck_card.position,
            remark=deck_card.remark
        )
        self.db.add(db_deck_card)
        await self.db.commit()
        await self.db.refresh(db_deck_card)
        return db_deck_card