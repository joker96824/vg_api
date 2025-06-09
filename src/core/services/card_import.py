import json
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from src.core.models.card import Card, CardRarity, CardAbility

# 设置SQLAlchemy日志级别为WARNING，减少SQL查询日志
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class CardImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_card(self, card_data: Dict) -> Dict[str, Any]:
        """导入单张卡牌数据"""
        result = {
            "status": "failed",
            "step": "init",
            "card_code": card_data.get("card_code"),
            "error": None,
            "card": None
        }
        
        try:
            # 1. 通过 name_cn、card_type 和 card_number 判断卡牌是否已存在
            result["step"] = "check_existing"
            name_cn = card_data.get("name_cn")
            card_type = card_data.get("card_type")
            ability = card_data.get("ability")
            card_number = card_data.get("card_number", "")
            
            if not name_cn or not card_type or not card_number:
                error_msg = f"缺少必要字段: name_cn={name_cn}, card_type={card_type}, card_number={card_number}, ability={ability}"
                logger.error(f"卡牌数据错误: {json.dumps(card_data, ensure_ascii=False)}\n{error_msg}")
                result["status"] = "error"
                result["error"] = error_msg
                return result

            # 获取card_number的前缀（/前面的部分）
            card_number_prefix = card_number.split("/")[0]
            
            # 构建查询条件
            conditions = [
                Card.name_cn == name_cn,
                Card.card_type == card_type,
                Card.ability == ability,
                Card.card_number.like(f"{card_number_prefix}%")  # 使用LIKE进行前缀匹配
            ]
            
            stmt = select(Card).where(*conditions)
            result_db = await self.session.execute(stmt)
            existing_card = result_db.scalar_one_or_none()
            
            if existing_card:
                logger.info(f"卡牌已存在: {name_cn}-{card_type}-{card_number_prefix}")
                result["status"] = "exists"
                result["card"] = existing_card
                
                # 2. 检查 rarity_infos 中 card_number 是否已存在
                result["step"] = "check_rarity"
                if card_data.get("rarity_infos"):
                    rarity_added = False
                    for rarity_data in card_data["rarity_infos"]:
                        card_number = rarity_data.get("card_number")
                        pack_name = rarity_data.get("pack_name")
                        if not card_number or not pack_name:
                            error_msg = f"稀有度信息缺少必要字段: card_number={card_number}, pack_name={pack_name}"
                            logger.error(f"卡牌数据错误: {json.dumps(card_data, ensure_ascii=False)}\n{error_msg}")
                            result["status"] = "error"
                            result["error"] = error_msg
                            return result

                        # 检查该 card_number 是否已存在
                        stmt = select(CardRarity).where(
                            CardRarity.card_id == existing_card.id,
                            CardRarity.card_number == card_number
                        )
                        result_db = await self.session.execute(stmt)
                        if result_db.scalar_one_or_none() is None:
                            # 不存在则添加新的稀有度信息
                            rarity_info = CardRarity(
                                card_id=existing_card.id,
                                pack_name=pack_name,
                                card_number=card_number,
                                release_info=rarity_data.get("release_info"),
                                quote=rarity_data.get("quote"),
                                illustrator=rarity_data.get("illustrator"),
                                image_url=rarity_data.get("image_url"),
                            )
                            self.session.add(rarity_info)
                            await self.session.flush()
                            rarity_added = True
                        
                        if rarity_added:
                            await self.session.commit()
                            await self.session.refresh(existing_card)
                            result["status"] = "updated"
                    
                    return result

            # 3. 若不存在，则依次添加 card，cardrarity，cardability
            result["step"] = "create_card"
            # 创建卡牌记录
            card = Card(
                card_code=card_data.get("card_code"),
                card_link=card_data.get("card_link"),
                card_number=card_data.get("card_number"),
                card_rarity=card_data.get("card_rarity"),
                name_cn=name_cn,
                name_jp=card_data.get("name_jp"),
                nation=card_data.get("nation"),
                clan=card_data.get("clan"),
                grade=card_data.get("grade"),
                skill=card_data.get("skill"),
                card_power=card_data.get("card_power"),
                shield=card_data.get("shield"),
                critical=card_data.get("critical"),
                special_mark=card_data.get("special_mark"),
                card_type=card_type,
                trigger_type=card_data.get("trigger_type"),
                ability=card_data.get("ability"),
                card_alias=card_data.get("card_alias"),
                card_group=card_data.get("card_group"),
            )

            self.session.add(card)
            await self.session.flush()
            result["step"] = "create_rarity"

            # 创建卡牌稀有度信息
            if card_data.get("rarity_infos"):
                for rarity_data in card_data["rarity_infos"]:
                    rarity_info = CardRarity(
                        card_id=card.id,
                        pack_name=rarity_data.get("pack_name"),
                        card_number=rarity_data.get("card_number"),
                        release_info=rarity_data.get("release_info"),
                        quote=rarity_data.get("quote"),
                        illustrator=rarity_data.get("illustrator"),
                        image_url=rarity_data.get("image_url"),
                    )
                    self.session.add(rarity_info)
                    await self.session.flush()

            result["step"] = "create_ability"
            # 创建卡牌能力信息
            if card_data.get("ability_infos"):
                for ability_data in card_data["ability_infos"]:
                    ability_info = CardAbility(
                        card_id=card.id,
                        ability_desc=ability_data.get("ability_desc"),
                        ability=ability_data.get("ability")
                    )
                    self.session.add(ability_info)
                    await self.session.flush()

            result["step"] = "commit"
            await self.session.commit()
            await self.session.refresh(card)
            result["status"] = "success"
            result["card"] = card
            return result

        except Exception as e:
            await self.session.rollback()
            error_msg = f"导入卡牌失败 (步骤: {result['step']}): {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            return result

    async def import_cards_batch(self, cards_data: List[Dict]) -> Dict[str, Any]:
        """批量导入卡牌数据"""
        results = {
            "total": len(cards_data),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []  # 只记录错误信息
        }

        for card_data in cards_data:
            try:
                result = await self.import_card(card_data)
                
                if result["status"] == "success":
                    results["success"] += 1
                elif result["status"] == "exists":
                    results["skipped"] += 1
                elif result["status"] == "updated":
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    if result.get("error"):
                        results["errors"].append({
                            "name_cn": result.get("card", {}).get("name_cn"),
                            "error": result["error"]
                        })
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "name_cn": card_data.get("name_cn"),
                    "error": str(e)
                })

        return results

    async def import_from_json_file(self, file_path: str) -> Dict[str, Any]:
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
                "skipped": 0,
                "errors": []
            } 