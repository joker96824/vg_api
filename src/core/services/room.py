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
from ..models.friendship import Friendship

logger = logging.getLogger(__name__)

class RoomService:
    """房间服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # 延迟初始化连接管理器
        self._connection_manager = None

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
        room = result.scalar_one_or_none()
        
        # 临时修改密码字段，防止泄露
        if room and room.pass_word:
            room.pass_word = "********"
            logger.debug(f"房间 {room.id} 的密码已隐藏")
        
        return room

    async def _get_room_for_validation(self, room_id: UUID) -> Optional[Room]:
        """获取房间信息用于密码验证（不隐藏密码）"""
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

    async def get_rooms(self, params: RoomQueryParams, user_id: UUID) -> Tuple[int, List[Room]]:
        """获取房间列表"""
        try:
            logger.info(f"开始查询房间列表 - user_id: {user_id}, params: {params.dict()}")
            
            # 基础条件：只显示未删除的房间，状态为waiting
            conditions = [
                Room.is_deleted == False,
                Room.status == "waiting"
            ]
            
            # 关键词搜索
            if params.key_word:
                conditions.append(Room.room_name.ilike(f"%{params.key_word}%"))
                logger.info(f"添加关键词搜索条件: {params.key_word}")
            
            # 获取用户的好友ID列表
            friend_ids = []
            if params.friend_room or not params.friend_room:  # 总是需要获取好友列表
                result = await self.db.execute(
                    select(Friendship.friend_id)
                    .where(
                        and_(
                            Friendship.user_id == user_id,
                            Friendship.is_deleted == False,
                            Friendship.is_blocked == False
                        )
                    )
                )
                friend_ids = [str(friend_id) for friend_id in result.scalars().all()]
                logger.info(f"用户好友数量: {len(friend_ids)}")
            
            # 房间可见性条件
            if params.friend_room:
                # 只显示好友的房间
                if friend_ids:
                    conditions.append(Room.created_by.in_(friend_ids))
                else:
                    # 如果没有好友，返回空结果
                    conditions.append(Room.id == None)  # 永远不匹配的条件
                logger.info("只显示好友的房间")
            else:
                # 显示所有可见房间：public、ranked，以及好友的private房间
                if friend_ids:
                    conditions.append(
                        or_(
                            Room.room_type.in_(["public", "ranked"]),
                            and_(
                                Room.room_type == "private",
                                Room.created_by.in_(friend_ids)
                            )
                        )
                    )
                else:
                    # 如果没有好友，只显示公开和排位房间
                    conditions.append(Room.room_type.in_(["public", "ranked"]))
                logger.info("显示所有可见房间")

            # 计算总数
            total = await self.db.scalar(
                select(func.count()).select_from(Room).where(and_(*conditions))
            )
            logger.info(f"查询房间总数: {total}")

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
            logger.info(f"查询房间结果数量: {len(rooms)}")

            # 临时修改密码字段，防止泄露
            for room in rooms:
                if room.pass_word:
                    room.pass_word = "********"
                    logger.debug(f"房间 {room.id} 的密码已隐藏")

            return total, rooms
            
        except Exception as e:
            logger.error(f"查询房间列表失败 - user_id: {user_id}, 错误: {str(e)}")
            raise ValueError(f"查询房间列表失败: {str(e)}")

    async def update_room(self, room_id: UUID, room: RoomUpdate) -> Optional[Room]:
        """更新房间信息"""
        try:
            logger.info(f"开始更新房间 - room_id: {room_id}")
            
            db_room = await self._get_room_for_validation(room_id)
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
            
            # 发送房间信息变化通知
            await self._notify_room_info_update(str(room_id))
            
            logger.info(f"房间更新完成 - room_id: {room_id}")
            return db_room
            
        except Exception as e:
            logger.error(f"更新房间时发生错误 - room_id: {room_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"更新房间失败: {str(e)}")

    async def delete_room(self, room_id: UUID) -> bool:
        """删除房间（软删除）"""
        try:
            logger.info(f"开始删除房间 - room_id: {room_id}")
            
            db_room = await self._get_room_for_validation(room_id)
            if not db_room:
                logger.warning(f"房间不存在 - room_id: {room_id}")
                return False

            # 软删除房间
            db_room.is_deleted = True
            db_room.update_time = datetime.utcnow()
            
            # 级联软删除房间中的所有玩家记录
            result = await self.db.execute(
                select(RoomPlayer)
                .where(
                    and_(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.is_deleted == False
                    )
                )
            )
            room_players = result.scalars().all()
            
            for room_player in room_players:
                room_player.is_deleted = True
                room_player.update_time = datetime.utcnow()
                logger.info(f"软删除房间玩家记录 - room_player_id: {room_player.id}")
            
            await self.db.commit()
            logger.info(f"房间删除成功 - room_id: {room_id}, 删除玩家记录数: {len(room_players)}")
            
            # 发送房间解散通知
            await self._notify_room_dissolved(str(room_id))
            
            return True
            
        except Exception as e:
            logger.error(f"删除房间失败 - room_id: {room_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"删除房间失败: {str(e)}")

    async def join_room(self, room_id: UUID, user_id: UUID, password: str = None) -> Optional[RoomPlayer]:
        """加入房间"""
        try:
            logger.info(f"用户尝试加入房间 - room_id: {room_id}, user_id: {user_id}")
            
            # 检查房间是否存在（获取真实密码用于验证）
            db_room = await self._get_room_for_validation(room_id)
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
                
            # 检查密码
            if db_room.pass_word:
                if not password:
                    logger.warning(f"房间需要密码但用户未提供 - room_id: {room_id}")
                    raise ValueError("房间需要密码")
                if db_room.pass_word != password:
                    logger.warning(f"房间密码错误 - room_id: {room_id}")
                    raise ValueError("房间密码错误")
                
            # 检查用户是否已在房间中（未删除的记录）
            existing_player = await self.get_room_player_by_user(room_id, user_id)
            if existing_player:
                logger.warning(f"用户已在房间中 - room_id: {room_id}, user_id: {user_id}")
                raise ValueError("用户已在房间中")
                
            # 检查是否存在已删除的玩家记录（被踢出或离开的记录）
            deleted_player = await self._get_deleted_room_player_by_user(room_id, user_id)
            if deleted_player:
                # 重新激活已删除的玩家记录
                logger.info(f"重新激活已删除的玩家记录 - room_id: {room_id}, user_id: {user_id}")
                deleted_player.is_deleted = False
                deleted_player.status = "waiting"
                deleted_player.join_time = datetime.utcnow()
                deleted_player.leave_time = None
                deleted_player.update_time = datetime.utcnow()
                
                # 更新房间当前玩家数
                db_room.current_players += 1
                db_room.update_time = datetime.utcnow()
                
                await self.db.commit()
                
                # 发送房间玩家变化通知
                await self._notify_room_user_update(str(room_id))
                
                logger.info(f"用户重新加入房间成功 - room_id: {room_id}, user_id: {user_id}, player_order: {deleted_player.player_order}")
                return deleted_player
            else:
                # 创建新的房间玩家记录
                # 获取下一个玩家顺序
                next_order = await self.get_next_player_order(room_id)
                
                # 创建房间玩家记录
                room_player = RoomPlayer(
                    room_id=room_id,
                    user_id=user_id,
                    player_order=next_order,
                    status="waiting",
                    deck_id=None,  # 不设置卡组ID
                    join_time=datetime.utcnow(),
                    remark=""
                )
                self.db.add(room_player)
                
                # 更新房间当前玩家数
                db_room.current_players += 1
                db_room.update_time = datetime.utcnow()
                
                # 提交事务
                await self.db.commit()
                
                # 发送房间玩家变化通知
                await self._notify_room_user_update(str(room_id))
                
                logger.info(f"用户成功加入房间 - room_id: {room_id}, user_id: {user_id}, player_order: {room_player.player_order}")
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
                
            # 软删除玩家记录
            room_player.is_deleted = True
            room_player.leave_time = datetime.utcnow()
            room_player.status = "disconnected"
            room_player.update_time = datetime.utcnow()
            
            # 更新房间当前玩家数
            db_room = await self._get_room_for_validation(room_id)
            if db_room:
                db_room.current_players = max(0, db_room.current_players - 1)
                db_room.update_time = datetime.utcnow()
                
                # 如果房间空了，删除房间和所有玩家记录
                if db_room.current_players == 0:
                    logger.info(f"房间空了，删除房间和所有玩家记录 - room_id: {room_id}")
                    
                    # 软删除房间
                    db_room.is_deleted = True
                    
                    # 级联软删除房间中的所有玩家记录
                    result = await self.db.execute(
                        select(RoomPlayer)
                        .where(
                            and_(
                                RoomPlayer.room_id == room_id,
                                RoomPlayer.is_deleted == False
                            )
                        )
                    )
                    room_players = result.scalars().all()
                    
                    for room_player in room_players:
                        room_player.is_deleted = True
                        room_player.update_time = datetime.utcnow()
                        logger.info(f"软删除房间玩家记录 - room_player_id: {room_player.id}")
                    
                    logger.info(f"房间删除完成 - room_id: {room_id}, 删除玩家记录数: {len(room_players)}")
            
            await self.db.commit()
            
            # 根据情况发送不同的通知
            if db_room and db_room.current_players == 0:
                # 房间空了，发送房间解散通知
                await self._notify_room_dissolved(str(room_id))
            else:
                # 房间还有玩家，发送房间玩家变化通知
                await self._notify_room_user_update(str(room_id))
            
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

    async def _get_deleted_room_player_by_user(self, room_id: UUID, user_id: UUID) -> Optional[RoomPlayer]:
        """根据用户ID获取已删除的房间玩家记录"""
        result = await self.db.execute(
            select(RoomPlayer)
            .where(
                and_(
                    RoomPlayer.room_id == room_id,
                    RoomPlayer.user_id == user_id,
                    RoomPlayer.is_deleted == True
                )
            )
            .order_by(RoomPlayer.update_time.desc())  # 按更新时间倒序，取最新的记录
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

    async def kick_player(self, room_id: UUID, owner_id: UUID, target_user_id: UUID) -> bool:
        """踢出房间玩家"""
        try:
            logger.info(f"房主尝试踢出玩家 - room_id: {room_id}, owner_id: {owner_id}, target_user_id: {target_user_id}")
            
            # 检查房间是否存在
            db_room = await self._get_room_for_validation(room_id)
            if not db_room:
                logger.warning(f"房间不存在 - room_id: {room_id}")
                raise ValueError("房间不存在")
                
            # 检查权限：只有房主可以踢人
            if str(db_room.created_by) != str(owner_id):
                logger.warning(f"无权限踢出玩家 - room_id: {room_id}, owner_id: {owner_id}, room_created_by: {db_room.created_by}")
                raise ValueError("只有房主可以踢出玩家")
                
            # 检查目标用户是否在房间中
            target_player = await self.get_room_player_by_user(room_id, target_user_id)
            if not target_player:
                logger.warning(f"目标用户不在房间中 - room_id: {room_id}, target_user_id: {target_user_id}")
                raise ValueError("目标用户不在房间中")
                
            # 不能踢出房主自己
            if str(target_user_id) == str(owner_id):
                logger.warning(f"不能踢出房主自己 - room_id: {room_id}, owner_id: {owner_id}")
                raise ValueError("不能踢出房主自己")
                
            # 软删除目标玩家的房间记录
            target_player.is_deleted = True
            target_player.leave_time = datetime.utcnow()
            target_player.status = "kicked"
            target_player.update_time = datetime.utcnow()
            
            # 更新房间当前玩家数
            db_room.current_players = max(0, db_room.current_players - 1)
            db_room.update_time = datetime.utcnow()
            
            # 如果房间空了，删除房间
            if db_room.current_players == 0:
                logger.info(f"房间空了，删除房间 - room_id: {room_id}")
                db_room.is_deleted = True
                
                # 级联软删除房间中的所有玩家记录
                result = await self.db.execute(
                    select(RoomPlayer)
                    .where(
                        and_(
                            RoomPlayer.room_id == room_id,
                            RoomPlayer.is_deleted == False
                        )
                    )
                )
                room_players = result.scalars().all()
                
                for room_player in room_players:
                    room_player.is_deleted = True
                    room_player.update_time = datetime.utcnow()
                    logger.info(f"软删除房间玩家记录 - room_player_id: {room_player.id}")
                
                logger.info(f"房间删除完成 - room_id: {room_id}, 删除玩家记录数: {len(room_players)}")
            
            await self.db.commit()
            
            # 发送踢出通知给被踢出的用户
            await self._notify_room_kicked(str(room_id), str(target_user_id))
            
            # 根据情况发送不同的通知给其他玩家
            if db_room.current_players == 0:
                # 房间空了，发送房间解散通知
                await self._notify_room_dissolved(str(room_id))
            else:
                # 房间还有玩家，发送房间玩家变化通知
                await self._notify_room_user_update(str(room_id))
            
            logger.info(f"玩家踢出成功 - room_id: {room_id}, target_user_id: {target_user_id}")
            return True
            
        except Exception as e:
            logger.error(f"踢出玩家失败 - room_id: {room_id}, owner_id: {owner_id}, target_user_id: {target_user_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"踢出玩家失败: {str(e)}")

    async def change_player_status(self, room_id: UUID, user_id: UUID, status: str) -> Optional[RoomPlayer]:
        """改变房间玩家状态"""
        try:
            logger.info(f"用户尝试改变状态 - room_id: {room_id}, user_id: {user_id}, status: {status}")
            
            # 检查房间是否存在
            db_room = await self._get_room_for_validation(room_id)
            if not db_room:
                logger.warning(f"房间不存在 - room_id: {room_id}")
                raise ValueError("房间不存在")
                
            # 检查用户是否在房间中
            room_player = await self.get_room_player_by_user(room_id, user_id)
            if not room_player:
                logger.warning(f"用户不在房间中 - room_id: {room_id}, user_id: {user_id}")
                raise ValueError("用户不在房间中")
                
            # 验证状态值
            valid_statuses = ["waiting", "ready"]
            if status not in valid_statuses:
                logger.warning(f"无效的状态值 - status: {status}")
                raise ValueError(f"无效的状态值，只能是: {', '.join(valid_statuses)}")
                
            # 更新玩家状态
            old_status = room_player.status
            room_player.status = status
            room_player.update_time = datetime.utcnow()
            
            await self.db.commit()
            
            # 发送房间玩家变化通知
            await self._notify_room_user_update(str(room_id))
            
            logger.info(f"玩家状态改变成功 - room_id: {room_id}, user_id: {user_id}, 状态: {old_status} -> {status}")
            return room_player
            
        except Exception as e:
            logger.error(f"改变玩家状态失败 - room_id: {room_id}, user_id: {user_id}, status: {status}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"改变玩家状态失败: {str(e)}")

    async def start_game_loading(self, room_id: UUID, user_id: UUID) -> bool:
        """开始游戏加载"""
        try:
            logger.info(f"用户尝试开始游戏加载 - room_id: {room_id}, user_id: {user_id}")
            
            # 检查房间是否存在
            db_room = await self._get_room_for_validation(room_id)
            if not db_room:
                logger.warning(f"房间不存在 - room_id: {room_id}")
                raise ValueError("房间不存在")
                
            # 检查房间状态
            if db_room.status != "waiting":
                logger.warning(f"房间状态不允许开始游戏加载 - room_id: {room_id}, status: {db_room.status}")
                raise ValueError("房间状态不允许开始游戏加载")
                
            # 检查用户是否是房主
            room_player = await self.get_room_player_by_user(room_id, user_id)
            if not room_player:
                logger.warning(f"用户不在房间中 - room_id: {room_id}, user_id: {user_id}")
                raise ValueError("用户不在房间中")
                
            if room_player.player_order != 1:
                logger.warning(f"只有房主可以开始游戏加载 - room_id: {room_id}, user_id: {user_id}, player_order: {room_player.player_order}")
                raise ValueError("只有房主可以开始游戏加载")
                
            # 获取房间中的所有玩家
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
            
            # 检查所有玩家状态是否为ready
            for player in room_players:
                # 跳过房主的状态检查
                if player.player_order == 1:
                    continue
                    
                if player.status != "ready":
                    logger.warning(f"玩家状态不是ready - room_id: {room_id}, user_id: {player.user_id}, status: {player.status}")
                    raise ValueError(f"玩家 {player.user_id} 状态不是ready，无法开始游戏加载")
                    
            # 检查所有玩家的preset=0卡组
            from .deck import DeckService
            deck_service = DeckService(self.db)
            
            for player in room_players:
                # 获取用户的preset=0卡组
                battle_deck = await self._get_user_battle_deck(player.user_id)
                if not battle_deck:
                    logger.warning(f"用户没有preset=0的卡组 - user_id: {player.user_id}")
                    raise ValueError(f"玩家 {player.user_id} 没有出战卡组")
                    
                # 检查卡组合规性
                is_valid, problems = await deck_service.check_deck_validity(battle_deck.id)
                if not is_valid:
                    logger.warning(f"用户卡组不合规 - user_id: {player.user_id}, problems: {problems}")
                    raise ValueError(f"玩家 {player.user_id} 的卡组不合规: {'; '.join(problems)}")
                    
                # 更新房间玩家记录中的卡组ID
                player.deck_id = battle_deck.id
                player.update_time = datetime.utcnow()
                
            # 更新房间状态为loading
            db_room.status = "loading"
            db_room.update_time = datetime.utcnow()
            
            # 更新所有玩家状态为loading
            for player in room_players:
                player.status = "loading"
                player.update_time = datetime.utcnow()
                
            await self.db.commit()
            
            # 发送游戏加载通知
            await self._notify_game_loading(str(room_id))
            
            logger.info(f"游戏加载开始成功 - room_id: {room_id}, user_id: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"开始游戏加载失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"开始游戏加载失败: {str(e)}")

    async def _get_user_battle_deck(self, user_id: UUID) -> Optional[Deck]:
        """获取用户的出战卡组（preset=0的卡组）"""
        try:
            result = await self.db.execute(
                select(Deck)
                .where(
                    Deck.user_id == user_id,
                    Deck.preset == 0,
                    Deck.is_deleted == False,
                    Deck.is_valid == True  # 确保卡组合规
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取用户出战卡组失败 - user_id: {user_id}, 错误: {str(e)}")
            return None

    async def _notify_game_loading(self, room_id: str) -> None:
        """发送游戏加载通知"""
        try:
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送游戏加载消息
            await connection_manager.send_game_loading(room_id)
            logger.info(f"游戏加载通知已发送: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发送游戏加载通知时发生错误: {str(e)}")

    async def _notify_room_update(self, room_id: str) -> None:
        """发送房间更新WebSocket通知"""
        try:
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送房间更新消息
            await connection_manager.send_room_update(room_id)
            logger.info(f"房间更新通知已发送: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发送房间更新通知时发生错误: {str(e)}")

    async def _notify_room_user_update(self, room_id: str) -> None:
        """发送房间玩家变化通知"""
        try:
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送房间玩家变化消息
            await connection_manager.send_room_user_update(room_id)
            logger.info(f"房间玩家变化通知已发送: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发送房间玩家变化通知时发生错误: {str(e)}")

    async def _notify_room_dissolved(self, room_id: str) -> None:
        """发送房间解散通知"""
        try:
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送房间解散消息
            await connection_manager.send_room_dissolved(room_id)
            logger.info(f"房间解散通知已发送: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发送房间解散通知时发生错误: {str(e)}")

    async def _notify_room_info_update(self, room_id: str) -> None:
        """发送房间信息变化通知"""
        try:
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送房间信息变化消息
            await connection_manager.send_room_info_update(room_id)
            logger.info(f"房间信息变化通知已发送: 房间ID={room_id}")
            
        except Exception as e:
            logger.error(f"发送房间信息变化通知时发生错误: {str(e)}")

    async def _notify_room_kicked(self, room_id: str, target_user_id: str) -> None:
        """发送房间踢出通知"""
        try:
            # 获取WebSocket连接管理器实例
            connection_manager = self._get_connection_manager()
            
            # 发送房间踢出消息
            await connection_manager.send_room_kicked(room_id, target_user_id)
            logger.info(f"房间踢出通知已发送: 房间ID={room_id}, 目标用户ID={target_user_id}")
            
        except Exception as e:
            logger.error(f"发送房间踢出通知时发生错误: {str(e)}")

    def _get_connection_manager(self):
        """获取WebSocket连接管理器实例（延迟初始化）"""
        if self._connection_manager is None:
            from src.core.websocket.connection_manager import ConnectionManager
            self._connection_manager = ConnectionManager()
        return self._connection_manager


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