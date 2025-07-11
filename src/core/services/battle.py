from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import logging

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.battle import Battle
from ..models.battle_action import BattleAction
from ..models.room_player import RoomPlayer
from .game_state_manager import GameStateManager
from .coin_game_manager import CoinGameManager
from .coin_timeout_manager import CoinTimeoutManager

logger = logging.getLogger(__name__)

def is_user_room_owner(room: Any, user_id: Any) -> bool:
    """判断用户是否为房主（统一逻辑）"""
    return str(room.created_by) == str(user_id)

class BattleService:
    """对战服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # 延迟初始化连接管理器
        self._connection_manager = None
        # 初始化游戏状态管理器
        self.game_state_manager = GameStateManager(db)
        
        # 初始化猜拳管理器（需要Redis客户端）
        # 这里暂时设为None，后续在需要时初始化
        self.coin_game_manager = None
        self.coin_timeout_manager = None
        
    def _init_coin_managers(self, redis_client):
        """初始化猜拳管理器"""
        if not self.coin_game_manager:
            self.coin_game_manager = CoinGameManager(redis_client)
            self.coin_timeout_manager = CoinTimeoutManager(self.coin_game_manager, self)

    async def create_battle_from_room(self, room_id: UUID, battle_type: str = "casual") -> Battle:
        """从房间创建对战记录"""
        try:
            logger.info(f"开始创建对战记录 - room_id: {room_id}, battle_type: {battle_type}")
            
            # 检查房间是否已有进行中的对战
            existing_battle = await self.get_battle_by_room(room_id)
            if existing_battle and existing_battle.status in ["coin", "prepare", "active"]:
                logger.warning(f"房间已有进行中的对战 - room_id: {room_id}, battle_id: {existing_battle.id}, status: {existing_battle.status}")
                raise ValueError("房间已有进行中的对战")
            
            # 创建对战记录
            battle = Battle(
                room_id=room_id,
                battle_type=battle_type,
                status="coin",  # 初始化为coin状态
                start_time=datetime.now(timezone.utc),  # 使用UTC时区
                current_game_state={},  # 先创建空对象，后续由GameStateManager初始化
                create_user_id=None,  # 暂时不设置，后续可以添加
                update_user_id=None,  # 暂时不设置，后续可以添加
                remark=f"从房间 {room_id} 创建的对战"
            )
            self.db.add(battle)
            await self.db.commit()
            await self.db.refresh(battle)
            
            logger.info(f"对战记录创建完成 - battle_id: {battle.id}, 初始current_game_state: {battle.current_game_state}")
            
            # 使用GameStateManager初始化游戏状态
            logger.info(f"开始初始化游戏状态 - battle_id: {battle.id}, room_id: {room_id}")
            initial_game_state = await self.game_state_manager.initialize_game_state(
                battle_id=battle.id,
                room_id=room_id
            )
            
            logger.info(f"游戏状态初始化完成 - battle_id: {battle.id}, 游戏状态大小: {len(str(initial_game_state))} 字符")
            
            # 重新加载battle对象以获取最新的游戏状态
            result = await self.db.execute(
                select(Battle)
                .where(Battle.id == battle.id)
            )
            battle = result.scalar_one()
            
            logger.info(f"重新加载battle对象完成 - battle_id: {battle.id}, current_game_state大小: {len(str(battle.current_game_state)) if battle.current_game_state else 0} 字符")
            
            # 初始化猜拳游戏
            try:
                from src.core.redis import get_redis_client
                redis_client = get_redis_client()
                coin_result = await self.initialize_coin_game(room_id, redis_client)
                if coin_result["success"]:
                    logger.info(f"猜拳游戏初始化成功 - room_id: {room_id}")
                else:
                    logger.warning(f"猜拳游戏初始化失败 - room_id: {room_id}, 错误: {coin_result.get('error')}")
            except Exception as e:
                logger.error(f"猜拳游戏初始化异常 - room_id: {room_id}, 错误: {str(e)}")
            
            logger.info(f"对战记录创建成功 - battle_id: {battle.id}")
            return battle
            
        except Exception as e:
            logger.error(f"创建对战记录失败 - room_id: {room_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"创建对战记录失败: {str(e)}")

    async def record_battle_action(self, battle_id: UUID, player_id: UUID, 
                                 action_type: str, action_data: Dict[str, Any],
                                 record_game_state: bool = True) -> BattleAction:
        """记录对战操作
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            action_type: 操作类型
            action_data: 操作数据
            record_game_state: 是否记录操作后的游戏状态
            
        Returns:
            对战操作记录
        """
        try:
            logger.info(f"记录对战操作 - battle_id: {battle_id}, player_id: {player_id}, action_type: {action_type}")
            
            # 获取当前最大操作序号
            result = await self.db.execute(
                select(func.max(BattleAction.action_sequence))
                .where(
                    and_(
                        BattleAction.battle_id == battle_id,
                        BattleAction.is_deleted == False
                    )
                )
            )
            max_sequence = result.scalar()
            next_sequence = (max_sequence or 0) + 1
            
            # 获取操作后的游戏状态（如果需要记录）
            game_state_after = {}
            if record_game_state:
                game_state_after = await self.game_state_manager.load_game_state(battle_id) or {}
            
            # 创建操作记录
            battle_action = BattleAction(
                battle_id=battle_id,
                action_sequence=next_sequence,
                player_id=player_id,
                action_type=action_type,
                action_data=action_data,
                game_state_after=game_state_after,  # 记录操作后的游戏状态
                timestamp=datetime.now(timezone.utc),  # 使用UTC时区
                create_user_id=player_id,
                update_user_id=player_id,
                remark=f"操作类型: {action_type}"
            )
            self.db.add(battle_action)
            await self.db.commit()
            await self.db.refresh(battle_action)
            
            logger.info(f"对战操作记录成功 - action_id: {battle_action.id}, sequence: {next_sequence}")
            return battle_action
            
        except Exception as e:
            logger.error(f"记录对战操作失败 - battle_id: {battle_id}, player_id: {player_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"记录对战操作失败: {str(e)}")

    async def get_battle(self, battle_id: UUID) -> Optional[Battle]:
        """获取对战记录"""
        result = await self.db.execute(
            select(Battle)
            .options(selectinload(Battle.battle_actions))
            .where(
                and_(
                    Battle.id == battle_id,
                    Battle.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_battle_by_room(self, room_id: UUID) -> Optional[Battle]:
        """根据房间ID获取对战记录"""
        result = await self.db.execute(
            select(Battle)
            .options(selectinload(Battle.battle_actions))
            .where(
                and_(
                    Battle.room_id == room_id,
                    Battle.is_deleted == False
                )
            )
            .order_by(desc(Battle.create_time))
        )
        return result.scalar_one_or_none()

    async def get_current_battle_by_user(self, user_id: UUID) -> Optional[Battle]:
        """根据用户ID获取当前对战记录
        
        Args:
            user_id: 用户ID
            
        Returns:
            当前对战记录，如果用户没有进行中的对战则返回None
        """
        try:
            logger.info(f"开始获取用户当前对战 - user_id: {user_id}")
            
            # 通过RoomPlayer表查找用户当前所在的房间（包含房间信息）
            result = await self.db.execute(
                select(RoomPlayer)
                .options(selectinload(RoomPlayer.room))
                .where(
                    and_(
                        RoomPlayer.user_id == user_id,
                        RoomPlayer.is_deleted == False
                    )
                )
                .order_by(desc(RoomPlayer.create_time))
            )
            room_player = result.scalar_one_or_none()
            
            if not room_player:
                logger.info(f"用户不在任何房间中 - user_id: {user_id}")
                return None
            
            # 检查房间是否存在且未删除
            if not room_player.room or room_player.room.is_deleted:
                logger.info(f"用户所在的房间已被删除 - user_id: {user_id}, room_id: {room_player.room_id}")
                return None
            
            logger.info(f"用户所在房间 - user_id: {user_id}, room_id: {room_player.room_id}, player_status: {room_player.status}, room_status: {room_player.room.status}")
            
            # 根据房间ID获取最新的未删除对战记录
            battle = await self.get_battle_by_room(room_player.room_id)
            
            if not battle:
                logger.info(f"房间中没有未删除的对战记录 - user_id: {user_id}, room_id: {room_player.room_id}")
                
                # 如果房间状态是gaming但没有对战记录，说明状态不一致，需要清理
                if room_player.room.status == "gaming":
                    logger.warning(f"房间状态不一致：房间状态为gaming但没有对战记录，开始清理 - user_id: {user_id}, room_id: {room_player.room_id}")
                    await self._cleanup_inconsistent_room_state(room_player.room_id)
                
                return None
            
            logger.info(f"找到对战记录 - user_id: {user_id}, battle_id: {battle.id}, battle_status: {battle.status}, is_deleted: {battle.is_deleted}")
            
            # 检查对战状态：只允许coin、prepare、active状态（进行中的对战）
            if battle.status in ["coin", "prepare", "active"]:
                logger.info(f"找到用户当前进行中的对战 - user_id: {user_id}, battle_id: {battle.id}, room_id: {battle.room_id}, status: {battle.status}")
                return battle
            else:
                logger.info(f"对战状态不是进行中 - user_id: {user_id}, room_id: {room_player.room_id}, battle_status: {battle.status}")
                
                # 如果房间状态是gaming但对战状态不是进行中，说明状态不一致，需要清理
                if room_player.room.status == "gaming":
                    logger.warning(f"房间状态不一致：房间状态为gaming但对战状态为{battle.status}，开始清理 - user_id: {user_id}, room_id: {room_player.room_id}, battle_id: {battle.id}")
                    await self._cleanup_inconsistent_room_state(room_player.room_id)
                
                return None
                
        except Exception as e:
            logger.error(f"获取用户当前对战失败 - user_id: {user_id}, 错误: {str(e)}")
            return None

    async def _cleanup_inconsistent_room_state(self, room_id: UUID) -> None:
        """清理不一致的房间状态
        
        Args:
            room_id: 房间ID
        """
        try:
            logger.info(f"开始清理不一致的房间状态 - room_id: {room_id}")
            
            # 更新房间状态为waiting
            from ..models.room import Room
            room_result = await self.db.execute(
                select(Room).where(
                    and_(
                        Room.id == room_id,
                        Room.is_deleted == False
                    )
                )
            )
            room = room_result.scalar_one_or_none()
            if room:
                room.status = "waiting"
                room.update_time = datetime.now(timezone.utc)
                logger.info(f"房间状态已重置为waiting - room_id: {room_id}")
            
            # 更新房间玩家状态为waiting
            from ..models.room_player import RoomPlayer
            player_result = await self.db.execute(
                select(RoomPlayer).where(
                    and_(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
            )
            room_players = player_result.scalars().all()
            
            for player in room_players:
                player.status = "waiting"
                player.update_time = datetime.now(timezone.utc)
                logger.info(f"玩家状态已重置为waiting - room_id: {room_id}, user_id: {player.user_id}")
            
            # 提交事务
            await self.db.commit()
            logger.info(f"房间状态清理完成 - room_id: {room_id}, 玩家数: {len(room_players)}")
            
        except Exception as e:
            logger.error(f"清理房间状态失败 - room_id: {room_id}, 错误: {str(e)}")
            await self.db.rollback()

    async def update_battle_status(self, battle_id: UUID, status: str, 
                                 winner_id: UUID = None) -> Optional[Battle]:
        """更新对战状态
        
        Args:
            battle_id: 对战ID
            status: 新状态 (coin/prepare/active/finished)
            winner_id: 获胜者ID（仅在status为finished时需要）
            
        Returns:
            更新后的对战记录
        """
        try:
            logger.info(f"更新对战状态 - battle_id: {battle_id}, status: {status}")
            
            # 验证状态值
            valid_statuses = ["coin", "prepare", "active", "finished"]
            if status not in valid_statuses:
                raise ValueError(f"无效的对战状态，只能是: {', '.join(valid_statuses)}")
            
            battle = await self.get_battle(battle_id)
            if not battle:
                logger.warning(f"对战记录不存在 - battle_id: {battle_id}")
                return None
                
            battle.status = status
            battle.update_time = datetime.now(timezone.utc)
            
            if status == "finished" and winner_id:
                battle.winner_id = winner_id
                battle.end_time = datetime.now(timezone.utc)
                if battle.start_time:
                    battle.duration_seconds = int((battle.end_time - battle.start_time).total_seconds())
            
            await self.db.commit()
            await self.db.refresh(battle)
            
            logger.info(f"对战状态更新成功 - battle_id: {battle_id}, status: {status}")
            return battle
            
        except Exception as e:
            logger.error(f"更新对战状态失败 - battle_id: {battle_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"更新对战状态失败: {str(e)}")

    async def _notify_game_start(self, battle_id: str, room_id: str) -> None:
        """发送游戏开始通知"""
        try:
            # 更新房间和玩家状态为gaming
            await self._update_room_and_players_to_gaming(UUID(room_id))
            
            # 确保游戏状态已初始化（如果不存在则初始化）
            game_state = await self.game_state_manager.load_game_state(UUID(battle_id))
            if not game_state:
                logger.warning(f"游戏状态不存在，重新初始化 - battle_id: {battle_id}")
                # 如果游戏状态不存在，重新初始化
                game_state = await self.game_state_manager.initialize_game_state(
                    battle_id=UUID(battle_id),
                    room_id=UUID(room_id)
                )
                logger.info(f"游戏状态初始化完成 - battle_id: {battle_id}, 状态大小: {len(str(game_state))} 字符")
            
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送游戏开始消息（不包含游戏状态，前端通过HTTP接口获取）
            await connection_manager.send_game_start(battle_id, room_id)
            logger.info(f"游戏开始通知已发送: battle_id={battle_id}, room_id={room_id}")
            
        except Exception as e:
            logger.error(f"发送游戏开始通知时发生错误: {str(e)}")

    async def _update_room_and_players_to_gaming(self, room_id: UUID) -> None:
        """将房间和房间玩家状态更新为gaming"""
        try:
            logger.info(f"开始更新房间和玩家状态为gaming - room_id: {room_id}")
            
            # 更新房间状态
            from ..models.room import Room
            result = await self.db.execute(
                select(Room).where(
                    and_(
                        Room.id == room_id,
                        Room.is_deleted == False
                    )
                )
            )
            room = result.scalar_one_or_none()
            if room:
                room.status = "gaming"
                room.update_time = datetime.now(timezone.utc)
                logger.info(f"房间状态已更新为gaming - room_id: {room_id}")
            
            # 更新房间玩家状态
            from ..models.room_player import RoomPlayer
            result = await self.db.execute(
                select(RoomPlayer).where(
                    and_(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
            )
            room_players = result.scalars().all()
            
            for player in room_players:
                player.status = "gaming"
                player.update_time = datetime.now(timezone.utc)
                logger.info(f"玩家状态已更新为gaming - room_id: {room_id}, user_id: {player.user_id}")
            
            # 提交事务
            await self.db.commit()
            logger.info(f"房间和玩家状态更新完成 - room_id: {room_id}, 玩家数: {len(room_players)}")
            
        except Exception as e:
            logger.error(f"更新房间和玩家状态为gaming时发生错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"更新房间和玩家状态失败: {str(e)}")

    def _get_connection_manager(self):
        """获取WebSocket连接管理器实例（延迟初始化）"""
        if self._connection_manager is None:
            from src.core.websocket.connection_manager import ConnectionManager
            self._connection_manager = ConnectionManager()
        return self._connection_manager
    
    # 游戏状态管理便捷方法
    
    async def get_game_state(self, battle_id: UUID) -> Optional[Dict[str, Any]]:
        """获取游戏状态
        
        Args:
            battle_id: 对战ID
            
        Returns:
            游戏状态字典，如果不存在则返回None
        """
        return await self.game_state_manager.load_game_state(battle_id)
    
    async def update_game_state(self, battle_id: UUID, updates: Dict[str, Any]) -> bool:
        """更新游戏状态
        
        Args:
            battle_id: 对战ID
            updates: 要更新的字段字典
            
        Returns:
            更新是否成功
        """
        return await self.game_state_manager.update_game_state(battle_id, updates)
    
    async def validate_game_state(self, battle_id: UUID) -> tuple[bool, List[str]]:
        """验证游戏状态
        
        Args:
            battle_id: 对战ID
            
        Returns:
            (是否有效, 错误信息列表)
        """
        game_state = await self.get_game_state(battle_id)
        if not game_state:
            return False, ["游戏状态不存在"]
        return await self.game_state_manager.validate_game_state(game_state)
    
    async def get_player_field(self, battle_id: UUID, player_id: UUID) -> Optional[Dict[str, Any]]:
        """获取玩家场面
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            
        Returns:
            玩家场面数据，如果不存在则返回None
        """
        return await self.game_state_manager.get_player_field(battle_id, player_id)
    
    async def update_player_field(self, battle_id: UUID, player_id: UUID, field_data: Dict[str, Any]) -> bool:
        """更新玩家场面
        
        Args:
            battle_id: 对战ID
            player_id: 玩家ID
            field_data: 场面数据
            
        Returns:
            更新是否成功
        """
        return await self.game_state_manager.update_player_field(battle_id, player_id, field_data)
    
    async def next_turn(self, battle_id: UUID) -> bool:
        """进入下一回合
        
        Args:
            battle_id: 对战ID
            
        Returns:
            操作是否成功
        """
        return await self.game_state_manager.next_turn(battle_id)
    
    async def set_phase(self, battle_id: UUID, phase: str) -> bool:
        """设置回合阶段
        
        Args:
            battle_id: 对战ID
            phase: 回合阶段名称
            
        Returns:
            操作是否成功
        """
        return await self.game_state_manager.set_phase(battle_id, phase)
    
    async def get_game_state_for_reconnect(self, battle_id: UUID, player_id: UUID) -> Optional[Dict[str, Any]]:
        """获取用于断线重连的游戏状态
        
        Args:
            battle_id: 对战ID
            player_id: 重连玩家ID
            
        Returns:
            适合重连的游戏状态，如果不存在则返回None
        """
        return await self.game_state_manager.get_game_state_for_reconnect(battle_id, player_id)
    
    async def cleanup_game_state(self, battle_id: UUID) -> bool:
        """清理游戏状态（游戏结束时调用）
        
        Args:
            battle_id: 对战ID
            
        Returns:
            清理是否成功
        """
        return await self.game_state_manager.cleanup_game_state(battle_id)

    async def send_state_update_to_user(self, user_id: UUID, state_data: Dict[str, Any]) -> bool:
        """发送游戏状态更新消息给指定用户
        
        Args:
            user_id: 用户ID
            state_data: 游戏状态数据
            
        Returns:
            发送是否成功
        """
        try:
            logger.info(f"发送游戏状态更新消息给用户 - user_id: {user_id}")
            
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送状态更新消息
            success = await connection_manager.send_state_update(str(user_id), state_data)
            
            if success:
                logger.info(f"游戏状态更新消息发送成功 - user_id: {user_id}")
            else:
                logger.warning(f"游戏状态更新消息发送失败 - user_id: {user_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"发送游戏状态更新消息时发生错误 - user_id: {user_id}, 错误: {str(e)}")
            return False

    async def handle_surrender(self, battle_id: UUID, surrender_user_id: UUID) -> Dict[str, Any]:
        """
        处理用户投降
        
        Args:
            battle_id: 对战ID
            surrender_user_id: 投降用户ID
            
        Returns:
            投降处理结果
        """
        try:
            logger.info(f"处理用户投降 - battle_id: {battle_id}, surrender_user_id: {surrender_user_id}")
            
            # 获取对战信息
            battle = await self.get_battle(battle_id)
            if not battle:
                raise ValueError("对战记录不存在")
            
            # 检查对战状态
            if battle.status not in ["coin", "prepare", "active"]:
                raise ValueError("对战状态不允许投降")
            
            # 获取房间玩家信息
            result = await self.db.execute(
                select(RoomPlayer)
                .where(
                    and_(
                        RoomPlayer.room_id == battle.room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
                .order_by(RoomPlayer.player_order)
            )
            room_players = result.scalars().all()
            
            if len(room_players) != 2:
                raise ValueError("房间玩家数量不正确")
            
            # 确定投降者和获胜者
            surrender_player = None
            winner_player = None
            
            for player in room_players:
                if player.user_id == surrender_user_id:
                    surrender_player = player
                else:
                    winner_player = player
            
            if not surrender_player:
                raise ValueError("投降用户不在对战中")
            
            if not winner_player:
                raise ValueError("无法确定获胜者")
            
            # 更新对战状态
            updated_battle = await self.update_battle_status(
                battle_id=battle_id,
                status="finished",
                winner_id=winner_player.user_id
            )
            
            if not updated_battle:
                raise ValueError("更新对战状态失败")
            
            # 软删除对战记录（游戏正常结束）
            battle.is_deleted = True
            battle.update_time = datetime.now(timezone.utc)
            logger.info(f"软删除对战记录 - battle_id: {battle_id}")
            
            # 软删除房间和所有房间玩家记录（游戏正常结束）
            from ..models.room import Room
            room_result = await self.db.execute(
                select(Room).where(
                    and_(
                        Room.id == battle.room_id,
                        Room.is_deleted == False
                    )
                )
            )
            room = room_result.scalar_one_or_none()
            if room:
                # 软删除房间
                room.is_deleted = True
                room.status = "finished"  # 标记为已结束
                room.update_time = datetime.now(timezone.utc)
                logger.info(f"软删除房间 - room_id: {room.id}")
            
            # 软删除所有房间玩家记录
            for player in room_players:
                player.is_deleted = True
                player.status = "finished"  # 标记为已结束
                player.leave_time = datetime.now(timezone.utc)
                player.update_time = datetime.now(timezone.utc)
                logger.info(f"软删除房间玩家记录 - room_player_id: {player.id}, user_id: {player.user_id}")
            
            # 提交事务
            await self.db.commit()
            
            # 记录投降操作
            await self.record_battle_action(
                battle_id=battle_id,
                player_id=surrender_user_id,
                action_type="surrender",
                action_data={
                    "surrender_user_id": str(surrender_user_id),
                    "winner_user_id": str(winner_player.user_id),
                    "battle_status": "finished"
                }
            )
            
            # 发送投降通知
            connection_manager = self._get_connection_manager()
            
            # 发送给投降者
            await connection_manager.send_surrender_notification(
                str(surrender_user_id),
                battle_id=str(battle_id),
                message="您已投降"
            )
            
            # 发送给获胜者
            await connection_manager.send_surrender_notification(
                str(winner_player.user_id),
                battle_id=str(battle_id),
                message=f"对手已投降，您获胜了！"
            )
            
            # 发送房间解散通知（因为房间已被软删除）
            await connection_manager.send_room_dissolved(str(battle.room_id))
            
            logger.info(f"投降处理完成 - battle_id: {battle_id}, winner: {winner_player.user_id}, room_id: {battle.room_id} 已软删除")
            
            return {
                "success": True,
                "battle_id": str(battle_id),
                "room_id": str(battle.room_id),
                "surrender_user_id": str(surrender_user_id),
                "winner_id": str(winner_player.user_id),
                "battle_status": "finished"
            }
            
        except Exception as e:
            logger.error(f"处理投降失败 - battle_id: {battle_id}, surrender_user_id: {surrender_user_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"处理投降失败: {str(e)}")
    
    # 猜拳相关方法
    async def initialize_coin_game(self, room_id: UUID, redis_client) -> Dict[str, Any]:
        """
        初始化猜拳游戏
        
        Args:
            room_id: 房间ID
            redis_client: Redis客户端
            
        Returns:
            初始化结果
        """
        try:
            logger.info(f"初始化猜拳游戏 - room_id: {room_id}")
            
            # 初始化猜拳管理器
            self._init_coin_managers(redis_client)
            
            # 初始化猜拳游戏
            result = await self.coin_game_manager.initialize_coin_game(room_id)
            
            if result["success"]:
                # 获取房间信息以确定房主
                from ..models.room import Room
                room_result = await self.db.execute(
                    select(Room).where(Room.id == room_id)
                )
                room = room_result.scalar_one_or_none()
                if room:
                    # 获取房间玩家信息
                    room_players = await self._get_room_players(room_id)
                    if len(room_players) == 2:
                        owner_id = room.created_by  # 房主是房间创建者
                        # 找到非房主玩家
                        guest_id = None
                        for player in room_players:
                            if not is_user_room_owner(room, player.user_id):
                                guest_id = player.user_id
                                break
                        
                        if guest_id:
                            # 安排房主超时任务
                            await self.coin_timeout_manager.schedule_owner_timeout(room_id, owner_id, guest_id)
                            
                            logger.info(f"猜拳游戏初始化完成 - room_id: {room_id}, owner_id: {owner_id}, guest_id: {guest_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"初始化猜拳游戏失败 - room_id: {room_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def make_coin_choice(self, room_id: UUID, user_id: UUID, choice: int, redis_client) -> Dict[str, Any]:
        """
        用户做出猜拳选择
        
        Args:
            room_id: 房间ID
            user_id: 用户ID
            choice: 选择（1、2、3）
            redis_client: Redis客户端
            
        Returns:
            选择结果
        """
        try:
            logger.info(f"用户做出猜拳选择 - room_id: {room_id}, user_id: {user_id}, choice: {choice}")
            
            # 初始化猜拳管理器
            self._init_coin_managers(redis_client)
            
            # 检查对战状态
            battle = await self.get_battle_by_room(room_id)
            if not battle or battle.status != "coin":
                return {
                    "success": False,
                    "error": "当前不在猜拳阶段"
                }
            
            # 获取房间玩家信息
            room_players = await self._get_room_players(room_id)
            if len(room_players) != 2:
                return {
                    "success": False,
                    "error": "房间玩家数量不正确"
                }
            
            # 获取房间信息以确定房主
            from ..models.room import Room
            room_result = await self.db.execute(
                select(Room).where(Room.id == room_id)
            )
            room = room_result.scalar_one_or_none()
            if not room:
                return {
                    "success": False,
                    "error": "房间不存在"
                }
            
            # 判断是否是房主（统一调用）
            is_owner = is_user_room_owner(room, user_id)
            
            # 执行选择
            result = await self.coin_game_manager.make_choice_with_owner_id(
                room_id, 
                user_id, 
                choice, 
                is_owner, 
                room.created_by if not is_owner else None
            )
            
            if result["success"]:
                if is_owner:
                    # 房主选择成功，取消房主超时任务，安排非房主超时任务
                    # 找到非房主玩家
                    guest_id = None
                    for player in room_players:
                        if not is_user_room_owner(room, player.user_id):
                            guest_id = player.user_id
                            break
                    
                    if guest_id:
                        await self.coin_timeout_manager.cancel_owner_timeout(room_id)
                        await self.coin_timeout_manager.schedule_guest_timeout(room_id, user_id, guest_id)
                        
                        # 获取映射信息用于WebSocket消息
                        mapping = await self.coin_game_manager.get_mapping(room_id)
                        gesture = mapping[str(choice)] if mapping else "未知"
                        
                        # 发送update_state消息给房主（确认选择）
                        await self._send_update_state_to_owner(room_id, user_id, choice, gesture)
                        
                        # 发送update_state消息给非房主（房主已选择）
                        await self._send_update_state_to_guest(room_id, guest_id, choice)
                    
                else:
                    # 非房主选择成功
                    # 获取映射信息用于WebSocket消息
                    mapping = await self.coin_game_manager.get_mapping(room_id)
                    gesture = mapping[str(choice)] if mapping else "未知"
                    
                    # 发送update_state消息给非房主（确认选择）
                    await self._send_update_state_to_guest_after_choice(room_id, user_id, choice, gesture)
                    
                    # 发送update_state消息给房主（非房主已选择）
                    await self._send_update_state_to_owner_after_guest_choice(room_id, room.created_by, choice, gesture)
                    
                    # 处理猜拳结果（发送coin_result消息）
                    owner_id = room.created_by
                    await self._handle_coin_result(room_id, owner_id, user_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"用户猜拳选择失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_coin_game_status(self, room_id: UUID, redis_client) -> Dict[str, Any]:
        """
        获取猜拳游戏状态
        
        Args:
            room_id: 房间ID
            redis_client: Redis客户端
            
        Returns:
            猜拳游戏状态
        """
        try:
            # 初始化猜拳管理器
            self._init_coin_managers(redis_client)
            
            # 获取基础状态
            status = await self.coin_game_manager.get_coin_game_status(room_id)
            
            # 获取对战状态
            battle = await self.get_battle_by_room(room_id)
            if battle:
                status["battle_status"] = battle.status
                status["battle_id"] = str(battle.id)
            
            return status
            
        except Exception as e:
            logger.error(f"获取猜拳游戏状态失败 - room_id: {room_id}, 错误: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _get_room_players(self, room_id: UUID) -> List[RoomPlayer]:
        """获取房间玩家列表"""
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
        return result.scalars().all()
    
    async def _send_update_state_to_owner(self, room_id: UUID, owner_id: UUID, choice: int, gesture: str) -> None:
        """发送update_state消息给房主"""
        try:
            connection_manager = self._get_connection_manager()
            await connection_manager.send_state_update(
                str(owner_id),
                {
                    "type": "update_state",
                    "room_id": str(room_id),
                    "choice": choice,
                    "gesture": gesture,
                    "is_auto": False,
                    "message": "选择已保存，等待对手选择"
                }
            )
            logger.info(f"已发送update_state消息给房主 - room_id: {room_id}, owner_id: {owner_id}, choice: {choice}")
        except Exception as e:
            logger.error(f"发送update_state消息给房主失败 - room_id: {room_id}, owner_id: {owner_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_guest(self, room_id: UUID, guest_id: UUID, owner_choice: int) -> None:
        """发送update_state消息给非房主（房主已选择）"""
        try:
            connection_manager = self._get_connection_manager()
            await connection_manager.send_state_update(
                str(guest_id),
                {
                    "type": "update_state",
                    "room_id": str(room_id),
                    "owner_choice": owner_choice,
                    "message": "房主已做出选择，请尽快选择"
                }
            )
            logger.info(f"已发送update_state消息给非房主（房主已选择）- room_id: {room_id}, guest_id: {guest_id}")
        except Exception as e:
            logger.error(f"发送update_state消息给非房主失败 - room_id: {room_id}, guest_id: {guest_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_guest_after_choice(self, room_id: UUID, guest_id: UUID, choice: int, gesture: str) -> None:
        """发送update_state消息给非房主（非房主选择后）"""
        try:
            connection_manager = self._get_connection_manager()
            await connection_manager.send_state_update(
                str(guest_id),
                {
                    "type": "update_state",
                    "room_id": str(room_id),
                    "choice": choice,
                    "gesture": gesture,
                    "is_auto": False,
                    "message": "选择已保存，等待结果"
                }
            )
            logger.info(f"已发送update_state消息给非房主（选择后）- room_id: {room_id}, guest_id: {guest_id}, choice: {choice}")
        except Exception as e:
            logger.error(f"发送update_state消息给非房主失败 - room_id: {room_id}, guest_id: {guest_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_owner_after_guest_choice(self, room_id: UUID, owner_id: UUID, choice: int, gesture: str) -> None:
        """发送update_state消息给房主（非房主已选择）"""
        try:
            connection_manager = self._get_connection_manager()
            await connection_manager.send_state_update(
                str(owner_id),
                {
                    "type": "update_state",
                    "room_id": str(room_id),
                    "choice": choice,
                    "gesture": gesture,
                    "is_auto": False,
                    "message": "对手已做出选择，请尽快选择"
                }
            )
            logger.info(f"已发送update_state消息给房主（非房主已选择）- room_id: {room_id}, owner_id: {owner_id}, choice: {choice}")
        except Exception as e:
            logger.error(f"发送update_state消息给房主失败 - room_id: {room_id}, owner_id: {owner_id}, 错误: {str(e)}")
    
    async def _handle_coin_result(self, room_id: UUID, owner_id: UUID, guest_id: UUID, result: Dict[str, Any]) -> None:
        """处理猜拳结果"""
        try:
            logger.info(f"处理猜拳结果 - room_id: {room_id}, owner_id: {owner_id}, guest_id: {guest_id}")
            
            # 发送猜拳结果消息给双方
            connection_manager = self._get_connection_manager()
            await connection_manager.send_coin_result(
                str(owner_id),
                str(guest_id),
                {
                    "type": "coin_result",
                    "room_id": str(room_id),
                    "owner_choice": result["owner_choice"],
                    "guest_choice": result["guest_choice"],
                    "owner_gesture": result["owner_gesture"],
                    "guest_gesture": result["guest_gesture"],
                    "mapping": result["mapping"],
                    "winner": result["winner"],
                    "loser": result["loser"],
                    "result": result["result"],
                    "message": result["result"]
                }
            )
            
            # 确定获胜者和失败者
            winner_id = owner_id if result["winner"] == "owner" else guest_id
            loser_id = guest_id if result["winner"] == "owner" else owner_id
            
            # 安排胜方选择先攻后攻的超时任务（30秒）
            await self.coin_timeout_manager.schedule_first_player_timeout(room_id, winner_id, loser_id)
            
            logger.info(f"猜拳结果处理完成，等待胜方选择先攻后攻 - room_id: {room_id}, winner_id: {winner_id}")
            
        except Exception as e:
            logger.error(f"处理猜拳结果失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def _update_battle_after_coin(self, room_id: UUID, winner_id: UUID, first_player: UUID) -> None:
        """猜拳结束后更新对战状态"""
        try:
            # 获取对战记录
            battle = await self.get_battle_by_room(room_id)
            if not battle:
                logger.error(f"找不到对战记录 - room_id: {room_id}")
                return
            
            # 更新对战状态为prepare
            await self.update_battle_status(battle.id, "prepare")
            
            # 更新游戏状态中的优先出牌玩家
            game_state = await self.get_game_state(battle.id)
            if game_state:
                updates = {
                    "first_player": str(first_player),
                    "current_player": str(first_player)
                }
                await self.update_game_state(battle.id, updates)
            
            # 获取房间玩家信息用于发送WebSocket消息
            room_players = await self._get_room_players(room_id)
            if len(room_players) == 2:
                # 发送state_update消息给双方
                connection_manager = self._get_connection_manager()
                
                # 构建状态更新消息
                state_update_data = {
                    "type": "state_update",
                    "room_id": str(room_id),
                    "battle_id": str(battle.id),
                    "battle_status": "prepare",
                    "first_player": str(first_player),
                    "current_player": str(first_player),
                    "winner_id": str(winner_id),
                    "message": "猜拳结束，游戏进入准备阶段"
                }
                
                # 发送给所有房间玩家
                for player in room_players:
                    try:
                        await connection_manager.send_state_update(str(player.user_id), state_update_data)
                        logger.info(f"已发送state_update消息给玩家 - user_id: {player.user_id}, room_id: {room_id}")
                    except Exception as e:
                        logger.error(f"发送state_update消息给玩家失败 - user_id: {player.user_id}, room_id: {room_id}, 错误: {str(e)}")
            
            logger.info(f"对战状态已更新 - room_id: {room_id}, winner_id: {winner_id}, first_player: {first_player}")
            
        except Exception as e:
            logger.error(f"更新对战状态失败 - room_id: {room_id}, 错误: {str(e)}") 