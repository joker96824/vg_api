import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.card import Card, CardRarity

logger = logging.getLogger(__name__)


class CardImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_card(self, card_data: Dict) -> Optional[Card]:
        """导入单张卡牌数据"""
        try:
            # 检查卡牌是否已存在
            existing_card = await self._get_card_by_code(card_data.get("card_code"))
            if existing_card:
                logger.info(f"卡牌已存在: {card_data.get('card_code')}")
                return existing_card

            # 创建卡牌记录
            card = Card(
                card_code=card_data.get("card_code"),
                card_link=card_data.get("card_link"),
                card_number=card_data.get("card_number"),
                card_rarity=card_data.get("card_rarity"),
                name_cn=card_data.get("name_cn"),
                name_jp=card_data.get("name_jp"),
                nation=card_data.get("nation"),
                clan=card_data.get("clan"),
                grade=card_data.get("grade"),
                skill=card_data.get("skill"),
                card_power=card_data.get("card_power"),
                shield=card_data.get("shield"),
                critical=card_data.get("critical"),
                special_mark=card_data.get("special_mark"),
                card_type=card_data.get("card_type"),
                trigger_type=card_data.get("trigger_type"),
                ability=card_data.get("ability"),
                card_alias=card_data.get("card_alias"),
                card_group=card_data.get("card_group"),
                ability_json=card_data.get("ability_json"),
            )

            # 创建卡牌稀有度信息
            if card_data.get("rarity_info"):
                rarity_info = CardRarity(
                    pack_name=card_data["rarity_info"].get("pack_name"),
                    card_number=card_data["rarity_info"].get("card_number"),
                    release_info=card_data["rarity_info"].get("release_info"),
                    quote=card_data["rarity_info"].get("quote"),
                    illustrator=card_data["rarity_info"].get("illustrator"),
                    image_url=card_data["rarity_info"].get("image_url"),
                )
                card.card_rarity_info = rarity_info

            self.session.add(card)
            await self.session.commit()
            await self.session.refresh(card)
            logger.info(f"成功导入卡牌: {card.card_code}")
            return card

        except Exception as e:
            await self.session.rollback()
            logger.error(f"导入卡牌失败: {str(e)}")
            return None

    async def import_cards_batch(self, cards_data: List[Dict]) -> Dict[str, int]:
        """批量导入卡牌数据"""
        results = {
            "total": len(cards_data),
            "success": 0,
            "failed": 0,
            "skipped": 0
        }

        for card_data in cards_data:
            try:
                card = await self.import_card(card_data)
                if card:
                    results["success"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                logger.error(f"批量导入卡牌失败: {str(e)}")
                results["failed"] += 1

        return results

    async def _get_card_by_code(self, card_code: str) -> Optional[Card]:
        """根据卡牌代码获取卡牌"""
        query = select(Card).where(Card.card_code == card_code)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def import_from_json_file(self, file_path: str) -> Dict[str, int]:
        """从 JSON 文件导入卡牌数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cards_data = json.load(f)
            return await self.import_cards_batch(cards_data)
        except Exception as e:
            logger.error(f"从文件导入卡牌失败: {str(e)}")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0
            } 