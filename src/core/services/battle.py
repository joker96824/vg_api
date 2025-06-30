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

logger = logging.getLogger(__name__)

class BattleService:
    """对战服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # 延迟初始化连接管理器
        self._connection_manager = None

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
                current_game_state={},  # 默认为空对象
                create_user_id=None,  # 暂时不设置，后续可以添加
                update_user_id=None,  # 暂时不设置，后续可以添加
                remark=f"从房间 {room_id} 创建的对战"
            )
            self.db.add(battle)
            await self.db.commit()
            await self.db.refresh(battle)
            
            logger.info(f"对战记录创建成功 - battle_id: {battle.id}")
            return battle
            
        except Exception as e:
            logger.error(f"创建对战记录失败 - room_id: {room_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"创建对战记录失败: {str(e)}")

    async def record_battle_action(self, battle_id: UUID, player_id: UUID, 
                                 action_type: str, action_data: Dict[str, Any]) -> BattleAction:
        """记录对战操作"""
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
            
            # 创建操作记录
            battle_action = BattleAction(
                battle_id=battle_id,
                action_sequence=next_sequence,
                player_id=player_id,
                action_type=action_type,
                action_data=action_data,
                game_state_after={},  # 暂时为空，后续可以添加
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
            
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送游戏开始消息
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