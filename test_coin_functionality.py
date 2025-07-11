#!/usr/bin/env python3
"""
猜拳功能测试脚本
"""

import asyncio
import json
import logging
from uuid import UUID
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockRedis:
    """模拟Redis客户端"""
    
    def __init__(self):
        self.data = {}
    
    def setex(self, key: str, expire: int, value: str):
        """设置键值对并设置过期时间"""
        self.data[key] = {
            'value': value,
            'expire_at': datetime.now().timestamp() + expire
        }
        logger.info(f"Redis SETEX: {key} = {value}, expire: {expire}s")
    
    def get(self, key: str):
        """获取键值"""
        if key in self.data:
            item = self.data[key]
            if datetime.now().timestamp() < item['expire_at']:
                logger.info(f"Redis GET: {key} = {item['value']}")
                return item['value']
            else:
                # 已过期，删除
                del self.data[key]
                logger.info(f"Redis GET: {key} = None (expired)")
                return None
        logger.info(f"Redis GET: {key} = None (not found)")
        return None
    
    def delete(self, *keys):
        """删除键"""
        for key in keys:
            if key in self.data:
                del self.data[key]
                logger.info(f"Redis DELETE: {key}")
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return key in self.data and datetime.now().timestamp() < self.data[key]['expire_at']

class MockCoinGameManager:
    """模拟猜拳游戏管理器"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.mapping_expire_time = 180
        self.choice_expire_time = 180
    
    def _get_mapping_key(self, room_id: UUID) -> str:
        return f"coin_mapping:{room_id}"
    
    def _get_choice_key(self, room_id: UUID, user_id: UUID) -> str:
        return f"coin_choice:{room_id}:{user_id}"
    
    async def initialize_coin_game(self, room_id: UUID):
        """初始化猜拳游戏"""
        import random
        
        # 生成1、2、3与石头、剪刀、布的随机映射
        choices = [1, 2, 3]
        gestures = ["石头", "剪刀", "布"]
        random.shuffle(gestures)
        
        mapping = {
            "1": gestures[0],
            "2": gestures[1], 
            "3": gestures[2]
        }
        
        # 保存映射到Redis
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
    
    async def get_mapping(self, room_id: UUID):
        """获取猜拳映射"""
        mapping_key = self._get_mapping_key(room_id)
        mapping_data = self.redis.get(mapping_key)
        
        if mapping_data:
            return json.loads(mapping_data)
        else:
            return None
    
    async def get_user_choice(self, room_id: UUID, user_id: UUID):
        """获取用户选择"""
        choice_key = self._get_choice_key(room_id, user_id)
        choice_data = self.redis.get(choice_key)
        
        if choice_data:
            return int(choice_data)
        else:
            return None
    
    async def make_choice_with_owner_id(self, room_id: UUID, user_id: UUID, choice: int, is_owner: bool, owner_id: UUID = None):
        """用户做出选择"""
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
            owner_choice = await self.get_user_choice(room_id, owner_id)
            
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
    
    def _determine_winner(self, owner_choice: int, guest_choice: int, mapping: dict):
        """判断胜负"""
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

async def test_coin_functionality():
    """测试猜拳功能"""
    logger.info("开始测试猜拳功能")
    
    # 创建模拟Redis客户端
    redis_client = MockRedis()
    
    # 创建猜拳游戏管理器
    coin_manager = MockCoinGameManager(redis_client)
    
    # 模拟房间和用户ID
    room_id = UUID("12345678-1234-1234-1234-123456789abc")
    owner_id = UUID("11111111-1111-1111-1111-111111111111")
    guest_id = UUID("22222222-2222-2222-2222-222222222222")
    
    try:
        # 1. 初始化猜拳游戏
        logger.info("\n=== 1. 初始化猜拳游戏 ===")
        init_result = await coin_manager.initialize_coin_game(room_id)
        logger.info(f"初始化结果: {init_result}")
        
        # 2. 房主做出选择
        logger.info("\n=== 2. 房主做出选择 ===")
        owner_result = await coin_manager.make_choice_with_owner_id(
            room_id, owner_id, 1, True
        )
        logger.info(f"房主选择结果: {owner_result}")
        
        # 3. 非房主做出选择
        logger.info("\n=== 3. 非房主做出选择 ===")
        guest_result = await coin_manager.make_choice_with_owner_id(
            room_id, guest_id, 2, False, owner_id
        )
        logger.info(f"非房主选择结果: {guest_result}")
        
        # 4. 验证选择不能重复
        logger.info("\n=== 4. 验证选择不能重复 ===")
        duplicate_result = await coin_manager.make_choice_with_owner_id(
            room_id, guest_id, 2, False, owner_id
        )
        logger.info(f"重复选择结果: {duplicate_result}")
        
        # 5. 验证不能选择相同数字
        logger.info("\n=== 5. 验证不能选择相同数字 ===")
        # 创建新的非房主用户
        guest2_id = UUID("33333333-3333-3333-3333-333333333333")
        same_choice_result = await coin_manager.make_choice_with_owner_id(
            room_id, guest2_id, 1, False, owner_id
        )
        logger.info(f"相同选择结果: {same_choice_result}")
        
        # 6. 查看Redis中的数据
        logger.info("\n=== 6. Redis中的数据 ===")
        mapping = await coin_manager.get_mapping(room_id)
        owner_choice = await coin_manager.get_user_choice(room_id, owner_id)
        guest_choice = await coin_manager.get_user_choice(room_id, guest_id)
        
        logger.info(f"映射: {mapping}")
        logger.info(f"房主选择: {owner_choice}")
        logger.info(f"非房主选择: {guest_choice}")
        
        logger.info("\n猜拳功能测试完成！")
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_coin_functionality()) 