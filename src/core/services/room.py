from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import logging

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.room import Room
from ..models.room_player import RoomPlayer
from ..models.user import User
from ..models.deck import Deck
from ..schemas.room import RoomCreate, RoomUpdate, RoomPlayerCreate, RoomPlayerUpdate, RoomQueryParams, RoomPlayerQueryParams

logger = logging.getLogger(__name__)

class RoomService:
    """房间服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room(self, room: RoomCreate, user_id: UUID) -> Room:
        """创建房间"""
        try:
            logger.info(f"开始创建房间 - 用户ID: {user_id}")
            
            # 创建房间
            db_room = Room(
                room_name=room.room_name,
                room_type=room.room_type,
                status=room.status,
                max_players=room.max_players,
                current_players=1,  # 创建者自动加入
                game_mode=room.game_mode,
                game_settings=room.game_settings,
                pass_word=room.pass_word,
                created_by=user_id,
                remark=room.remark
            )
            self.db.add(db_room)
            await self.db.commit()
            await self.db.refresh(db_room)
            
            logger.info(f"房间创建成功 - 房间ID: {db_room.id}")
            
            # 创建者自动加入房间作为房主
            room_player = RoomPlayer(
                room_id=db_room.id,
                user_id=user_id,
                player_order=1,  # 房主为1号位
                status="waiting",
                join_time=datetime.utcnow(),
                remark=""
            )
            self.db.add(room_player)
            await self.db.commit()
            
            logger.info(f"房主加入房间成功 - 房间ID: {db_room.id}, 用户ID: {user_id}")
            
            # 重新查询以加载关系
            result = await self.db.execute(
                select(Room)
                .options(selectinload(Room.room_players))
                .where(Room.id == db_room.id)
            )
            db_room = result.scalar_one()
            
            return db_room
            
        except Exception as e:
            logger.error(f"创建房间失败 - 用户ID: {user_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"创建房间失败: {str(e)}")

    async def get_room(self, room_id: UUID) -> Optional[Room]:
        """获取房间详情"""
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.room_players))
            .where(
                and_(
                    Room.id == room_id,
                    Room.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_rooms(self, params: RoomQueryParams) -> Tuple[int, List[Room]]:
        """获取房间列表"""
        # 构建查询条件
        conditions = [Room.is_deleted == False]
        
        if params.room_type:
            conditions.append(Room.room_type == params.room_type)
        if params.status:
            conditions.append(Room.status == params.status)
        if params.game_mode:
            conditions.append(Room.game_mode == params.game_mode)

        # 计算总数
        total = await self.db.scalar(
            select(func.count()).select_from(Room).where(and_(*conditions))
        )
        logger.debug(f"查询房间总数: {total}")

        # 获取分页数据
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.room_players))
            .where(and_(*conditions))
            .order_by(desc(Room.create_time))
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        rooms = result.scalars().all()
        logger.debug(f"查询房间结果数量: {len(rooms)}")

        return total, rooms

    async def update_room(self, room_id: UUID, room: RoomUpdate) -> Optional[Room]:
        """更新房间信息"""
        try:
            logger.info(f"开始更新房间 - room_id: {room_id}")
            
            db_room = await self.get_room(room_id)
            if not db_room:
                logger.warning(f"未找到房间 - room_id: {room_id}")
                return None
                
            # 更新房间信息
            update_data = room.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_room, field, value)
                logger.info(f"更新房间字段: {field} = {value}")

            db_room.update_time = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(db_room)
            
            logger.info(f"房间更新完成 - room_id: {room_id}")
            return db_room
            
        except Exception as e:
            logger.error(f"更新房间时发生错误 - room_id: {room_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"更新房间失败: {str(e)}")

    async def delete_room(self, room_id: UUID) -> bool:
        """删除房间（软删除）"""
        db_room = await self.get_room(room_id)
        if not db_room:
            return False

        db_room.is_deleted = True
        db_room.update_time = datetime.utcnow()
        await self.db.commit()
        return True

    async def join_room(self, room_id: UUID, user_id: UUID, deck_id: Optional[UUID] = None) -> Optional[RoomPlayer]:
        """加入房间"""
        try:
            logger.info(f"用户尝试加入房间 - room_id: {room_id}, user_id: {user_id}")
            
            # 检查房间是否存在
            db_room = await self.get_room(room_id)
            if not db_room:
                logger.warning(f"房间不存在 - room_id: {room_id}")
                return None
                
            # 检查房间状态
            if db_room.status != "waiting":
                logger.warning(f"房间状态不允许加入 - room_id: {room_id}, status: {db_room.status}")
                raise ValueError("房间状态不允许加入")
                
            # 检查房间是否已满
            if db_room.current_players >= db_room.max_players:
                logger.warning(f"房间已满 - room_id: {room_id}, current: {db_room.current_players}, max: {db_room.max_players}")
                raise ValueError("房间已满")
                
            # 检查用户是否已在房间中
            existing_player = await self.get_room_player_by_user(room_id, user_id)
            if existing_player:
                logger.warning(f"用户已在房间中 - room_id: {room_id}, user_id: {user_id}")
                raise ValueError("用户已在房间中")
                
            # 获取下一个玩家顺序
            next_order = await self.get_next_player_order(room_id)
            
            # 创建房间玩家记录
            room_player = RoomPlayer(
                room_id=room_id,
                user_id=user_id,
                player_order=next_order,
                status="waiting",
                deck_id=deck_id,
                join_time=datetime.utcnow(),
                remark=""
            )
            self.db.add(room_player)
            
            # 更新房间当前玩家数
            db_room.current_players += 1
            db_room.update_time = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(room_player)
            
            logger.info(f"用户成功加入房间 - room_id: {room_id}, user_id: {user_id}, order: {next_order}")
            return room_player
            
        except Exception as e:
            logger.error(f"加入房间失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"加入房间失败: {str(e)}")

    async def leave_room(self, room_id: UUID, user_id: UUID) -> bool:
        """离开房间"""
        try:
            logger.info(f"用户尝试离开房间 - room_id: {room_id}, user_id: {user_id}")
            
            # 获取房间玩家记录
            room_player = await self.get_room_player_by_user(room_id, user_id)
            if not room_player:
                logger.warning(f"用户不在房间中 - room_id: {room_id}, user_id: {user_id}")
                return False
                
            # 更新离开时间
            room_player.leave_time = datetime.utcnow()
            room_player.status = "disconnected"
            room_player.update_time = datetime.utcnow()
            
            # 更新房间当前玩家数
            db_room = await self.get_room(room_id)
            if db_room:
                db_room.current_players = max(0, db_room.current_players - 1)
                db_room.update_time = datetime.utcnow()
                
                # 如果房间空了，删除房间
                if db_room.current_players == 0:
                    db_room.is_deleted = True
                    logger.info(f"房间空了，删除房间 - room_id: {room_id}")
            
            await self.db.commit()
            
            logger.info(f"用户成功离开房间 - room_id: {room_id}, user_id: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"离开房间失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"离开房间失败: {str(e)}")

    async def get_room_player_by_user(self, room_id: UUID, user_id: UUID) -> Optional[RoomPlayer]:
        """根据用户ID获取房间玩家记录"""
        result = await self.db.execute(
            select(RoomPlayer)
            .where(
                and_(
                    RoomPlayer.room_id == room_id,
                    RoomPlayer.user_id == user_id,
                    RoomPlayer.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_next_player_order(self, room_id: UUID) -> int:
        """获取下一个玩家顺序"""
        result = await self.db.execute(
            select(func.max(RoomPlayer.player_order))
            .where(
                and_(
                    RoomPlayer.room_id == room_id,
                    RoomPlayer.is_deleted == False
                )
            )
        )
        max_order = result.scalar()
        return (max_order or 0) + 1

    async def get_room_players_info(self, room_id: UUID) -> Optional[Dict[str, Any]]:
        """获取房间玩家详细信息"""
        try:
            logger.info(f"获取房间玩家信息 - room_id: {room_id}")
            
            # 获取房间信息
            room = await self.get_room(room_id)
            if not room:
                logger.warning(f"房间不存在 - room_id: {room_id}")
                return None
            
            # 获取房间玩家列表，包含用户和卡组信息
            result = await self.db.execute(
                select(RoomPlayer)
                .options(
                    selectinload(RoomPlayer.user),
                    selectinload(RoomPlayer.deck)
                )
                .where(
                    and_(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
                .order_by(RoomPlayer.player_order)
            )
            room_players = result.scalars().all()
            
            # 构建玩家详细信息
            players_info = []
            for player in room_players:
                player_info = {
                    "id": player.id,
                    "room_id": player.room_id,
                    "user_id": player.user_id,
                    "player_order": player.player_order,
                    "status": player.status,
                    "deck_id": player.deck_id,
                    "join_time": player.join_time,
                    "leave_time": player.leave_time,
                    "remark": player.remark,
                    "user_info": None,
                    "deck_info": None
                }
                
                # 添加用户信息
                if player.user:
                    player_info["user_info"] = {
                        "id": str(player.user.id),
                        "nickname": player.user.nickname,
                        "avatar": player.user.avatar
                    }
                
                # 添加卡组信息
                if player.deck:
                    player_info["deck_info"] = {
                        "id": str(player.deck.id),
                        "deck_name": player.deck.deck_name,
                        "deck_description": player.deck.deck_description,
                        "is_valid": player.deck.is_valid
                    }
                
                players_info.append(player_info)
            
            # 构建返回结果
            result_data = {
                "room_id": str(room.id),
                "room_name": room.room_name,
                "total_players": len(players_info),
                "max_players": room.max_players,
                "players": players_info
            }
            
            logger.info(f"获取房间玩家信息成功 - room_id: {room_id}, 玩家数: {len(players_info)}")
            return result_data
            
        except Exception as e:
            logger.error(f"获取房间玩家信息失败 - room_id: {room_id}, 错误: {str(e)}")
            raise ValueError(f"获取房间玩家信息失败: {str(e)}")

    async def check_user_room_status(self, user_id: UUID) -> Dict[str, Any]:
        """检查用户房间状态"""
        try:
            logger.info(f"检查用户房间状态 - user_id: {user_id}")
            
            # 查询用户是否在房间中且未删除
            result = await self.db.execute(
                select(RoomPlayer)
                .options(selectinload(RoomPlayer.room))
                .where(
                    and_(
                        RoomPlayer.user_id == user_id,
                        RoomPlayer.is_deleted == False
                    )
                )
                .order_by(RoomPlayer.create_time.desc())  # 按创建时间倒序，取最新的
            )
            room_players = result.scalars().all()
            
            if not room_players:
                logger.info(f"用户不在任何房间中 - user_id: {user_id}")
                return {
                    "in_room": False,
                    "room_id": None,
                    "room_name": None,
                    "player_order": None,
                    "status": None,
                    "join_time": None
                }
            
            # 取最新的房间记录
            room_player = room_players[0]
            
            # 检查房间是否存在且未删除
            if not room_player.room or room_player.room.is_deleted:
                logger.info(f"用户所在的房间已被删除 - user_id: {user_id}, room_id: {room_player.room_id}")
                return {
                    "in_room": False,
                    "room_id": None,
                    "room_name": None,
                    "player_order": None,
                    "status": None,
                    "join_time": None
                }
            
            # 用户在房间中
            result_data = {
                "in_room": True,
                "room_id": str(room_player.room_id),
                "room_name": room_player.room.room_name,
                "player_order": room_player.player_order,
                "status": room_player.status,
                "join_time": room_player.join_time
            }
            
            logger.info(f"用户正在房间中 - user_id: {user_id}, room_id: {room_player.room_id}, room_name: {room_player.room.room_name}")
            return result_data
            
        except Exception as e:
            logger.error(f"检查用户房间状态失败 - user_id: {user_id}, 错误: {str(e)}")
            raise ValueError(f"检查用户房间状态失败: {str(e)}")


class RoomPlayerService:
    """房间玩家服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room_player(self, room_player: RoomPlayerCreate) -> RoomPlayer:
        """创建房间玩家"""
        db_room_player = RoomPlayer(
            room_id=room_player.room_id,
            user_id=room_player.user_id,
            player_order=room_player.player_order,
            status=room_player.status,
            deck_id=room_player.deck_id,
            join_time=datetime.utcnow(),
            remark=room_player.remark or ""
        )
        self.db.add(db_room_player)
        await self.db.commit()
        await self.db.refresh(db_room_player)
        return db_room_player

    async def get_room_player(self, room_player_id: UUID) -> Optional[RoomPlayer]:
        """获取房间玩家详情"""
        result = await self.db.execute(
            select(RoomPlayer)
            .where(
                and_(
                    RoomPlayer.id == room_player_id,
                    RoomPlayer.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_room_players(self, params: RoomPlayerQueryParams) -> Tuple[int, List[RoomPlayer]]:
        """获取房间玩家列表"""
        # 构建查询条件
        conditions = [RoomPlayer.is_deleted == False]
        
        if params.room_id:
            conditions.append(RoomPlayer.room_id == params.room_id)
        if params.user_id:
            conditions.append(RoomPlayer.user_id == params.user_id)
        if params.status:
            conditions.append(RoomPlayer.status == params.status)

        # 计算总数
        total = await self.db.scalar(
            select(func.count()).select_from(RoomPlayer).where(and_(*conditions))
        )

        # 获取分页数据
        result = await self.db.execute(
            select(RoomPlayer)
            .where(and_(*conditions))
            .order_by(RoomPlayer.player_order)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        room_players = result.scalars().all()

        return total, room_players

    async def update_room_player(self, room_player_id: UUID, room_player: RoomPlayerUpdate) -> Optional[RoomPlayer]:
        """更新房间玩家信息"""
        db_room_player = await self.get_room_player(room_player_id)
        if not db_room_player:
            return None

        # 更新房间玩家信息
        update_data = room_player.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_room_player, field, value)

        db_room_player.update_time = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(db_room_player)
        return db_room_player

    async def delete_room_player(self, room_player_id: UUID) -> bool:
        """删除房间玩家（软删除）"""
        db_room_player = await self.get_room_player(room_player_id)
        if not db_room_player:
            return False

        db_room_player.is_deleted = True
        db_room_player.update_time = datetime.utcnow()
        await self.db.commit()
        return True 