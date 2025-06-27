import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..utils.redis import set_key, get_key, delete_key, key_exists
from ..models.room import Room
from ..models.room_player import RoomPlayer
from ..schemas.room import RoomCreate

logger = logging.getLogger(__name__)

class MatchService:
    """匹配服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.match_queue_key = "match_queue"
        self.match_timeout = 1800  # 匹配超时时间（30分钟）
        self.pending_matches_key = "pending_matches"  # 待确认的匹配
        
    async def join_match_queue(self, user_id: UUID, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """加入匹配队列"""
        try:
            logger.info(f"用户加入匹配队列 - user_id: {user_id}")
            
            # 检查用户是否已在匹配队列中
            if await self._is_user_in_queue(user_id):
                logger.warning(f"用户已在匹配队列中 - user_id: {user_id}")
                return {
                    "success": False,
                    "message": "用户已在匹配队列中",
                    "match_id": None
                }
            
            # 检查用户是否已在房间中
            if await self._is_user_in_room(user_id):
                logger.warning(f"用户已在房间中 - user_id: {user_id}")
                return {
                    "success": False,
                    "message": "用户已在房间中",
                    "match_id": None
                }
            
            # 生成匹配ID
            match_id = str(uuid.uuid4())
            
            # 构建匹配信息
            match_info = {
                "user_id": str(user_id),
                "match_id": match_id,
                "join_time": datetime.utcnow().isoformat(),
                "user_info": user_info
            }
            
            # 将用户加入匹配队列
            await self._add_to_queue(match_info)
            
            # 尝试匹配
            match_result = await self._try_match()
            
            if match_result["matched"]:
                # 匹配成功，发送确认通知
                await self._send_match_confirmation(match_result["users"])
                return {
                    "success": True,
                    "message": "匹配成功，等待确认",
                    "match_id": match_id,
                    "room_id": None,
                    "matched_users": match_result["users"]
                }
            else:
                # 匹配中，等待其他玩家
                return {
                    "success": True,
                    "message": "已加入匹配队列，等待其他玩家",
                    "match_id": match_id,
                    "room_id": None,
                    "matched_users": None
                }
                
        except Exception as e:
            logger.error(f"加入匹配队列失败 - user_id: {user_id}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"加入匹配队列失败: {str(e)}",
                "match_id": None
            }
    
    async def confirm_match(self, user_id: UUID, match_id: str, confirm: bool) -> Dict[str, Any]:
        """确认或拒绝匹配"""
        try:
            logger.info(f"用户确认匹配 - user_id: {user_id}, match_id: {match_id}, confirm: {confirm}")
            
            # 获取待确认的匹配信息
            pending_match = await self._get_pending_match(match_id)
            if not pending_match:
                return {
                    "success": False,
                    "message": "匹配已过期或不存在"
                }
            
            # 检查用户是否在匹配中
            user_in_match = any(user["user_id"] == str(user_id) for user in pending_match["users"])
            if not user_in_match:
                return {
                    "success": False,
                    "message": "用户不在此匹配中"
                }
            
            # 更新用户确认状态
            await self._update_user_confirmation(match_id, user_id, confirm)
            
            if confirm:
                # 用户确认，检查是否所有人都确认了
                all_confirmed = await self._check_all_confirmed(match_id)
                if all_confirmed:
                    # 所有人确认，创建房间
                    room_data = await self._create_room_from_confirmed_match(match_id)
                    await self._remove_pending_match(match_id)
                    return {
                        "success": True,
                        "message": "匹配确认成功，房间已创建",
                        "room_id": str(room_data["room_id"]),
                        "room_name": room_data["room_name"]
                    }
                else:
                    return {
                        "success": True,
                        "message": "已确认，等待其他玩家确认"
                    }
            else:
                # 用户拒绝，处理拒绝逻辑
                await self._handle_match_rejection(match_id, user_id)
                return {
                    "success": True,
                    "message": "已拒绝匹配"
                }
                
        except Exception as e:
            logger.error(f"确认匹配失败 - user_id: {user_id}, match_id: {match_id}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"确认匹配失败: {str(e)}"
            }
    
    async def leave_match_queue(self, user_id: UUID) -> Dict[str, Any]:
        """离开匹配队列"""
        try:
            logger.info(f"用户离开匹配队列 - user_id: {user_id}")
            
            # 从队列中移除用户
            removed = await self._remove_from_queue(user_id)
            
            if removed:
                return {
                    "success": True,
                    "message": "已离开匹配队列"
                }
            else:
                return {
                    "success": False,
                    "message": "用户不在匹配队列中"
                }
                
        except Exception as e:
            logger.error(f"离开匹配队列失败 - user_id: {user_id}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"离开匹配队列失败: {str(e)}"
            }
    
    async def cancel_user_match(self, user_id: UUID) -> Dict[str, Any]:
        """取消用户匹配（用户登录失效时调用）"""
        try:
            logger.info(f"取消用户匹配 - user_id: {user_id}")
            
            # 从队列中移除用户
            removed = await self._remove_from_queue(user_id)
            
            if removed:
                logger.info(f"用户匹配已取消 - user_id: {user_id}")
                return {
                    "success": True,
                    "message": "用户匹配已取消"
                }
            else:
                logger.info(f"用户不在匹配队列中 - user_id: {user_id}")
                return {
                    "success": True,
                    "message": "用户不在匹配队列中"
                }
                
        except Exception as e:
            logger.error(f"取消用户匹配失败 - user_id: {user_id}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"取消用户匹配失败: {str(e)}"
            }
    
    async def get_match_status(self, user_id: UUID) -> Dict[str, Any]:
        """获取匹配状态"""
        try:
            # 检查用户是否在匹配队列中
            in_queue = await self._is_user_in_queue(user_id)
            
            if in_queue:
                # 获取队列中的用户信息
                queue_info = await self._get_queue_info()
                user_position = await self._get_user_position(user_id)
                
                return {
                    "in_queue": True,
                    "queue_size": len(queue_info),
                    "position": user_position,
                    "estimated_wait_time": user_position * 10  # 简单估算等待时间
                }
            else:
                return {
                    "in_queue": False,
                    "queue_size": 0,
                    "position": 0,
                    "estimated_wait_time": 0
                }
                
        except Exception as e:
            logger.error(f"获取匹配状态失败 - user_id: {user_id}, 错误: {str(e)}")
            return {
                "in_queue": False,
                "queue_size": 0,
                "position": 0,
                "estimated_wait_time": 0,
                "error": str(e)
            }
    
    async def cleanup_match_queue(self) -> Dict[str, Any]:
        """手动清理匹配队列（管理员功能）"""
        try:
            logger.info("开始手动清理匹配队列")
            
            # 清空匹配队列
            delete_key(self.match_queue_key)
            delete_key(self.pending_matches_key)
            
            logger.info("匹配队列清理完成")
            return {
                "success": True,
                "message": "匹配队列清理完成"
            }
                
        except Exception as e:
            logger.error(f"清理匹配队列失败: {str(e)}")
            return {
                "success": False,
                "message": f"清理匹配队列失败: {str(e)}"
            }
    
    async def cleanup_expired_matches(self) -> Dict[str, Any]:
        """清理过期的匹配记录"""
        try:
            logger.info("开始清理过期的匹配记录")
            queue_info = await self._get_queue_info()
            current_time = datetime.utcnow()
            
            # 过滤掉过期的匹配记录
            valid_matches = []
            cleaned_count = 0
            for match_info in queue_info:
                join_time = datetime.fromisoformat(match_info["join_time"])
                if (current_time - join_time).total_seconds() < self.match_timeout:
                    valid_matches.append(match_info)
                else:
                    logger.info(f"清理过期匹配记录 - user_id: {match_info['user_id']}")
                    cleaned_count += 1
            
            if cleaned_count > 0:
                await self._save_queue_info(valid_matches)
                logger.info(f"清理了 {cleaned_count} 条过期匹配记录")
                return {
                    "success": True,
                    "message": f"清理了 {cleaned_count} 条过期匹配记录",
                    "cleaned_count": cleaned_count
                }
            else:
                return {
                    "success": True,
                    "message": "没有过期的匹配记录",
                    "cleaned_count": 0
                }
                
        except Exception as e:
            logger.error(f"清理过期匹配记录时发生错误: {str(e)}")
            return {
                "success": False,
                "message": f"清理过期匹配记录失败: {str(e)}"
            }
    
    async def _is_user_in_queue(self, user_id: UUID) -> bool:
        """检查用户是否在匹配队列中"""
        queue_info = await self._get_queue_info()
        return any(user["user_id"] == str(user_id) for user in queue_info)
    
    async def _is_user_in_room(self, user_id: UUID) -> bool:
        """检查用户是否已在房间中"""
        result = await self.db.execute(
            select(RoomPlayer)
            .where(
                RoomPlayer.user_id == user_id,
                RoomPlayer.is_deleted == False
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def _add_to_queue(self, match_info: Dict[str, Any]):
        """将用户添加到匹配队列"""
        queue_info = await self._get_queue_info()
        queue_info.append(match_info)
        await self._save_queue_info(queue_info)
        logger.info(f"用户已添加到匹配队列 - user_id: {match_info['user_id']}")
    
    async def _remove_from_queue(self, user_id: UUID) -> bool:
        """从匹配队列中移除用户"""
        queue_info = await self._get_queue_info()
        original_size = len(queue_info)
        
        # 移除指定用户
        queue_info = [user for user in queue_info if user["user_id"] != str(user_id)]
        
        if len(queue_info) < original_size:
            await self._save_queue_info(queue_info)
            logger.info(f"用户已从匹配队列中移除 - user_id: {user_id}")
            return True
        else:
            logger.warning(f"用户不在匹配队列中 - user_id: {user_id}")
            return False
    
    async def _get_queue_info(self) -> List[Dict[str, Any]]:
        """获取匹配队列信息"""
        queue_data = get_key(self.match_queue_key)
        if queue_data:
            return json.loads(queue_data)
        return []
    
    async def _save_queue_info(self, queue_info: List[Dict[str, Any]]):
        """保存匹配队列信息"""
        set_key(self.match_queue_key, json.dumps(queue_info), expire=self.match_timeout)
    
    async def _get_user_position(self, user_id: UUID) -> int:
        """获取用户在队列中的位置"""
        queue_info = await self._get_queue_info()
        for i, user in enumerate(queue_info):
            if user["user_id"] == str(user_id):
                return i + 1
        return 0
    
    async def _try_match(self) -> Dict[str, Any]:
        """尝试匹配（使用原子操作防止匹配混乱）"""
        try:
            # 获取当前队列信息
            queue_info = await self._get_queue_info()
            
            if len(queue_info) >= 2:
                # 取前两个用户进行匹配
                matched_users = queue_info[:2]
                remaining_users = queue_info[2:]
                
                # 验证匹配用户是否仍然有效（防止重复匹配）
                valid_matched_users = []
                for user in matched_users:
                    # 检查用户是否仍然在队列中（通过重新获取队列验证）
                    current_queue = await self._get_queue_info()
                    if any(u["user_id"] == user["user_id"] for u in current_queue):
                        valid_matched_users.append(user)
                    else:
                        logger.warning(f"用户已离开队列，跳过匹配 - user_id: {user['user_id']}")
                
                if len(valid_matched_users) >= 2:
                    # 重新获取队列并移除已匹配的用户
                    final_queue = await self._get_queue_info()
                    final_queue = [user for user in final_queue if user["user_id"] not in [u["user_id"] for u in valid_matched_users[:2]]]
                    await self._save_queue_info(final_queue)
                    
                    logger.info(f"匹配成功 - 用户: {[user['user_id'] for user in valid_matched_users[:2]]}")
                    
                    return {
                        "matched": True,
                        "users": valid_matched_users[:2]
                    }
                else:
                    logger.info("匹配用户不足，继续等待")
                    return {
                        "matched": False,
                        "users": []
                    }
            else:
                return {
                    "matched": False,
                    "users": []
                }
                
        except Exception as e:
            logger.error(f"尝试匹配时发生错误: {str(e)}")
            return {
                "matched": False,
                "users": []
            }
    
    async def _send_match_confirmation(self, matched_users: List[Dict[str, Any]]):
        """发送匹配确认通知"""
        try:
            # 生成匹配ID
            match_id = str(uuid.uuid4())
            
            # 保存待确认的匹配信息
            pending_match = {
                "match_id": match_id,
                "users": matched_users,
                "confirmations": {},
                "create_time": datetime.utcnow().isoformat()
            }
            await self._save_pending_match(match_id, pending_match)
            
            # 获取WebSocket连接管理器实例
            from ..websocket.connection_manager import ConnectionManager
            connection_manager = ConnectionManager()
            
            # 为每个匹配的用户发送确认通知
            for user_info in matched_users:
                user_id = user_info["user_id"]
                await connection_manager.send_match_confirmation(user_id, {
                    "match_id": match_id,
                    "matched_users": matched_users
                })
            
            logger.info(f"匹配确认通知已发送 - match_id: {match_id}")
            
        except Exception as e:
            logger.error(f"发送匹配确认通知时发生错误: {str(e)}")
    
    async def _save_pending_match(self, match_id: str, pending_match: Dict[str, Any]):
        """保存待确认的匹配信息"""
        pending_matches = await self._get_pending_matches()
        pending_matches[match_id] = pending_match
        set_key(self.pending_matches_key, json.dumps(pending_matches), expire=self.match_timeout)
    
    async def _get_pending_matches(self) -> Dict[str, Any]:
        """获取所有待确认的匹配"""
        data = get_key(self.pending_matches_key)
        if data:
            return json.loads(data)
        return {}
    
    async def _get_pending_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """获取指定的待确认匹配"""
        pending_matches = await self._get_pending_matches()
        return pending_matches.get(match_id)
    
    async def _update_user_confirmation(self, match_id: str, user_id: UUID, confirm: bool):
        """更新用户确认状态"""
        pending_matches = await self._get_pending_matches()
        if match_id in pending_matches:
            pending_matches[match_id]["confirmations"][str(user_id)] = confirm
            set_key(self.pending_matches_key, json.dumps(pending_matches), expire=self.match_timeout)
    
    async def _check_all_confirmed(self, match_id: str) -> bool:
        """检查是否所有人都确认了"""
        pending_match = await self._get_pending_match(match_id)
        if not pending_match:
            return False
        
        users = pending_match["users"]
        confirmations = pending_match.get("confirmations", {})
        
        # 检查所有用户是否都确认了
        for user in users:
            user_id = user["user_id"]
            if user_id not in confirmations or not confirmations[user_id]:
                return False
        
        return True
    
    async def _handle_match_rejection(self, match_id: str, reject_user_id: UUID):
        """处理匹配拒绝"""
        try:
            pending_match = await self._get_pending_match(match_id)
            if not pending_match:
                return
            
            # 获取其他未拒绝的用户
            other_users = []
            confirmations = pending_match.get("confirmations", {})
            
            for user in pending_match["users"]:
                user_id = user["user_id"]
                if user_id != str(reject_user_id):
                    # 检查用户是否拒绝
                    if user_id not in confirmations or confirmations[user_id] is not False:
                        other_users.append(user)
            
            # 将未拒绝的用户重新加入队列（排在前面）
            if other_users:
                queue_info = await self._get_queue_info()
                # 将未拒绝的用户插入到队列前面
                queue_info = other_users + queue_info
                await self._save_queue_info(queue_info)
                
                logger.info(f"未拒绝的用户已重新加入队列 - users: {[u['user_id'] for u in other_users]}")
            
            # 移除待确认的匹配
            await self._remove_pending_match(match_id)
            
        except Exception as e:
            logger.error(f"处理匹配拒绝时发生错误: {str(e)}")
    
    async def _remove_pending_match(self, match_id: str):
        """移除待确认的匹配"""
        pending_matches = await self._get_pending_matches()
        if match_id in pending_matches:
            del pending_matches[match_id]
            set_key(self.pending_matches_key, json.dumps(pending_matches), expire=self.match_timeout)
    
    async def _create_room_from_confirmed_match(self, match_id: str) -> Dict[str, Any]:
        """根据确认的匹配创建房间"""
        try:
            pending_match = await self._get_pending_match(match_id)
            if not pending_match:
                raise ValueError("匹配信息不存在")
            
            users = pending_match["users"]
            logger.info(f"根据确认的匹配创建房间 - 用户: {[user['user_id'] for user in users]}")
            
            # 创建房间
            room_name = f"匹配房间_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            db_room = Room(
                room_name=room_name,
                room_type="public",
                status="waiting",
                max_players=2,
                current_players=2,
                game_mode="standard",
                game_settings={},
                pass_word=None,
                created_by=UUID(users[0]["user_id"]),  # 第一个用户作为房主
                remark="自动匹配创建的房间"
            )
            self.db.add(db_room)
            await self.db.commit()
            await self.db.refresh(db_room)
            
            logger.info(f"房间创建成功 - room_id: {db_room.id}")
            
            # 添加玩家到房间
            for i, user_info in enumerate(users):
                user_id = UUID(user_info["user_id"])
                room_player = RoomPlayer(
                    room_id=db_room.id,
                    user_id=user_id,
                    player_order=i + 1,
                    status="waiting",
                    join_time=datetime.utcnow(),
                    remark=""
                )
                self.db.add(room_player)
            
            await self.db.commit()
            
            logger.info(f"玩家已添加到房间 - room_id: {db_room.id}")
            
            # 发送房间创建通知
            await self._notify_room_created(str(db_room.id), users)
            
            return {
                "room_id": db_room.id,
                "room_name": db_room.room_name,
                "matched_users": users
            }
            
        except Exception as e:
            logger.error(f"创建确认匹配房间失败 - 错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"创建确认匹配房间失败: {str(e)}")
    
    async def _notify_room_created(self, room_id: str, matched_users: List[Dict[str, Any]]):
        """通知房间创建成功"""
        try:
            # 获取WebSocket连接管理器实例
            from ..websocket.connection_manager import ConnectionManager
            connection_manager = ConnectionManager()
            
            # 为每个匹配的用户发送通知
            for user_info in matched_users:
                user_id = user_info["user_id"]
                await connection_manager.send_match_success(user_id, {
                    "room_id": room_id,
                    "room_name": f"匹配房间_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    "matched_users": matched_users
                })
            
            logger.info(f"匹配成功通知已发送 - room_id: {room_id}")
            
        except Exception as e:
            logger.error(f"发送匹配成功通知时发生错误: {str(e)}") 