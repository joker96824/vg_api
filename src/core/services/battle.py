from datetime import datetime
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

logger = logging.getLogger(__name__)

class BattleService:
    """对战服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # 延迟初始化连接管理器
        self._connection_manager = None
        # 初始化游戏状态管理器
        self.game_state_manager = GameStateManager(db)

    async def create_battle_from_room(self, room_id: UUID, battle_type: str = "casual") -> Battle:
        """从房间创建对战记录"""
        try:
            logger.info(f"开始创建对战记录 - room_id: {room_id}, battle_type: {battle_type}")
            
            # 创建对战记录
            battle = Battle(
                room_id=room_id,
                battle_type=battle_type,
                status="active",
                start_time=datetime.utcnow(),
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
                timestamp=datetime.utcnow(),
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

    async def update_battle_status(self, battle_id: UUID, status: str, 
                                 winner_id: UUID = None) -> Optional[Battle]:
        """更新对战状态"""
        try:
            logger.info(f"更新对战状态 - battle_id: {battle_id}, status: {status}")
            
            battle = await self.get_battle(battle_id)
            if not battle:
                logger.warning(f"对战记录不存在 - battle_id: {battle_id}")
                return None
                
            battle.status = status
            battle.update_time = datetime.utcnow()
            
            if status == "finished" and winner_id:
                battle.winner_id = winner_id
                battle.end_time = datetime.utcnow()
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
            
            # 获取游戏状态
            game_state = await self.game_state_manager.load_game_state(UUID(battle_id))
            if not game_state:
                logger.warning(f"游戏状态不存在，重新初始化 - battle_id: {battle_id}")
                # 如果游戏状态不存在，重新初始化
                game_state = await self.game_state_manager.initialize_game_state(
                    battle_id=UUID(battle_id),
                    room_id=UUID(room_id)
                )
            
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送游戏开始消息（包含游戏状态）
            await connection_manager.send_game_start_with_state(battle_id, room_id, game_state)
            logger.info(f"游戏开始通知已发送: battle_id={battle_id}, room_id={room_id}, 游戏状态大小: {len(str(game_state))} 字符")
            
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
                room.update_time = datetime.utcnow()
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
                player.update_time = datetime.utcnow()
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