from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import logging

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.deck import Deck, DeckCard
from ..schemas.deck import DeckCreate, DeckUpdate, DeckCardCreate, DeckCardUpdate, DeckQueryParams, DeckCardQueryParams
from ..models.card import Card

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
        if params.only_preset:
            conditions = [
                Deck.is_deleted == False,
                Deck.user_id == params.user_id,
                Deck.preset > -1
            ]
        else:
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
        try:
            logger.info(f"开始更新卡组 - deck_id: {deck_id}")
            
            db_deck = await self.get_deck(deck_id)
            if not db_deck:
                logger.warning(f"未找到卡组 - deck_id: {deck_id}")
                return None
                
            logger.info(f"找到卡组，当前信息: {db_deck.deck_name}")
            
            # 更新卡组基本信息
            update_data = deck.model_dump(exclude_unset=True, exclude={'deck_cards'})
            for field, value in update_data.items():
                setattr(db_deck, field, value)
                logger.info(f"更新卡组字段: {field} = {value}")

            # 记录原有卡片数量
            original_card_count = len(db_deck.deck_cards)
            logger.info(f"原有卡片数量: {original_card_count}")

            # 显式删除所有现有卡片
            delete_query = select(DeckCard).where(
                and_(
                    DeckCard.deck_id == deck_id,
                    DeckCard.is_deleted == False
                )
            )
            result = await self.db.execute(delete_query)
            existing_cards = result.scalars().all()
            
            for card in existing_cards:
                logger.info(f"删除卡片: deck_id={card.deck_id}, card_id={card.card_id}, image={card.image}, deck_zone={card.deck_zone}")
                await self.db.delete(card)
            
            # 提交删除操作
            logger.info("提交删除操作")
            await self.db.commit()
            
            # 添加新的卡片
            new_cards_count = len(deck.deck_cards)
            logger.info(f"准备添加新卡片，数量: {new_cards_count}")
            
            for card_data in deck.deck_cards:
                logger.info(f"添加新卡片: card_id={card_data.card_id}, image={card_data.image}, deck_zone={card_data.deck_zone}, quantity={card_data.quantity}")
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

            db_deck.update_time = datetime.now()
            logger.info("提交数据库更改")
            await self.db.commit()
            
            logger.info("刷新卡组信息")
            await self.db.refresh(db_deck)
            
            logger.info(f"卡组更新完成 - deck_id: {deck_id}, 新卡片数量: {len(db_deck.deck_cards)}")
            return db_deck
            
        except Exception as e:
            logger.error(f"更新卡组时发生错误 - deck_id: {deck_id}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {str(e)}")
            # 回滚事务
            await self.db.rollback()
            raise ValueError(f"更新卡组失败: {str(e)}")

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

    async def update_deck_preset(self, deck_id: UUID, preset: int, user_id: UUID) -> Optional[Deck]:
        """更新卡组预设值"""
        try:
            # 1. 获取卡组信息并检查is_valid
            db_deck = await self.get_deck(deck_id)
            if not db_deck:
                return None
                
            if not db_deck.is_valid:
                raise ValueError("该卡组不符合要求")
                
            # 2. 检查用户权限
            # 将两个ID都转换为字符串进行比较
            user_id_str = str(user_id)
            db_user_id_str = str(db_deck.user_id)
            
            if user_id_str != db_user_id_str:
                raise ValueError(f"无权修改此卡组")
                
            # 3. 获取原有的preset值
            old_preset = db_deck.preset
            
            # 4. 处理预设值更新逻辑
            if preset == 0:
                if old_preset == 1:
                    # 找到当前preset为0的卡组，将其改为1
                    result = await self.db.execute(
                        select(Deck)
                        .where(
                            and_(
                                Deck.user_id == user_id,
                                Deck.preset == 0,
                                Deck.is_deleted == False
                            )
                        )
                    )
                    current_preset_0 = result.scalar_one_or_none()
                    if current_preset_0:
                        current_preset_0.preset = 1
                        current_preset_0.update_time = datetime.now()
                        
                elif old_preset == -1:
                    # 找到所有preset > -1的卡组
                    result = await self.db.execute(
                        select(Deck)
                        .where(
                            and_(
                                Deck.user_id == user_id,
                                Deck.preset > -1,
                                Deck.is_deleted == False
                            )
                        )
                        .order_by(Deck.update_time)
                    )
                    preset_decks = result.scalars().all()
                    
                    if preset_decks:
                        # 将最早的改为-1，其他的改为1
                        for i, deck in enumerate(preset_decks):
                            deck.preset = -1 if i > 3 else 1
                            deck.update_time = datetime.now()
            
            # 5. 更新当前卡组的preset值
            db_deck.preset = preset
            db_deck.update_time = datetime.now()
            
            await self.db.commit()
            await self.db.refresh(db_deck)
            return db_deck
            
        except ValueError as e:
            raise e
        except Exception as e:
            raise ValueError(f"更新卡组预设值失败: {str(e)}")

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
            preset=-1,
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

    async def check_deck_validity(self, deck_id: UUID) -> Tuple[bool, List[str]]:
        """
        检查卡组合规性
        返回: (是否合规, 问题描述列表)
        """
        try:
            problems = []
            
            # 获取卡组信息
            deck = await self.get_deck(deck_id)
            if not deck:
                return False, ["卡组不存在"]

            # 获取卡组中的所有卡牌
            query = select(DeckCard).where(
                and_(
                    DeckCard.deck_id == deck_id,
                    DeckCard.is_deleted == False
                )
            )
            result = await self.db.execute(query)
            deck_cards = result.scalars().all()

            if not deck_cards:
                return False, ["卡组为空"]

            # 获取所有卡牌ID
            card_ids = [dc.card_id for dc in deck_cards]
            
            # 获取卡牌详细信息
            cards_query = select(Card).where(Card.id.in_(card_ids))
            cards_result = await self.db.execute(cards_query)
            cards = cards_result.scalars().all()
            card_dict = {str(card.id): card for card in cards}

            # 按区域分组卡牌
            zone_cards = {
                "ride": [],
                "main": [],
                "g": [],
                "token": []
            }
            for dc in deck_cards:
                if dc.deck_zone in zone_cards:
                    zone_cards[dc.deck_zone].append(dc)

            # 1. 检查各区域卡牌数量
            main_cards = zone_cards["main"]
            ride_cards = zone_cards["ride"]
            g_cards = zone_cards["g"]

            total_main_cards = sum(dc.quantity for dc in main_cards)
            if total_main_cards != 50:
                problems.append(f"主卡组数量必须为50张，当前为{total_main_cards}张")

            total_ride_cards = sum(dc.quantity for dc in ride_cards)
            if total_ride_cards != 4:
                problems.append(f"骑乘区数量必须为4张，当前为{total_ride_cards}张")

            total_g_cards = sum(dc.quantity for dc in g_cards)
            if total_g_cards > 16:
                problems.append(f"G区数量不能超过16张，当前为{total_g_cards}张")

            # 2. 检查骑乘区卡牌类型
            for dc in ride_cards:
                card = card_dict.get(str(dc.card_id))
                if card and card.card_type not in ["普通单位", "触发单位"]:
                    problems.append(f"骑乘区只能放入普通单位或触发单位，{card.name_cn}是{card.card_type}")

            # 3. 检查骑乘区等级分布
            ride_grades = {}
            for dc in ride_cards:
                card = card_dict.get(str(dc.card_id))
                if card and card.grade is not None:
                    ride_grades[card.grade] = ride_grades.get(card.grade, 0) + dc.quantity

            for grade in [0, 1, 2, 3]:
                if ride_grades.get(grade, 0) != 1:
                    problems.append(f"骑乘区必须包含1张等级{grade}的卡牌")

            # 4. 检查G区卡牌类型
            for dc in g_cards:
                card = card_dict.get(str(dc.card_id))
                if card and card.card_type != "G单位":
                    problems.append(f"G区只能放入G单位，{card.name_cn}是{card.card_type}")

            # 5. 检查主卡组卡牌类型
            invalid_types = ["G单位", "RIDE卡组纹章", "标记", "纹章", "能量", "衍生物单位", "衍生物设置指令"]
            for dc in main_cards:
                card = card_dict.get(str(dc.card_id))
                if card and card.card_type in invalid_types:
                    problems.append(f"主卡组不能放入{card.card_type}，{card.name_cn}是{card.card_type}")

            # 6. 检查main+ride中同名卡牌数量
            main_ride_cards = main_cards + ride_cards
            card_counts: Dict[str, int] = {}
            for dc in main_ride_cards:
                card = card_dict.get(str(dc.card_id))
                if not card:
                    continue
                card_counts[str(dc.card_id)] = card_counts.get(str(dc.card_id), 0) + dc.quantity
                if card_counts[str(dc.card_id)] > 4:
                    problems.append(f"主卡组和骑乘区中同名卡牌最多只能放入4张，{card.name_cn}当前为{card_counts[str(dc.card_id)]}张")

            # 7. 检查main+ride中触发单位数量
            trigger_cards = sum(
                dc.quantity for dc in main_ride_cards 
                if card_dict.get(str(dc.card_id)) and card_dict[str(dc.card_id)].card_type == "触发单位"
            )
            if trigger_cards > 16:
                problems.append(f"主卡组和骑乘区中触发单位不能超过16张，当前为{trigger_cards}张")

            # 8. 检查main+ride中特定触发类型数量
            heal_trigger = sum(
                dc.quantity for dc in main_ride_cards 
                if card_dict.get(str(dc.card_id)) and 
                card_dict[str(dc.card_id)].trigger_type and 
                "治" in card_dict[str(dc.card_id)].trigger_type
            )
            if heal_trigger > 4:
                problems.append(f"主卡组和骑乘区中治疗触发不能超过4张，当前为{heal_trigger}张")

            over_trigger = sum(
                dc.quantity for dc in main_ride_cards 
                if card_dict.get(str(dc.card_id)) and 
                card_dict[str(dc.card_id)].trigger_type and 
                "超" in card_dict[str(dc.card_id)].trigger_type
            )
            if over_trigger > 1:
                problems.append(f"主卡组和骑乘区中暴击触发不能超过1张，当前为{over_trigger}张")

            # 检查主卡组、ride+g中卡牌国家一致性
            all_cards = main_cards + ride_cards + g_cards
            # 用于存储每个卡片的完整国家信息
            card_nations = {}  # {card_id: nation}
            # 用于存储每个国家的卡片
            nation_cards = {}  # {nation: [{"name_cn": xxx, "name_jp": xxx, "card_id": xxx}, ...]}
            
            # 第一步：收集所有卡片的国家信息
            for dc in all_cards:
                card = card_dict.get(str(dc.card_id))
                if card and card.nation:
                    # 存储卡片的完整国家信息
                    card_nations[str(dc.card_id)] = card.nation
                    # 将卡片添加到对应国家的列表中
                    if card.nation not in nation_cards:
                        nation_cards[card.nation] = []
                    nation_cards[card.nation].append({
                        "name_cn": card.name_cn,
                        "name_jp": card.name_jp,
                        "card_id": str(dc.card_id)
                    })
            
            if len(nation_cards) > 1:
                # 第二步：检查国家兼容性
                # 首先找出所有可能的主要国家（按卡片数量排序）
                possible_main_nations = sorted(
                    nation_cards.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
                
                # 检查每个可能的主要国家
                main_nation = None
                other_nations = []
                has_incompatible = False
                
                for nation, cards in possible_main_nations:
                    # 检查这个国家是否可以作为主要国家
                    is_valid_main = True
                    temp_other_nations = []
                    
                    for other_nation, other_cards in nation_cards.items():
                        if other_nation == nation:
                            continue
                            
                        # 检查这个其他国家的所有卡片是否与主要国家兼容
                        is_compatible = True
                        for other_card in other_cards:
                            other_nation_str = card_nations[other_card["card_id"]]
                            # 如果其他卡片的国家包含主要国家，则兼容
                            if nation in other_nation_str:
                                continue
                            # 如果主要国家的卡片包含其他卡片的国家，则兼容
                            for main_card in cards:
                                main_nation_str = card_nations[main_card["card_id"]]
                                if other_nation_str in main_nation_str:
                                    continue
                            # 否则不兼容
                            is_compatible = False
                            has_incompatible = True
                            break
                            
                        if not is_compatible:
                            is_valid_main = False
                            break
                            
                        temp_other_nations.append((other_nation, other_cards))
                    
                    if is_valid_main:
                        main_nation = nation
                        other_nations = temp_other_nations
                        break
                
                # 如果没有找到合适的主要国家，使用卡片数量最多的国家
                if not main_nation:
                    main_nation = possible_main_nations[0][0]
                    other_nations = [(n, c) for n, c in nation_cards.items() if n != main_nation]
                
                # 只有在存在不兼容的卡片时才添加错误信息
                if has_incompatible:
                    # 第三步：生成错误信息
                    other_nations_info = []
                    for nation, cards in other_nations:
                        # 检查这个国家的卡片是否与主要国家兼容
                        compatible_cards = []
                        incompatible_cards = []
                        for card in cards:
                            card_nation = card_nations[card["card_id"]]
                            if main_nation in card_nation:
                                compatible_cards.append(f"{card['name_cn']}({card['name_jp']}) [包含{main_nation}]")
                            else:
                                incompatible_cards.append(f"{card['name_cn']}({card['name_jp']})")
                        
                        if compatible_cards:
                            other_nations_info.append(f"{nation} [兼容]: {', '.join(compatible_cards)}")
                        if incompatible_cards:
                            other_nations_info.append(f"{nation} [不兼容]: {', '.join(incompatible_cards)}")
                    
                    problems.append(
                        f"主卡组、骑乘区和G区中的卡牌国家必须一致。"
                        f"主要国家({main_nation})与其他国家卡片：{' | '.join(other_nations_info)}"
                    )

            # 在返回结果前更新数据库中的is_valid字段
            is_valid = len(problems) == 0
            deck.is_valid = is_valid
            deck.preset = 1 if is_valid else -1
            deck.update_time = datetime.now()
            deck.remark = ";".join(problems)
            await self.db.commit()

            return is_valid, problems

        except Exception as e:
            return False, [f"检查卡组合规性时发生错误: {str(e)}"]

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