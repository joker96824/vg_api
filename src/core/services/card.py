from typing import List, Optional, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.orm import selectinload
import logging

from src.core.models.card import Card, CardRarity
from src.core.schemas.card import CardQueryParams

logger = logging.getLogger(__name__)

class CardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cards(self, params: CardQueryParams) -> Tuple[List[Card], int]:
        """
        查询卡牌列表
        """
        logger.debug(f"查询参数: {params}")

        # 构建查询条件
        conditions = []
        if params.card_code:
            conditions.append(Card.card_code.ilike(f"%{params.card_code}%"))
        if params.name_cn:
            conditions.append(Card.name_cn.ilike(f"%{params.name_cn}%"))
        if params.name_en:
            conditions.append(Card.name_en.ilike(f"%{params.name_en}%"))
        if params.card_type:
            conditions.append(Card.card_type == params.card_type)
        if params.trigger_type:
            conditions.append(Card.trigger_type == params.trigger_type)
        if params.grade is not None:
            conditions.append(Card.grade == params.grade)
        if params.race:
            conditions.append(Card.race == params.race)
        if params.nation:
            conditions.append(Card.nation == params.nation)
        if params.clan:
            conditions.append(Card.clan == params.clan)

        logger.debug(f"查询条件: {conditions}")

        # 构建查询语句
        query: Select = select(Card).options(selectinload(Card.rarity_infos))
        if conditions:
            query = query.where(and_(*conditions))

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)

        # 分页
        query = query.offset((params.page - 1) * params.page_size).limit(params.page_size)

        logger.debug(f"SQL查询: {query}")

        # 执行查询
        result = await self.session.execute(query)
        cards = result.scalars().all()

        logger.debug(f"查询结果: {cards}")

        return cards, total

    async def get_card_by_id(self, card_id: int) -> Optional[Card]:
        """
        根据ID查询卡牌
        """
        logger.debug(f"查询卡牌ID: {card_id}")

        query = select(Card).options(selectinload(Card.rarity_infos)).where(Card.id == card_id)
        result = await self.session.execute(query)
        card = result.scalar_one_or_none()

        logger.debug(f"查询结果: {card}")

        return card

    async def get_card_by_code(self, card_code: str) -> Optional[Card]:
        """
        根据卡牌编号查询卡牌
        """
        logger.debug(f"查询卡牌编号: {card_code}")

        query = select(Card).options(selectinload(Card.rarity_infos)).where(Card.card_code == card_code)
        result = await self.session.execute(query)
        card = result.scalar_one_or_none()

        logger.debug(f"查询结果: {card}")

        return card 