import random
import logging
from typing import Dict, Any, Optional, Tuple
from uuid import UUID
import json

logger = logging.getLogger(__name__)

class CoinGameManager:
    """猜拳游戏管理器
    
    负责管理猜拳游戏的Redis数据、选择逻辑、胜负判断和超时处理
    """
    
    def __init__(self, redis_client):
        """
        初始化猜拳游戏管理器
        
        Args:
            redis_client: Redis客户端实例
        """
        self.redis = redis_client
        self.mapping_expire_time = 180  # 映射数据过期时间：3分钟
        self.choice_expire_time = 180   # 选择数据过期时间：3分钟
        self.owner_timeout = 30         # 房主选择超时时间：30秒
        self.guest_timeout = 20         # 非房主选择超时时间：20秒
        
    def _get_mapping_key(self, room_id: UUID) -> str:
        """获取映射数据的Redis键"""
        return f"coin_mapping:{room_id}"
    
    def _get_choice_key(self, room_id: UUID, user_id: UUID) -> str:
        """获取用户选择的Redis键"""
        return f"coin_choice:{room_id}:{user_id}"
    
    def _get_owner_timeout_key(self, room_id: UUID) -> str:
        """获取房主超时的Redis键"""
        return f"coin_owner_timeout:{room_id}"
    
    def _get_guest_timeout_key(self, room_id: UUID) -> str:
        """获取非房主超时的Redis键"""
        return f"coin_guest_timeout:{room_id}"
    
    async def initialize_coin_game(self, room_id: UUID) -> Dict[str, Any]:
        """
        初始化猜拳游戏
        
        Args:
            room_id: 房间ID
            
        Returns:
            初始化结果，包含映射信息
        """
        try:
            logger.info(f"初始化猜拳游戏 - room_id: {room_id}")
            
            # 生成1、2、3与石头、剪刀、布的随机映射
            choices = [1, 2, 3]
            gestures = ["石头", "剪刀", "布"]
            random.shuffle(gestures)
            
            mapping = {
                "1": gestures[0],
                "2": gestures[1], 
                "3": gestures[2]
            }
            
            # 保存映射到Redis，设置3分钟过期时间
            mapping_key = self._get_mapping_key(room_id)
            self.redis.setex(
                mapping_key,
                self.mapping_expire_time,
                json.dumps(mapping)
            )
            
            logger.info(f"猜拳映射已保存 - room_id: {room_id}, mapping: {mapping}")
            
            return {
                "success": True,
                "room_id": str(room_id),
                "mapping": mapping,
                "expire_time": self.mapping_expire_time
            }
            
        except Exception as e:
            logger.error(f"初始化猜拳游戏失败 - room_id: {room_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_mapping(self, room_id: UUID) -> Optional[Dict[str, str]]:
        """
        获取猜拳映射
        
        Args:
            room_id: 房间ID
            
        Returns:
            映射字典，如果不存在则返回None
        """
        try:
            mapping_key = self._get_mapping_key(room_id)
            mapping_data = self.redis.get(mapping_key)
            
            if mapping_data:
                return json.loads(mapping_data)
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取猜拳映射失败 - room_id: {room_id}, 错误: {str(e)}")
            return None
    
    async def make_choice(self, room_id: UUID, user_id: UUID, choice: int, is_owner: bool) -> Dict[str, Any]:
        """
        用户做出选择
        
        Args:
            room_id: 房间ID
            user_id: 用户ID
            choice: 选择（1、2、3）
            is_owner: 是否是房主
            
        Returns:
            选择结果
        """
        try:
            logger.info(f"用户做出选择 - room_id: {room_id}, user_id: {user_id}, choice: {choice}, is_owner: {is_owner}")
            
            # 验证选择值
            if choice not in [1, 2, 3]:
                return {
                    "success": False,
                    "error": "选择值只能是1、2、3中的一个"
                }
            
            # 检查映射是否存在
            mapping = await self.get_mapping(room_id)
            if not mapping:
                return {
                    "success": False,
                    "error": "猜拳游戏未初始化或已过期"
                }
            
            choice_key = self._get_choice_key(room_id, user_id)
            
            # 检查是否已经选择过
            existing_choice = self.redis.get(choice_key)
            if existing_choice:
                return {
                    "success": False,
                    "error": "您已做出选择"
                }
            
            if is_owner:
                # 房主选择
                # 保存用户选择
                self.redis.setex(choice_key, self.choice_expire_time, str(choice))
                
                logger.info(f"房主选择已保存 - room_id: {room_id}, user_id: {user_id}, choice: {choice}")
                
                return {
                    "success": True,
                    "message": "选择已保存，等待对手选择",
                    "choice": choice,
                    "gesture": mapping[str(choice)]
                }
            else:
                # 非房主选择
                # 获取房主选择（需要调用方传入房主ID）
                # 这里暂时返回错误，由调用方处理
                return {
                    "success": False,
                    "error": "需要房主ID来获取房主选择"
                }
                
        except Exception as e:
            logger.error(f"用户选择失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def make_choice_with_owner_id(self, room_id: UUID, user_id: UUID, choice: int, is_owner: bool, owner_id: UUID = None) -> Dict[str, Any]:
        """
        用户做出选择（包含房主ID）
        
        Args:
            room_id: 房间ID
            user_id: 用户ID
            choice: 选择（1、2、3）
            is_owner: 是否是房主
            owner_id: 房主ID（非房主选择时需要）
            
        Returns:
            选择结果
        """
        try:
            logger.info(f"用户做出选择 - room_id: {room_id}, user_id: {user_id}, choice: {choice}, is_owner: {is_owner}")
            
            # 验证选择值
            if choice not in [1, 2, 3]:
                return {
                    "success": False,
                    "error": "选择值只能是1、2、3中的一个"
                }
            
            # 检查映射是否存在
            mapping = await self.get_mapping(room_id)
            if not mapping:
                return {
                    "success": False,
                    "error": "猜拳游戏未初始化或已过期"
                }
            
            choice_key = self._get_choice_key(room_id, user_id)
            
            # 检查是否已经选择过
            existing_choice = self.redis.get(choice_key)
            if existing_choice:
                return {
                    "success": False,
                    "error": "您已做出选择"
                }
            
            if is_owner:
                # 房主选择
                # 保存用户选择
                self.redis.setex(choice_key, self.choice_expire_time, str(choice))
                
                logger.info(f"房主选择已保存 - room_id: {room_id}, user_id: {user_id}, choice: {choice}")
                
                return {
                    "success": True,
                    "message": "选择已保存，等待对手选择",
                    "choice": choice,
                    "gesture": mapping[str(choice)]
                }
            else:
                # 非房主选择
                if not owner_id:
                    return {
                        "success": False,
                        "error": "房主ID不能为空"
                    }
                
                # 获取房主选择
                owner_choice = await self.get_owner_choice(room_id, owner_id)
                
                if not owner_choice:
                    return {
                        "success": False,
                        "error": "房主尚未做出选择"
                    }
                
                # 检查是否选择相同
                if choice == owner_choice:
                    return {
                        "success": False,
                        "error": "不能选择相同的出拳"
                    }
                
                # 保存非房主选择
                self.redis.setex(choice_key, self.choice_expire_time, str(choice))
                
                # 判断胜负
                winner, loser, result = self._determine_winner(owner_choice, choice, mapping)
                
                logger.info(f"猜拳结果 - room_id: {room_id}, owner_choice: {owner_choice}, guest_choice: {choice}, winner: {winner}")
                
                return {
                    "success": True,
                    "message": "猜拳完成",
                    "owner_choice": owner_choice,
                    "guest_choice": choice,
                    "owner_gesture": mapping[str(owner_choice)],
                    "guest_gesture": mapping[str(choice)],
                    "mapping": mapping,
                    "winner": winner,
                    "loser": loser,
                    "result": result
                }
                
        except Exception as e:
            logger.error(f"用户选择失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _determine_winner(self, owner_choice: int, guest_choice: int, mapping: Dict[str, str]) -> Tuple[str, str, str]:
        """
        判断胜负
        
        Args:
            owner_choice: 房主选择
            guest_choice: 非房主选择
            mapping: 映射字典
            
        Returns:
            (获胜者, 失败者, 结果描述)
        """
        owner_gesture = mapping[str(owner_choice)]
        guest_gesture = mapping[str(guest_choice)]
        
        # 胜负判断逻辑
        if owner_gesture == "石头":
            if guest_gesture == "剪刀":
                return "owner", "guest", f"{owner_gesture} 胜 {guest_gesture}"
            else:  # 布
                return "guest", "owner", f"{guest_gesture} 胜 {owner_gesture}"
        elif owner_gesture == "剪刀":
            if guest_gesture == "布":
                return "owner", "guest", f"{owner_gesture} 胜 {guest_gesture}"
            else:  # 石头
                return "guest", "owner", f"{guest_gesture} 胜 {owner_gesture}"
        else:  # 布
            if guest_gesture == "石头":
                return "owner", "guest", f"{owner_gesture} 胜 {guest_gesture}"
            else:  # 剪刀
                return "guest", "owner", f"{guest_gesture} 胜 {owner_gesture}"
    
    async def get_user_choice(self, room_id: UUID, user_id: UUID) -> Optional[int]:
        """
        获取用户选择
        
        Args:
            room_id: 房间ID
            user_id: 用户ID
            
        Returns:
            用户选择，如果未选择则返回None
        """
        try:
            choice_key = self._get_choice_key(room_id, user_id)
            choice_data = self.redis.get(choice_key)
            
            if choice_data:
                return int(choice_data)
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取用户选择失败 - room_id: {room_id}, user_id: {user_id}, 错误: {str(e)}")
            return None
    
    async def _get_owner_choice(self, room_id: UUID) -> Optional[int]:
        """
        获取房主选择（通过房间创建者ID）
        
        Args:
            room_id: 房间ID
            
        Returns:
            房主选择，如果未选择则返回None
        """
        try:
            # 这里需要从数据库获取房间创建者ID
            # 暂时返回None，由调用方传入房主ID
            return None
                
        except Exception as e:
            logger.error(f"获取房主选择失败 - room_id: {room_id}, 错误: {str(e)}")
            return None
    
    async def get_owner_choice(self, room_id: UUID, owner_id: UUID) -> Optional[int]:
        """
        获取房主选择
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            
        Returns:
            房主选择，如果未选择则返回None
        """
        try:
            return await self.get_user_choice(room_id, owner_id)
                
        except Exception as e:
            logger.error(f"获取房主选择失败 - room_id: {room_id}, owner_id: {owner_id}, 错误: {str(e)}")
            return None
    
    async def get_all_choices(self, room_id: UUID) -> Dict[str, Any]:
        """
        获取房间所有用户的选择
        
        Args:
            room_id: 房间ID
            
        Returns:
            所有选择信息
        """
        try:
            # 这里需要从数据库获取房间玩家列表
            # 暂时返回空字典，由调用方传入玩家列表
            return {}
                
        except Exception as e:
            logger.error(f"获取所有选择失败 - room_id: {room_id}, 错误: {str(e)}")
            return {}
    
    async def auto_choose_for_owner(self, room_id: UUID, owner_id: UUID) -> Dict[str, Any]:
        """
        房主超时自动选择
        
        Args:
            room_id: 房间ID
            owner_id: 房主ID
            
        Returns:
            自动选择结果
        """
        try:
            logger.info(f"房主超时自动选择 - room_id: {room_id}, owner_id: {owner_id}")
            
            # 检查是否已经选择过
            existing_choice = await self.get_user_choice(room_id, owner_id)
            if existing_choice:
                return {
                    "success": False,
                    "error": "房主已经做出选择"
                }
            
            # 随机选择1、2、3中的一个
            choice = random.randint(1, 3)
            
            # 保存房主选择
            choice_key = self._get_choice_key(room_id, owner_id)
            self.redis.setex(choice_key, self.choice_expire_time, str(choice))
            
            logger.info(f"房主自动选择完成 - room_id: {room_id}, owner_id: {owner_id}, choice: {choice}")
            
            return {
                "success": True,
                "choice": choice,
                "message": "房主超时自动选择"
            }
            
        except Exception as e:
            logger.error(f"房主自动选择失败 - room_id: {room_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def auto_choose_for_guest(self, room_id: UUID, guest_id: UUID, owner_choice: int) -> Dict[str, Any]:
        """
        非房主超时自动选择
        
        Args:
            room_id: 房间ID
            guest_id: 非房主ID
            owner_choice: 房主选择
            
        Returns:
            自动选择结果
        """
        try:
            logger.info(f"非房主超时自动选择 - room_id: {room_id}, guest_id: {guest_id}")
            
            # 检查是否已经选择过
            existing_choice = await self.get_user_choice(room_id, guest_id)
            if existing_choice:
                return {
                    "success": False,
                    "error": "非房主已经做出选择"
                }
            
            # 选择房主没有选择的数字
            available_choices = [1, 2, 3]
            available_choices.remove(owner_choice)
            choice = random.choice(available_choices)
            
            # 获取映射
            mapping = await self.get_mapping(room_id)
            if not mapping:
                return {
                    "success": False,
                    "error": "猜拳映射不存在"
                }
            
            # 保存非房主选择
            choice_key = self._get_choice_key(room_id, guest_id)
            self.redis.setex(choice_key, self.choice_expire_time, str(choice))
            
            # 判断胜负
            winner, loser, result = self._determine_winner(owner_choice, choice, mapping)
            
            logger.info(f"非房主自动选择完成 - room_id: {room_id}, owner_choice: {owner_choice}, guest_choice: {choice}, winner: {winner}")
            
            return {
                "success": True,
                "owner_choice": owner_choice,
                "guest_choice": choice,
                "owner_gesture": mapping[str(owner_choice)],
                "guest_gesture": mapping[str(choice)],
                "mapping": mapping,
                "winner": winner,
                "loser": loser,
                "result": result,
                "message": "非房主超时自动选择"
            }
            
        except Exception as e:
            logger.error(f"非房主自动选择失败 - room_id: {room_id}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_coin_game_status(self, room_id: UUID) -> Dict[str, Any]:
        """
        获取猜拳游戏状态
        
        Args:
            room_id: 房间ID
            
        Returns:
            猜拳游戏状态
        """
        try:
            # 获取映射信息
            mapping = await self.get_mapping(room_id)
            
            if not mapping:
                return {
                    "status": "not_initialized",
                    "message": "猜拳游戏未初始化"
                }
            
            return {
                "status": "active",
                "mapping": mapping,
                "expire_time": self.mapping_expire_time
            }
            
        except Exception as e:
            logger.error(f"获取猜拳游戏状态失败 - room_id: {room_id}, 错误: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            } 