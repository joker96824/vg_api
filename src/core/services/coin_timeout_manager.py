import asyncio
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class CoinTimeoutManager:
    """猜拳超时管理器
    
    负责管理猜拳游戏的超时任务，包括房主和非房主的超时自动选择
    """
    
    def __init__(self, coin_game_manager, battle_service):
        """
        初始化超时管理器
        
        Args:
            coin_game_manager: 猜拳游戏管理器实例
            battle_service: 对战服务实例
        """
        self.coin_game_manager = coin_game_manager
        self.battle_service = battle_service
        self.timeout_tasks = {}  # 存储超时任务
        
    def _get_owner_timeout_key(self, room_id: UUID) -> str:
        """获取房主超时任务的键"""
        return f"owner_timeout:{room_id}"
    
    def _get_guest_timeout_key(self, room_id: UUID) -> str:
        """获取非房主超时任务的的键"""
        return f"guest_timeout:{room_id}"
    
    def _get_first_player_timeout_key(self, room_id: UUID) -> str:
        """获取胜方选择先攻后攻超时任务的键"""
        return f"first_player_timeout:{room_id}"
    
    async def schedule_owner_timeout(self, room_id: UUID, owner_id: UUID, guest_id: UUID) -> None:
        """
        安排房主超时任务
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            guest_id: 非房主ID
        """
        try:
            logger.info(f"安排房主超时任务 - room_id: {room_id}, owner_id: {owner_id}")
            
            # 取消已存在的超时任务
            await self.cancel_owner_timeout(room_id)
            
            # 创建新的超时任务
            task_key = self._get_owner_timeout_key(room_id)
            task = asyncio.create_task(
                self._owner_timeout_handler(room_id, owner_id, guest_id)
            )
            self.timeout_tasks[task_key] = task
            
            logger.info(f"房主超时任务已安排 - room_id: {room_id}, 30秒后执行")
            
        except Exception as e:
            logger.error(f"安排房主超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def schedule_guest_timeout(self, room_id: UUID, owner_id: UUID, guest_id: UUID) -> None:
        """
        安排非房主超时任务
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            guest_id: 非房主ID
        """
        try:
            logger.info(f"安排非房主超时任务 - room_id: {room_id}, guest_id: {guest_id}")
            
            # 取消已存在的超时任务
            await self.cancel_guest_timeout(room_id)
            
            # 创建新的超时任务
            task_key = self._get_guest_timeout_key(room_id)
            task = asyncio.create_task(
                self._guest_timeout_handler(room_id, owner_id, guest_id)
            )
            self.timeout_tasks[task_key] = task
            
            logger.info(f"非房主超时任务已安排 - room_id: {room_id}, 20秒后执行")
            
        except Exception as e:
            logger.error(f"安排非房主超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def schedule_first_player_timeout(self, room_id: UUID, winner_id: UUID, loser_id: UUID) -> None:
        """
        安排胜方选择先攻后攻的超时任务
        
        Args:
            room_id: 房间ID
            winner_id: 胜方ID
            loser_id: 败方ID
        """
        try:
            logger.info(f"安排胜方选择先攻后攻超时任务 - room_id: {room_id}, winner_id: {winner_id}")
            
            # 取消已存在的超时任务
            await self.cancel_first_player_timeout(room_id)
            
            # 创建新的超时任务
            task_key = self._get_first_player_timeout_key(room_id)
            task = asyncio.create_task(
                self._first_player_timeout_handler(room_id, winner_id, loser_id)
            )
            self.timeout_tasks[task_key] = task
            
            logger.info(f"胜方选择先攻后攻超时任务已安排 - room_id: {room_id}, 30秒后执行")
            
        except Exception as e:
            logger.error(f"安排胜方选择先攻后攻超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def _owner_timeout_handler(self, room_id: UUID, owner_id: UUID, guest_id: UUID) -> None:
        """
        房主超时处理
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            guest_id: 非房主ID
        """
        try:
            # 等待30秒
            await asyncio.sleep(30)
            
            logger.info(f"房主超时处理开始 - room_id: {room_id}")
            
            # 检查房主是否已经选择
            owner_choice = await self.coin_game_manager.get_user_choice(room_id, owner_id)
            if owner_choice:
                logger.info(f"房主已经选择，取消超时处理 - room_id: {room_id}")
                return
            
            # 执行房主自动选择
            result = await self.coin_game_manager.auto_choose_for_owner(room_id, owner_id)
            
            if result["success"]:
                logger.info(f"房主自动选择完成 - room_id: {room_id}, choice: {result['choice']}")
                
                # 获取映射信息用于WebSocket消息
                mapping = await self.coin_game_manager.get_mapping(room_id)
                gesture = mapping[str(result["choice"])] if mapping else "未知"
                
                # 发送update_state消息给房主
                await self._send_update_state_to_owner(room_id, owner_id, result["choice"], gesture, is_auto=True)
                
                # 发送update_state消息给非房主（房主已选择）
                await self._send_update_state_to_guest(room_id, guest_id, result["choice"])
                
                # 安排非房主超时任务
                await self.schedule_guest_timeout(room_id, owner_id, guest_id)
            else:
                logger.error(f"房主自动选择失败 - room_id: {room_id}, 错误: {result['error']}")
                
        except asyncio.CancelledError:
            logger.info(f"房主超时任务被取消 - room_id: {room_id}")
        except Exception as e:
            logger.error(f"房主超时处理失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def _guest_timeout_handler(self, room_id: UUID, owner_id: UUID, guest_id: UUID) -> None:
        """
        非房主超时处理
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            guest_id: 非房主ID
        """
        try:
            # 等待20秒
            await asyncio.sleep(20)
            
            logger.info(f"非房主超时处理开始 - room_id: {room_id}")
            
            # 检查非房主是否已经选择
            guest_choice = await self.coin_game_manager.get_user_choice(room_id, guest_id)
            if guest_choice:
                logger.info(f"非房主已经选择，取消超时处理 - room_id: {room_id}")
                return
            
            # 获取房主选择
            owner_choice = await self.coin_game_manager.get_user_choice(room_id, owner_id)
            if not owner_choice:
                logger.error(f"房主选择不存在，无法进行非房主自动选择 - room_id: {room_id}")
                return
            
            # 执行非房主自动选择
            result = await self.coin_game_manager.auto_choose_for_guest(room_id, guest_id, owner_choice)
            
            if result["success"]:
                logger.info(f"非房主自动选择完成 - room_id: {room_id}, winner: {result['winner']}")
                
                # 发送update_state消息给非房主
                await self._send_update_state_to_guest_after_choice(room_id, guest_id, result["guest_choice"], result["guest_gesture"], is_auto=True)
                
                # 发送update_state消息给房主（非房主已选择）
                await self._send_update_state_to_owner_after_guest_choice(room_id, owner_id, result["guest_choice"], result["guest_gesture"], is_auto=True)
                
                # 处理猜拳结果
                await self._handle_coin_result(room_id, owner_id, guest_id, result)
            else:
                logger.error(f"非房主自动选择失败 - room_id: {room_id}, 错误: {result['error']}")
                
        except asyncio.CancelledError:
            logger.info(f"非房主超时任务被取消 - room_id: {room_id}")
        except Exception as e:
            logger.error(f"非房主超时处理失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def _first_player_timeout_handler(self, room_id: UUID, winner_id: UUID, loser_id: UUID) -> None:
        """
        胜方选择先攻后攻超时处理
        
        Args:
            room_id: 房间ID
            winner_id: 胜方ID
            loser_id: 败方ID
        """
        try:
            # 等待30秒
            await asyncio.sleep(30)
            
            logger.info(f"胜方选择先攻后攻超时处理开始 - room_id: {room_id}")
            
            # 随机选择先攻后攻
            import random
            first_player = winner_id if random.choice([True, False]) else loser_id
            
            # 更新对战状态
            await self._update_battle_after_coin(room_id, winner_id, first_player)
            
            logger.info(f"胜方选择先攻后攻超时处理完成 - room_id: {room_id}, first_player: {first_player}")
                
        except asyncio.CancelledError:
            logger.info(f"胜方选择先攻后攻超时任务被取消 - room_id: {room_id}")
        except Exception as e:
            logger.error(f"胜方选择先攻后攻超时处理失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_owner(self, room_id: UUID, owner_id: UUID, choice: int, gesture: str, is_auto: bool = False) -> None:
        """
        发送update_state消息给房主
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            choice: 选择的值
            gesture: 对应的手势
            is_auto: 是否为自动选择
        """
        try:
            # 获取WebSocket连接管理器
            connection_manager = self.battle_service._get_connection_manager()
            
            # 构建消息数据
            message_data = {
                "type": "update_state",
                "room_id": str(room_id),
                "choice": choice,
                "gesture": gesture,
                "is_auto": is_auto,
                "message": "房主超时自动选择完成" if is_auto else "选择已保存，等待对手选择"
            }
            
            # 发送状态更新消息给房主
            await connection_manager.send_state_update(str(owner_id), message_data)
            
            logger.info(f"已发送update_state消息给房主 - room_id: {room_id}, owner_id: {owner_id}, choice: {choice}, is_auto: {is_auto}")
            
        except Exception as e:
            logger.error(f"发送update_state消息给房主失败 - room_id: {room_id}, owner_id: {owner_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_guest(self, room_id: UUID, guest_id: UUID, owner_choice: int) -> None:
        """
        发送update_state消息给非房主（房主已选择）
        
        Args:
            room_id: 房间ID
            guest_id: 非房主ID
            owner_choice: 房主选择
        """
        try:
            # 获取WebSocket连接管理器
            connection_manager = self.battle_service._get_connection_manager()
            
            # 构建消息数据
            message_data = {
                "type": "update_state",
                "room_id": str(room_id),
                "owner_choice": owner_choice,
                "message": "房主已做出选择，请尽快选择"
            }
            
            # 发送状态更新消息给非房主
            await connection_manager.send_state_update(str(guest_id), message_data)
            
            logger.info(f"已发送update_state消息给非房主（房主已选择）- room_id: {room_id}, guest_id: {guest_id}")
            
        except Exception as e:
            logger.error(f"发送update_state消息给非房主失败 - room_id: {room_id}, guest_id: {guest_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_guest_after_choice(self, room_id: UUID, guest_id: UUID, choice: int, gesture: str, is_auto: bool = False) -> None:
        """
        发送update_state消息给非房主（非房主选择后）
        
        Args:
            room_id: 房间ID
            guest_id: 非房主ID
            choice: 选择的值
            gesture: 对应的手势
            is_auto: 是否为自动选择
        """
        try:
            # 获取WebSocket连接管理器
            connection_manager = self.battle_service._get_connection_manager()
            
            # 构建消息数据
            message_data = {
                "type": "update_state",
                "room_id": str(room_id),
                "choice": choice,
                "gesture": gesture,
                "is_auto": is_auto,
                "message": "非房主超时自动选择完成" if is_auto else "选择已保存，等待结果"
            }
            
            # 发送状态更新消息给非房主
            await connection_manager.send_state_update(str(guest_id), message_data)
            
            logger.info(f"已发送update_state消息给非房主（选择后）- room_id: {room_id}, guest_id: {guest_id}, choice: {choice}, is_auto: {is_auto}")
            
        except Exception as e:
            logger.error(f"发送update_state消息给非房主失败 - room_id: {room_id}, guest_id: {guest_id}, 错误: {str(e)}")
    
    async def _send_update_state_to_owner_after_guest_choice(self, room_id: UUID, owner_id: UUID, choice: int, gesture: str, is_auto: bool = False) -> None:
        """
        发送update_state消息给房主（非房主已选择）
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            choice: 选择的值
            gesture: 对应的手势
            is_auto: 是否为自动选择
        """
        try:
            # 获取WebSocket连接管理器
            connection_manager = self.battle_service._get_connection_manager()
            
            # 构建消息数据
            message_data = {
                "type": "update_state",
                "room_id": str(room_id),
                "choice": choice,
                "gesture": gesture,
                "is_auto": is_auto,
                "message": "非房主超时自动选择完成" if is_auto else "选择已保存，等待结果"
            }
            
            # 发送状态更新消息给房主
            await connection_manager.send_state_update(str(owner_id), message_data)
            
            logger.info(f"已发送update_state消息给房主（非房主已选择）- room_id: {room_id}, owner_id: {owner_id}, choice: {choice}, is_auto: {is_auto}")
            
        except Exception as e:
            logger.error(f"发送update_state消息给房主失败 - room_id: {room_id}, owner_id: {owner_id}, 错误: {str(e)}")
    
    async def _handle_coin_result(self, room_id: UUID, owner_id: UUID, guest_id: UUID, result: Dict[str, Any]) -> None:
        """
        处理猜拳结果
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            guest_id: 非房主ID
            result: 猜拳结果
        """
        try:
            logger.info(f"处理猜拳结果 - room_id: {room_id}, winner: {result['winner']}")
            
            # 获取WebSocket连接管理器
            connection_manager = self.battle_service._get_connection_manager()
            
            # 确定获胜者和失败者
            winner_id = owner_id if result["winner"] == "owner" else guest_id
            loser_id = guest_id if result["winner"] == "owner" else owner_id
            
            # 发送猜拳结果消息给双方
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
                    "winner_id": str(winner_id),
                    "loser_id": str(loser_id),
                    "result": result["result"]
                }
            )
            
            # 安排胜方选择先攻后攻的超时任务（30秒）
            await self.schedule_first_player_timeout(room_id, winner_id, loser_id)
            
            logger.info(f"猜拳结果处理完成，等待胜方选择先攻后攻 - room_id: {room_id}, winner_id: {winner_id}")
            
        except Exception as e:
            logger.error(f"处理猜拳结果失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def _update_battle_after_coin(self, room_id: UUID, winner_id: UUID, first_player: UUID) -> None:
        """
        猜拳结束后更新对战状态
        
        Args:
            room_id: 房间ID
            winner_id: 获胜者ID
            first_player: 优先出牌玩家ID
        """
        try:
            # 获取对战记录
            battle = await self.battle_service.get_battle_by_room(room_id)
            if not battle:
                logger.error(f"找不到对战记录 - room_id: {room_id}")
                return
            
            # 更新对战状态为prepare
            await self.battle_service.update_battle_status(battle.id, "prepare")
            
            # 更新游戏状态中的优先出牌玩家
            game_state = await self.battle_service.get_game_state(battle.id)
            if game_state:
                updates = {
                    "first_player": str(first_player),
                    "current_player": str(first_player)
                }
                await self.battle_service.update_game_state(battle.id, updates)
            
            # 获取房间玩家信息用于发送WebSocket消息
            room_players = await self.battle_service._get_room_players(room_id)
            if len(room_players) == 2:
                # 发送state_update消息给双方
                connection_manager = self.battle_service._get_connection_manager()
                
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
    
    async def cancel_owner_timeout(self, room_id: UUID) -> None:
        """
        取消房主超时任务
        
        Args:
            room_id: 房间ID
        """
        try:
            task_key = self._get_owner_timeout_key(room_id)
            if task_key in self.timeout_tasks:
                task = self.timeout_tasks[task_key]
                task.cancel()
                del self.timeout_tasks[task_key]
                logger.info(f"房主超时任务已取消 - room_id: {room_id}")
                
        except Exception as e:
            logger.error(f"取消房主超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def cancel_guest_timeout(self, room_id: UUID) -> None:
        """
        取消非房主超时任务
        
        Args:
            room_id: 房间ID
        """
        try:
            task_key = self._get_guest_timeout_key(room_id)
            if task_key in self.timeout_tasks:
                task = self.timeout_tasks[task_key]
                task.cancel()
                del self.timeout_tasks[task_key]
                logger.info(f"非房主超时任务已取消 - room_id: {room_id}")
                
        except Exception as e:
            logger.error(f"取消非房主超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def cancel_first_player_timeout(self, room_id: UUID) -> None:
        """
        取消胜方选择先攻后攻的超时任务
        
        Args:
            room_id: 房间ID
        """
        try:
            task_key = self._get_first_player_timeout_key(room_id)
            if task_key in self.timeout_tasks:
                task = self.timeout_tasks[task_key]
                task.cancel()
                del self.timeout_tasks[task_key]
                logger.info(f"胜方选择先攻后攻超时任务已取消 - room_id: {room_id}")
                
        except Exception as e:
            logger.error(f"取消胜方选择先攻后攻超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    async def cancel_all_timeouts(self, room_id: UUID) -> None:
        """
        取消房间的所有超时任务
        
        Args:
            room_id: 房间ID
        """
        try:
            await self.cancel_owner_timeout(room_id)
            await self.cancel_guest_timeout(room_id)
            await self.cancel_first_player_timeout(room_id)
            logger.info(f"房间所有超时任务已取消 - room_id: {room_id}")
            
        except Exception as e:
            logger.error(f"取消房间超时任务失败 - room_id: {room_id}, 错误: {str(e)}")
    
    def get_active_timeouts(self) -> Dict[str, Any]:
        """
        获取当前活跃的超时任务
        
        Returns:
            活跃任务信息
        """
        active_tasks = {}
        for task_key, task in self.timeout_tasks.items():
            if not task.done():
                active_tasks[task_key] = {
                    "status": "running",
                    "created_at": getattr(task, 'created_at', None)
                }
            else:
                active_tasks[task_key] = {
                    "status": "completed",
                    "result": getattr(task, 'result', None)
                }
        
        return active_tasks 