from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
import json

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.battle import Battle
from ..models.battle_action import BattleAction
from ..models.room_player import RoomPlayer
from ..models.deck import Deck, DeckCard
from ..models.card import Card, CardAbility

logger = logging.getLogger(__name__)


class GameStateManager:
    """游戏状态管理器
    
    负责管理Battle.current_game_state字段，包括：
    - 游戏状态的保存和更新
    - 游戏状态的验证
    - 断线重连时的状态恢复
    - 游戏状态的历史记录
    """
    
    # 回合阶段定义
    PHASES = {
        "reset": "重置阶段",
        "draw": "抽卡阶段", 
        "ride": "骑升阶段",
        "main": "主要阶段",
        "battle": "战斗阶段",
        "battle_start": "战斗开始",
        "battle_attack": "攻击阶段",
        "battle_defence": "防御阶段", 
        "battle_trigger": "触发阶段",
        "battle_damage": "伤害阶段",
        "battle_end": "战斗结束",
        "turnend": "回合结束"
    }
    
    # 战斗子阶段列表
    BATTLE_SUBPHASES = [
        "battle_start",
        "battle_attack", 
        "battle_defence",
        "battle_trigger",
        "battle_damage",
        "battle_end"
    ]
    
    # 玩家场面区域定义
    FIELD_AREAS = {
        "ride": "骑升轴",
        "deck": "卡组",
        "hand": "手牌",
        "v": "先导者",
        "leftfront": "左前",
        "leftback": "左后",
        "rightfront": "右前",
        "rightback": "右后",
        "vback": "v后",
        "damage": "伤害区",
        "instruction": "指令区",
        "trigger": "判定区",
        "coa": "纹章",
        "g": "g区",
        "gdeck": "g卡组",
        "token": "衍生物",
        "seal": "封存",
        "effect": "永续效果"
    }
    
    # Card结构定义
    CARD_STRUCTURE = {
        "show": "bool",  # 后端发送时，根据用户调整bool，如果不是自己的卡或者卡组中的内容，则只有False，没有后续内容
        "id": "UUID",  # 卡牌ID
        "name_cn": "str",  # 中文名称
        "nation": "str",  # 所属国家
        "clan": "str",  # 所属种族
        "grade": "int",  # 等级
        "skill": "str",  # 技能
        "card_power": "int",  # 力量值
        "shield": "int",  # 护盾值
        "critical": "int",  # 暴击值
        "special_mark": "str",  # 特殊标识
        "card_type": "str",  # 卡片类型
        "trigger_type": "str",  # 触发类型
        "ability": "str",  # 能力描述
        "card_alias": "str",  # 卡牌别称
        "card_group": "str",  # 所属集团
        "image": "str",  # 图片属性
        "ability_list": "[CardAbility]",  # 卡牌能力列表，参考card和cardability的关系
        "status": "[string]",  # 特殊状态，如：武装，默认为空
        "normal_effect": "jsonb",  # 加攻/加暴，默认为空
        "additional_ability": "[]"  # 被赋予的技能，默认为空
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def create_card_object(self, card_data: Dict[str, Any], show: bool = True, 
                          ability_list: List[Dict[str, Any]] = None,
                          status: List[str] = None, normal_effect: Dict[str, Any] = None,
                          additional_ability: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建Card对象
        
        Args:
            card_data: 卡牌基础信息（来自数据库）
            show: 是否显示详细信息
            ability_list: 卡牌能力列表
            status: 特殊状态列表
            normal_effect: 普通效果（加攻/加暴）
            additional_ability: 被赋予的技能列表
            
        Returns:
            Card对象字典
        """
        if not show:
            # 如果不显示，只返回show=False
            return {"show": False}
        
        # 构建Card对象
        card_object = {
            "show": show,
            "id": str(card_data.get("id")),
            "name_cn": card_data.get("name_cn", ""),
            "nation": card_data.get("nation", ""),
            "clan": card_data.get("clan", ""),
            "grade": card_data.get("grade"),
            "skill": card_data.get("skill", ""),
            "card_power": card_data.get("card_power"),
            "shield": card_data.get("shield"),
            "critical": card_data.get("critical"),
            "special_mark": card_data.get("special_mark", ""),
            "card_type": card_data.get("card_type", ""),
            "trigger_type": card_data.get("trigger_type", ""),
            "ability": card_data.get("ability", ""),
            "card_alias": card_data.get("card_alias", ""),
            "card_group": card_data.get("card_group", ""),
            "image": card_data.get("image_url", ""),  # 使用image_url作为image属性
            "ability_list": ability_list or [],
            "status": status or [],
            "normal_effect": normal_effect or {},
            "additional_ability": additional_ability or []
        }
        
        return card_object
    
    def create_hidden_card(self) -> Dict[str, Any]:
        """创建隐藏的卡牌对象（只显示show=False）
        
        Returns:
            隐藏的Card对象
        """
        return {"show": False}
    
    def validate_card_object(self, card: Dict[str, Any]) -> tuple[bool, List[str]]:
        """验证Card对象的结构
        
        Args:
            card: Card对象字典
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        try:
            # 检查show字段
            if "show" not in card:
                errors.append("Card对象缺少show字段")
                return False, errors
            
            # 如果show=False，只需要这一个字段
            if not card["show"]:
                return True, []
            
            # 如果show=True，需要检查所有必需字段
            required_fields = [
                "id", "name_cn", "nation", "clan", "grade", "skill", "card_power", 
                "shield", "critical", "special_mark", "card_type", 
                "trigger_type", "ability", "card_alias", "card_group", 
                "image", "ability_list", "status", "normal_effect", "additional_ability"
            ]
            
            for field in required_fields:
                if field not in card:
                    errors.append(f"Card对象缺少字段: {field}")
            
            # 检查数据类型
            if "ability_list" in card and not isinstance(card["ability_list"], list):
                errors.append("ability_list字段必须是数组格式")
            
            if "status" in card and not isinstance(card["status"], list):
                errors.append("status字段必须是数组格式")
            
            if "normal_effect" in card and not isinstance(card["normal_effect"], dict):
                errors.append("normal_effect字段必须是对象格式")
            
            if "additional_ability" in card and not isinstance(card["additional_ability"], list):
                errors.append("additional_ability字段必须是数组格式")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"验证Card对象时发生错误: {str(e)}")
            return False, errors
    
    def convert_card_to_hidden(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """将Card对象转换为隐藏状态
        
        Args:
            card: 原始Card对象
            
        Returns:
            隐藏的Card对象
        """
        return {"show": False}
    
    def convert_cards_to_hidden(self, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将Card对象列表转换为隐藏状态
        
        Args:
            cards: Card对象列表
            
        Returns:
            隐藏的Card对象列表
        """
        return [self.convert_card_to_hidden(card) for card in cards]
    
    def filter_cards_by_visibility(self, cards: List[Dict[str, Any]], 
                                 visible_card_ids: List[str] = None) -> List[Dict[str, Any]]:
        """根据可见性过滤Card对象列表
        
        Args:
            cards: Card对象列表
            visible_card_ids: 可见卡牌ID列表，如果为None则全部可见
            
        Returns:
            过滤后的Card对象列表
        """
        if visible_card_ids is None:
            return cards
        
        filtered_cards = []
        for card in cards:
            if not card.get("show", True):
                # 如果已经是隐藏状态，保持隐藏
                filtered_cards.append(card)
            elif card.get("id") in visible_card_ids:
                # 如果在可见列表中，保持原样
                filtered_cards.append(card)
            else:
                # 否则转换为隐藏状态
                filtered_cards.append(self.convert_card_to_hidden(card))
        
        return filtered_cards
    
    def _create_empty_field(self) -> Dict[str, Any]:
        """创建空的玩家场面
        
        Returns:
            空的玩家场面字典
        """
        field = {}
        for area in self.FIELD_AREAS.keys():
            if area == "effect":
                field[area] = {}  # 永续效果为空对象
            else:
                field[area] = []  # 其他区域为空数组
        return field
    
    async def initialize_game_state(self, battle_id: UUID, room_id: UUID) -> Dict[str, Any]:
        """初始化游戏状态
        
        Args:
            battle_id: 对战ID
            room_id: 房间ID
            
        Returns:
            初始化后的游戏状态字典
        """
        try:
            logger.info(f"初始化游戏状态 - battle_id: {battle_id}, room_id: {room_id}")
            
            # 获取房间玩家信息
            # 查询房间玩家
            result = await self.db.execute(
                select(RoomPlayer)
                .where(
                    and_(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
                .order_by(RoomPlayer.player_order)
            )
            room_players = result.scalars().all()
            
            logger.info(f"找到房间玩家数量: {len(room_players)}")
            for i, player in enumerate(room_players):
                logger.info(f"玩家{i+1}: user_id={player.user_id}, player_order={player.player_order}, status={player.status}")
            
            if len(room_players) != 2:
                raise ValueError("卡牌游戏需要恰好2个玩家")
            
            # 获取玩家信息
            players = []
            player_fields = {}
            
            for i, room_player in enumerate(room_players):
                user_id = room_player.user_id
                players.append(user_id)
                logger.info(f"处理玩家{i+1} - user_id: {user_id}")
                
                # 获取用户的preset=0的卡组
                deck_result = await self.db.execute(
                    select(Deck)
                    .where(
                        and_(
                            Deck.user_id == user_id,
                            Deck.preset == 0,
                            Deck.is_deleted == False
                        )
                    )
                )
                deck = deck_result.scalar_one_or_none()
                
                if not deck:
                    logger.error(f"用户 {user_id} 没有preset=0的卡组")
                    raise ValueError(f"用户 {user_id} 没有preset=0的卡组")
                
                logger.info(f"玩家{i+1}的卡组: deck_id={deck.id}, deck_name={deck.deck_name}")
                
                # 获取卡组中的所有卡牌
                deck_cards_result = await self.db.execute(
                    select(DeckCard)
                    .where(
                        and_(
                            DeckCard.deck_id == deck.id,
                            DeckCard.is_deleted == False
                        )
                    )
                )
                deck_cards = deck_cards_result.scalars().all()
                
                logger.info(f"玩家{i+1}的卡组中有 {len(deck_cards)} 张卡牌")
                
                # 初始化玩家场面
                player_field = self._create_empty_field()
                
                # 根据deck_zone将卡牌分配到不同区域
                for deck_card in deck_cards:
                    logger.debug(f"处理卡牌: card_id={deck_card.card_id}, deck_zone={deck_card.deck_zone}, quantity={deck_card.quantity}")
                    
                    # 获取卡牌基础信息
                    card_result = await self.db.execute(
                        select(Card)
                        .where(
                            and_(
                                Card.id == deck_card.card_id,
                                Card.is_deleted == False
                            )
                        )
                    )
                    card = card_result.scalar_one_or_none()
                    
                    if not card:
                        logger.warning(f"卡牌不存在 - card_id: {deck_card.card_id}")
                        continue
                    
                    # 获取卡牌能力信息
                    ability_result = await self.db.execute(
                        select(CardAbility)
                        .where(
                            CardAbility.card_id == deck_card.card_id
                        )
                    )
                    card_abilities = ability_result.scalars().all()
                    
                    # 构建能力列表
                    ability_list = []
                    for ability in card_abilities:
                        ability_list.append({
                            "id": str(ability.id),
                            "ability_desc": ability.ability_desc,
                            "ability": ability.ability or {}
                        })
                    
                    # 创建Card对象
                    card_data = {
                        "id": str(card.id),
                        "name_cn": card.name_cn or "",
                        "nation": card.nation or "",
                        "clan": card.clan or "",
                        "grade": card.grade,
                        "skill": card.skill or "",
                        "card_power": card.card_power,
                        "shield": card.shield,
                        "critical": card.critical,
                        "special_mark": card.special_mark or "",
                        "card_type": card.card_type or "",
                        "trigger_type": card.trigger_type or "",
                        "ability": card.ability or "",
                        "card_alias": card.card_alias or "",
                        "card_group": card.card_group or "",
                        "image_url": deck_card.image  # 使用deck_card中的image
                    }
                    
                    card_object = self.create_card_object(
                        card_data=card_data,
                        show=True,
                        ability_list=ability_list
                    )
                    
                    # 根据deck_zone分配到不同区域
                    target_area = None
                    if deck_card.deck_zone == "ride":
                        target_area = "ride"
                    elif deck_card.deck_zone == "main":
                        target_area = "deck"
                    elif deck_card.deck_zone == "g":
                        target_area = "gdeck"
                    elif deck_card.deck_zone == "token":
                        target_area = "token"
                    else:
                        logger.warning(f"未知的deck_zone: {deck_card.deck_zone}")
                        continue
                    
                    # 根据quantity添加多个Card对象
                    for _ in range(deck_card.quantity):
                        player_field[target_area].append(card_object)
                    
                    logger.debug(f"卡牌已分配到区域 {target_area}, 当前区域卡牌数: {len(player_field[target_area])}")
                
                # 使用正确的玩家索引
                player_fields[f"player{i+1}_field"] = player_field
                logger.info(f"玩家{i+1}场面初始化完成，各区域卡牌数:")
                for area, cards in player_field.items():
                    if isinstance(cards, list):
                        logger.info(f"  {area}: {len(cards)} 张卡牌")
            
            # 创建初始游戏状态
            initial_state = {
                "battle_id": str(battle_id),
                "room_id": str(room_id),
                "player1_id": str(players[0]),  # 第一个玩家
                "player2_id": str(players[1]),  # 第二个玩家
                "first_player": str(players[0]),  # 优先出牌的玩家（默认第一个玩家）
                "turn_number": 1,  # 回合数，从1开始
                "current_player": str(players[0]),  # 当前回合的玩家
                "phase": "reset",  # 回合阶段，从重置阶段开始
                "player1_field": player_fields["player1_field"],
                "player2_field": player_fields["player2_field"],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"初始游戏状态创建完成，包含字段: {list(initial_state.keys())}")
            
            # 保存到数据库
            save_success = await self.save_game_state(battle_id, initial_state)
            if not save_success:
                logger.error(f"保存游戏状态失败 - battle_id: {battle_id}")
                raise ValueError("保存游戏状态失败")
            
            logger.info(f"游戏状态初始化成功 - battle_id: {battle_id}, room_id: {room_id}")
            return initial_state
            
        except Exception as e:
            logger.error(f"初始化游戏状态失败 - battle_id: {battle_id}, room_id: {room_id}, 错误: {str(e)}")
            raise ValueError(f"初始化游戏状态失败: {str(e)}")
    
    async def save_game_state(self, battle_id: UUID, game_state: Dict[str, Any]) -> bool:
        """保存游戏状态到数据库
        
        Args:
            battle_id: 对战ID
            game_state: 游戏状态字典
            
        Returns:
            保存是否成功
        """
        try:
            logger.info(f"保存游戏状态 - battle_id: {battle_id}, 游戏状态大小: {len(str(game_state))} 字符")
            
            # 更新游戏状态的更新时间
            game_state["updated_at"] = datetime.utcnow().isoformat()
            
            # 更新数据库中的current_game_state字段
            result = await self.db.execute(
                update(Battle)
                .where(
                    and_(
                        Battle.id == battle_id,
                        Battle.is_deleted == False
                    )
                )
                .values(
                    current_game_state=game_state,
                    update_time=datetime.utcnow()
                )
            )
            
            # 检查更新是否成功
            if result.rowcount == 0:
                logger.error(f"没有找到要更新的对战记录 - battle_id: {battle_id}")
                return False
            
            await self.db.commit()
            
            logger.info(f"游戏状态保存成功 - battle_id: {battle_id}, 更新行数: {result.rowcount}")
            return True
            
        except Exception as e:
            logger.error(f"保存游戏状态失败 - battle_id: {battle_id}, 错误: {str(e)}")
            await self.db.rollback()
            return False
    
    async def load_game_state(self, battle_id: UUID) -> Optional[Dict[str, Any]]:
        """从数据库加载游戏状态
        
        Args:
            battle_id: 对战ID
            
        Returns:
            游戏状态字典，如果不存在则返回None
        """
        try:
            logger.debug(f"加载游戏状态 - battle_id: {battle_id}")
            
            result = await self.db.execute(
                select(Battle.current_game_state)
                .where(
                    and_(
                        Battle.id == battle_id,
                        Battle.is_deleted == False
                    )
                )
            )
            
            game_state = result.scalar_one_or_none()
            
            if game_state:
                logger.debug(f"游戏状态加载成功 - battle_id: {battle_id}")
                return game_state
            else:
                logger.warning(f"游戏状态不存在 - battle_id: {battle_id}")
                return None
                
        except Exception as e:
            logger.error(f"加载游戏状态失败 - battle_id: {battle_id}, 错误: {str(e)}")
            return None
    
    async def update_game_state(self, battle_id: UUID, updates: Dict[str, Any]) -> bool:
        """更新游戏状态
        
        Args:
            battle_id: 对战ID
            updates: 要更新的字段字典
            
        Returns:
            更新是否成功
        """
        try:
            logger.debug(f"更新游戏状态 - battle_id: {battle_id}, updates: {updates}")
            
            # 加载当前游戏状态
            current_state = await self.load_game_state(battle_id)
            if not current_state:
                logger.warning(f"游戏状态不存在，无法更新 - battle_id: {battle_id}")
                return False
            
            # 合并更新
            current_state.update(updates)
            current_state["updated_at"] = datetime.utcnow().isoformat()
            
            # 保存更新后的状态
            return await self.save_game_state(battle_id, current_state)
            
        except Exception as e:
            logger.error(f"更新游戏状态失败 - battle_id: {battle_id}, 错误: {str(e)}")
            return False
    
    async def validate_game_state(self, game_state: Dict[str, Any]) -> tuple[bool, List[str]]:
        """验证游戏状态的有效性
        
        Args:
            game_state: 游戏状态字典
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        try:
            # 检查必需字段
            required_fields = [
                "battle_id", "player1_id", "player2_id", "first_player", 
                "turn_number", "current_player", "phase", 
                "player1_field", "player2_field"
            ]
            for field in required_fields:
                if field not in game_state:
                    errors.append(f"缺少必需字段: {field}")
            
            # 检查玩家ID格式
            if "player1_id" in game_state and "player2_id" in game_state:
                if game_state["player1_id"] == game_state["player2_id"]:
                    errors.append("玩家1和玩家2的ID不能相同")
            
            # 检查当前玩家是否在玩家列表中
            if "current_player" in game_state:
                valid_players = []
                if "player1_id" in game_state:
                    valid_players.append(game_state["player1_id"])
                if "player2_id" in game_state:
                    valid_players.append(game_state["player2_id"])
                
                if game_state["current_player"] not in valid_players:
                    errors.append("当前玩家不在玩家列表中")
            
            # 检查优先出牌玩家是否在玩家列表中
            if "first_player" in game_state:
                valid_players = []
                if "player1_id" in game_state:
                    valid_players.append(game_state["player1_id"])
                if "player2_id" in game_state:
                    valid_players.append(game_state["player2_id"])
                
                if game_state["first_player"] not in valid_players:
                    errors.append("优先出牌玩家不在玩家列表中")
            
            # 检查回合数
            if "turn_number" in game_state:
                if not isinstance(game_state["turn_number"], int) or game_state["turn_number"] < 1:
                    errors.append("回合数必须是大于等于1的整数")
            
            # 检查场面数据格式
            for field_name in ["player1_field", "player2_field"]:
                if field_name in game_state:
                    if not isinstance(game_state[field_name], dict):
                        errors.append(f"{field_name} 必须是字典格式")
                    else:
                        # 检查场面区域是否完整
                        field_errors = self._validate_field_structure(game_state[field_name], field_name)
                        errors.extend(field_errors)
            
            # 检查回合阶段是否有效
            if "phase" in game_state:
                if game_state["phase"] not in self.PHASES:
                    errors.append(f"无效的回合阶段: {game_state['phase']}")
            
            is_valid = len(errors) == 0
            return is_valid, errors
            
        except Exception as e:
            errors.append(f"验证游戏状态时发生错误: {str(e)}")
            return False, errors
    
    def _validate_field_structure(self, field: Dict[str, Any], field_name: str) -> List[str]:
        """验证玩家场面结构
        
        Args:
            field: 玩家场面字典
            field_name: 场面名称（用于错误信息）
            
        Returns:
            错误信息列表
        """
        errors = []
        
        for area, description in self.FIELD_AREAS.items():
            if area not in field:
                errors.append(f"{field_name} 缺少区域: {area} ({description})")
            else:
                # 检查区域数据类型
                if area == "effect":
                    if not isinstance(field[area], dict):
                        errors.append(f"{field_name}.{area} 必须是字典格式")
                else:
                    if not isinstance(field[area], list):
                        errors.append(f"{field_name}.{area} 必须是数组格式")
                    else:
                        # 验证数组中的Card对象
                        card_errors = self._validate_cards_in_area(field[area], f"{field_name}.{area}")
                        errors.extend(card_errors)
        
        return errors
    
    def _validate_cards_in_area(self, cards: List[Any], area_name: str) -> List[str]:
        """验证区域中的Card对象
        
        Args:
            cards: Card对象列表
            area_name: 区域名称（用于错误信息）
            
        Returns:
            错误信息列表
        """
        errors = []
        
        for i, card in enumerate(cards):
            if not isinstance(card, dict):
                errors.append(f"{area_name}[{i}] 必须是Card对象")
                continue
            
            # 验证Card对象结构
            is_valid, card_errors = self.validate_card_object(card)
            if not is_valid:
                for error in card_errors:
                    errors.append(f"{area_name}[{i}]: {error}")
        
        return errors
    
    async def get_game_state_for_reconnect(self, battle_id: UUID, player_id: UUID) -> Optional[Dict[str, Any]]:
        """获取用于断线重连的游戏状态
        
        Args:
            battle_id: 对战ID
            player_id: 重连玩家ID
            
        Returns:
            适合重连的游戏状态，如果不存在则返回None
        """
        try:
            logger.info(f"获取重连游戏状态 - battle_id: {battle_id}, player_id: {player_id}")
            
            game_state = await self.load_game_state(battle_id)
            if not game_state:
                return None
            
            # 验证游戏状态
            is_valid, errors = await self.validate_game_state(game_state)
            if not is_valid:
                logger.warning(f"游戏状态验证失败 - battle_id: {battle_id}, errors: {errors}")
                return None
            
            # 检查玩家是否在游戏中
            valid_players = [game_state.get("player1_id"), game_state.get("player2_id")]
            if str(player_id) not in valid_players:
                logger.warning(f"玩家不在游戏中 - battle_id: {battle_id}, player_id: {player_id}")
                return None
            
            logger.info(f"重连游戏状态获取成功 - battle_id: {battle_id}, player_id: {player_id}")
            return game_state
            
        except Exception as e:
            logger.error(f"获取重连游戏状态失败 - battle_id: {battle_id}, player_id: {player_id}, 错误: {str(e)}")
            return None
    
    async def update_player_field(self, battle_id: UUID, player_id: UUID, field_data: Dict[str, Any]) -> bool:
        """更新指定玩家的场面情况
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            field_data: 场面数据
            
        Returns:
            更新是否成功
        """
        try:
            logger.info(f"更新玩家场面 - battle_id: {battle_id}, player_id: {player_id}")
            
            game_state = await self.load_game_state(battle_id)
            if not game_state:
                logger.warning(f"游戏状态不存在 - battle_id: {battle_id}")
                return False
            
            # 确定是哪个玩家的场面
            if str(player_id) == game_state.get("player1_id"):
                field_key = "player1_field"
            elif str(player_id) == game_state.get("player2_id"):
                field_key = "player2_field"
            else:
                logger.warning(f"玩家不在游戏中 - battle_id: {battle_id}, player_id: {player_id}")
                return False
            
            # 验证场面数据结构
            field_errors = self._validate_field_structure(field_data, field_key)
            if field_errors:
                logger.warning(f"场面数据结构无效: {field_errors}")
                return False
            
            # 更新场面数据
            updates = {field_key: field_data}
            return await self.update_game_state(battle_id, updates)
            
        except Exception as e:
            logger.error(f"更新玩家场面失败 - battle_id: {battle_id}, player_id: {player_id}, 错误: {str(e)}")
            return False
    
    async def update_player_field_area(self, battle_id: UUID, player_id: UUID, area: str, cards: List[Any]) -> bool:
        """更新指定玩家的特定场面区域
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            area: 场面区域名称
            cards: 卡牌列表
            
        Returns:
            更新是否成功
        """
        try:
            logger.info(f"更新玩家场面区域 - battle_id: {battle_id}, player_id: {player_id}, area: {area}")
            
            # 验证区域是否有效
            if area not in self.FIELD_AREAS:
                logger.warning(f"无效的场面区域: {area}")
                return False
            
            # 获取当前玩家场面
            current_field = await self.get_player_field(battle_id, player_id)
            if current_field is None:
                logger.warning(f"玩家场面不存在 - battle_id: {battle_id}, player_id: {player_id}")
                return False
            
            # 更新特定区域
            current_field[area] = cards
            
            # 保存更新后的场面
            return await self.update_player_field(battle_id, player_id, current_field)
            
        except Exception as e:
            logger.error(f"更新玩家场面区域失败 - battle_id: {battle_id}, player_id: {player_id}, area: {area}, 错误: {str(e)}")
            return False
    
    async def get_player_field(self, battle_id: UUID, player_id: UUID) -> Optional[Dict[str, Any]]:
        """获取指定玩家的场面情况
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            
        Returns:
            玩家场面数据，如果不存在则返回None
        """
        try:
            game_state = await self.load_game_state(battle_id)
            if not game_state:
                return None
            
            if str(player_id) == game_state.get("player1_id"):
                return game_state.get("player1_field", {})
            elif str(player_id) == game_state.get("player2_id"):
                return game_state.get("player2_field", {})
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取玩家场面失败 - battle_id: {battle_id}, player_id: {player_id}, 错误: {str(e)}")
            return None
    
    async def get_player_field_area(self, battle_id: UUID, player_id: UUID, area: str) -> Optional[List[Any]]:
        """获取指定玩家的特定场面区域
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            area: 场面区域名称
            
        Returns:
            区域卡牌列表，如果不存在则返回None
        """
        try:
            # 验证区域是否有效
            if area not in self.FIELD_AREAS:
                logger.warning(f"无效的场面区域: {area}")
                return None
            
            # 获取玩家场面
            field = await self.get_player_field(battle_id, player_id)
            if field is None:
                return None
            
            return field.get(area, [])
            
        except Exception as e:
            logger.error(f"获取玩家场面区域失败 - battle_id: {battle_id}, player_id: {player_id}, area: {area}, 错误: {str(e)}")
            return None
    
    async def next_turn(self, battle_id: UUID) -> bool:
        """进入下一个回合
        
        Args:
            battle_id: 对战ID
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"进入下一回合 - battle_id: {battle_id}")
            
            game_state = await self.load_game_state(battle_id)
            if not game_state:
                logger.warning(f"游戏状态不存在 - battle_id: {battle_id}")
                return False
            
            # 切换当前玩家
            current_player = game_state.get("current_player")
            player1_id = game_state.get("player1_id")
            player2_id = game_state.get("player2_id")
            
            if current_player == player1_id:
                next_player = player2_id
            else:
                next_player = player1_id
                # 如果是玩家2的回合结束，回合数+1
                game_state["turn_number"] += 1
            
            updates = {
                "current_player": next_player,
                "turn_number": game_state.get("turn_number", 1),
                "phase": "reset"  # 新回合从重置阶段开始
            }
            
            return await self.update_game_state(battle_id, updates)
            
        except Exception as e:
            logger.error(f"进入下一回合失败 - battle_id: {battle_id}, 错误: {str(e)}")
            return False
    
    async def set_phase(self, battle_id: UUID, phase: str) -> bool:
        """设置当前回合阶段
        
        Args:
            battle_id: 对战ID
            phase: 回合阶段名称
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"设置回合阶段 - battle_id: {battle_id}, phase: {phase}")
            
            # 验证阶段是否有效
            if phase not in self.PHASES:
                logger.warning(f"无效的回合阶段: {phase}")
                return False
            
            updates = {"phase": phase}
            return await self.update_game_state(battle_id, updates)
            
        except Exception as e:
            logger.error(f"设置回合阶段失败 - battle_id: {battle_id}, phase: {phase}, 错误: {str(e)}")
            return False
    
    def is_valid_phase(self, phase: str) -> bool:
        """检查回合阶段是否有效
        
        Args:
            phase: 回合阶段名称
            
        Returns:
            是否有效
        """
        return phase in self.PHASES
    
    def get_phase_description(self, phase: str) -> Optional[str]:
        """获取回合阶段的描述
        
        Args:
            phase: 回合阶段名称
            
        Returns:
            阶段描述，如果无效则返回None
        """
        return self.PHASES.get(phase)
    
    def is_battle_subphase(self, phase: str) -> bool:
        """检查是否为战斗子阶段
        
        Args:
            phase: 回合阶段名称
            
        Returns:
            是否为战斗子阶段
        """
        return phase in self.BATTLE_SUBPHASES
    
    def is_valid_field_area(self, area: str) -> bool:
        """检查场面区域是否有效
        
        Args:
            area: 场面区域名称
            
        Returns:
            是否有效
        """
        return area in self.FIELD_AREAS
    
    def get_field_area_description(self, area: str) -> Optional[str]:
        """获取场面区域的描述
        
        Args:
            area: 场面区域名称
            
        Returns:
            区域描述，如果无效则返回None
        """
        return self.FIELD_AREAS.get(area)
    
    async def cleanup_game_state(self, battle_id: UUID) -> bool:
        """清理游戏状态（游戏结束时调用）
        
        Args:
            battle_id: 对战ID
            
        Returns:
            清理是否成功
        """
        try:
            logger.info(f"清理游戏状态 - battle_id: {battle_id}")
            
            # 清空游戏状态
            empty_state = {
                "battle_id": str(battle_id),
                "status": "finished",
                "cleaned_at": datetime.utcnow().isoformat()
            }
            
            return await self.save_game_state(battle_id, empty_state)
            
        except Exception as e:
            logger.error(f"清理游戏状态失败 - battle_id: {battle_id}, 错误: {str(e)}")
            return False 