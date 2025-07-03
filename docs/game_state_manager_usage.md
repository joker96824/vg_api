# 游戏状态管理器使用说明

## 概述

`GameStateManager` 是专门用于管理 `Battle.current_game_state` 字段的类，提供了完整的游戏状态管理功能，包括初始化、保存、加载、更新、验证和断线重连支持。

## 回合阶段定义

游戏状态管理器定义了完整的回合阶段系统：

### 主要阶段
- **reset**: 重置阶段
- **draw**: 抽卡阶段
- **ride**: 骑升阶段
- **main**: 主要阶段
- **battle**: 战斗阶段
- **turnend**: 回合结束

### 战斗子阶段
- **battle_start**: 战斗开始
- **battle_attack**: 攻击阶段
- **battle_defence**: 防御阶段
- **battle_trigger**: 触发阶段
- **battle_damage**: 伤害阶段
- **battle_end**: 战斗结束

## 玩家场面区域定义

每个玩家的场面包含以下区域：

### 卡牌区域
- **ride**: 骑升轴 - 存放骑升卡牌
- **deck**: 卡组 - 存放剩余卡牌
- **hand**: 手牌 - 存放手牌
- **v**: 先导者 - 存放先导者卡牌
- **leftfront**: 左前 - 左前卫位置
- **leftback**: 左后 - 左后卫位置
- **rightfront**: 右前 - 右前卫位置
- **rightback**: 右后 - 右后卫位置
- **vback**: v后 - 先导者后方位置
- **damage**: 伤害区 - 存放伤害卡牌
- **instruction**: 指令区 - 存放指令卡牌
- **trigger**: 判定区 - 存放触发卡牌
- **coa**: 纹章 - 存放纹章卡牌
- **g**: g区 - 存放g区卡牌
- **gdeck**: g卡组 - 存放g卡组卡牌
- **token**: 衍生物 - 存放衍生物卡牌
- **seal**: 封存 - 存放封存卡牌

### 效果区域
- **effect**: 永续效果 - 存放永续效果（JSON格式）

## Card对象结构

每个卡牌区域中的元素都是Card对象，具有以下结构：

### 基础结构
```json
{
    "show": true,  // 是否显示详细信息
    "id": "卡牌ID",
    "name_cn": "中文名称",
    "nation": "所属国家",
    "clan": "所属种族",
    "grade": 3,  // 等级
    "skill": "技能描述",
    "card_power": 9000,  // 力量值
    "shield": 5000,  // 护盾值
    "critical": 1,  // 暴击值
    "special_mark": "特殊标识",
    "card_type": "卡片类型",
    "trigger_type": "触发类型",
    "ability": "能力描述",
    "card_alias": "卡牌别称",
    "card_group": "所属集团",
    "image": "图片URL",
    "ability_list": [  // 卡牌能力列表
        {
            "id": "ability-uuid",
            "ability_desc": "能力描述",
            "ability": {
                "type": "auto",
                "condition": "when_attacks",
                "effect": "power_boost_2000"
            }
        }
    ],
    "status": ["武装", "强化"],  // 特殊状态列表
    "normal_effect": {  // 普通效果（加攻/加暴）
        "power_boost": 2000,
        "critical_boost": 1
    },
    "additional_ability": [  // 被赋予的技能列表
        {
            "type": "attack_boost",
            "value": 3000,
            "duration": "until_end_of_turn"
        }
    ]
}
```

### 隐藏卡牌
当`show`为`false`时，Card对象只包含：
```json
{
    "show": false
}
```

### 字段说明
- **show**: 布尔值，控制是否显示卡牌详细信息
- **基础字段**: 包含卡牌的基本信息（id、name_cn、nation等）
- **ability_list**: 对象数组，存放卡牌的能力列表，参考card和cardability的关系
- **status**: 字符串数组，存放特殊状态（如：武装、强化等）
- **normal_effect**: JSON对象，存放普通效果（加攻、加暴等）
- **additional_ability**: 对象数组，存放被赋予的技能

## 主要功能

### 1. 游戏状态初始化

```python
from src.core.services.game_state_manager import GameStateManager

# 创建管理器实例
game_state_manager = GameStateManager(db_session)

# 初始化游戏状态（根据房间ID自动获取玩家和卡组信息）
initial_state = await game_state_manager.initialize_game_state(
    battle_id=battle_id,
    room_id=room_id
)
```

初始化过程会自动：
1. 根据room_id获取房间中的两个玩家
2. 根据user_id获取每个玩家的preset=0的卡组
3. 根据deck_id获取所有deck_card信息
4. 根据deck_zone将卡牌分配到不同区域：
   - ride -> ride (骑升轴)
   - main -> deck (卡组)
   - g -> gdeck (g卡组)
   - token -> token (衍生物)
5. 根据quantity添加多个Card对象
6. 根据card_id获取卡牌基础信息
7. 使用deck_card中的image作为Card的image属性

### 2. 保存和加载游戏状态

```python
# 保存游戏状态
game_state = {
    "battle_id": str(battle_id),
    "room_id": str(room_id),
    "player1_id": str(player1_id),
    "player2_id": str(player2_id),
    "first_player": str(player1_id),
    "turn_number": 1,
    "current_player": str(player1_id),
    "phase": "reset",
    "player1_field": {
        "ride": [{
            "show": True,
            "id": "card1",
            "name_cn": "骑升卡",
            "card_power": 8000,
            "shield": 5000,
            "ability_list": [
                {
                    "id": "ability1",
                    "ability_desc": "骑升能力",
                    "ability": {"type": "ride", "effect": "grade_boost"}
                }
            ],
            "status": ["武装"],
            "normal_effect": {"power_boost": 1000},
            "additional_ability": []
        }],
        "deck": [{"show": False}],  # 卡组中的卡牌隐藏
        "hand": [{
            "show": True,
            "id": "card2",
            "name_cn": "手牌卡",
            "card_power": 6000,
            "shield": 5000,
            "ability_list": [],
            "status": [],
            "normal_effect": {},
            "additional_ability": []
        }],
        "v": [{
            "show": True,
            "id": "card3",
            "name_cn": "先导者",
            "card_power": 9000,
            "shield": 5000,
            "ability_list": [
                {
                    "id": "ability2",
                    "ability_desc": "先导者能力",
                    "ability": {"type": "vanguard", "effect": "draw_1"}
                }
            ],
            "status": [],
            "normal_effect": {},
            "additional_ability": []
        }],
        "leftfront": [],
        "leftback": [],
        "rightfront": [],
        "rightback": [],
        "vback": [],
        "damage": [],
        "instruction": [],
        "trigger": [],
        "coa": [],
        "g": [],
        "gdeck": [{
            "show": True,
            "id": "card4",
            "name_cn": "g卡组卡",
            "card_power": 10000,
            "shield": 0,
            "ability_list": [],
            "status": [],
            "normal_effect": {},
            "additional_ability": []
        }],
        "token": [],
        "seal": [],
        "effect": {}
    },
    "player2_field": {
        "ride": [],
        "deck": [{"show": False}],  # 对手卡组隐藏
        "hand": [{"show": False}],  # 对手手牌隐藏
        "v": [{"show": True, "id": "card5", "name_cn": "对手先导者"}],  # 先导者可见
        "leftfront": [],
        "leftback": [],
        "rightfront": [],
        "rightback": [],
        "vback": [],
        "damage": [],
        "instruction": [],
        "trigger": [],
        "coa": [],
        "g": [],
        "gdeck": [],
        "token": [],
        "seal": [],
        "effect": {}
    }
}

success = await game_state_manager.save_game_state(battle_id, game_state)

# 加载游戏状态
loaded_state = await game_state_manager.load_game_state(battle_id)
```

### 3. 更新游戏状态

```python
# 部分更新游戏状态
updates = {
    "turn_number": 2,
    "current_player": str(player2_id),
    "phase": "draw"
}

success = await game_state_manager.update_game_state(battle_id, updates)
```

### 4. 更新玩家场面

```python
# 更新指定玩家的完整场面情况
field_data = {
    "ride": [{"id": "card1", "name": "骑升卡"}],
    "deck": [{"id": "card2", "name": "卡组卡"}],
    "hand": [{"id": "card3", "name": "手牌卡"}],
    "v": [{"id": "card4", "name": "先导者"}],
    "leftfront": [{"id": "card5", "name": "左前卫"}],
    "leftback": [],
    "rightfront": [],
    "rightback": [],
    "vback": [],
    "damage": [],
    "instruction": [],
    "trigger": [],
    "coa": [],
    "g": [],
    "seal": [],
    "effect": {"effect1": {"type": "attack_boost", "value": 2000}}
}

success = await game_state_manager.update_player_field(battle_id, player_id, field_data)

# 获取指定玩家的场面情况
field = await game_state_manager.get_player_field(battle_id, player_id)
```

### 5. 更新特定场面区域

```python
# 更新玩家的手牌区域
hand_cards = [{"id": "card1", "name": "手牌1"}, {"id": "card2", "name": "手牌2"}]
success = await game_state_manager.update_player_field_area(battle_id, player_id, "hand", hand_cards)

# 更新玩家的永续效果
effects = {"effect1": {"type": "attack_boost", "value": 2000}}
success = await game_state_manager.update_player_field_area(battle_id, player_id, "effect", effects)

# 获取玩家的特定区域
hand = await game_state_manager.get_player_field_area(battle_id, player_id, "hand")
v_cards = await game_state_manager.get_player_field_area(battle_id, player_id, "v")
```

### 6. Card对象管理

```python
# 从数据库卡牌信息创建Card对象
card_data = {
    "id": "card-uuid",
    "name_cn": "示例卡牌",
    "nation": "圣域联合王国",
    "clan": "皇家骑士团",
    "grade": 3,
    "card_power": 9000,
    "shield": 5000,
    "critical": 1,
    "image_url": "https://example.com/image.jpg"
}

# 卡牌能力列表
ability_list = [
    {
        "id": "ability-uuid-1",
        "ability_desc": "自动能力：攻击时，力量+2000",
        "ability": {
            "type": "auto",
            "condition": "when_attacks",
            "effect": "power_boost_2000"
        }
    },
    {
        "id": "ability-uuid-2", 
        "ability_desc": "永续能力：力量+1000",
        "ability": {
            "type": "continuous",
            "effect": "power_boost_1000"
        }
    }
]

# 创建完整的Card对象
card = game_state_manager.create_card_object(
    card_data=card_data,
    show=True,
    ability_list=ability_list,
    status=["武装"],
    normal_effect={"power_boost": 2000},
    additional_ability=[{"type": "attack_boost", "value": 3000}]
)

# 创建隐藏的Card对象
hidden_card = game_state_manager.create_hidden_card()
# 返回: {"show": False}

# 验证Card对象
is_valid, errors = game_state_manager.validate_card_object(card)
if not is_valid:
    print(f"Card对象无效: {errors}")

# 转换Card对象为隐藏状态
hidden = game_state_manager.convert_card_to_hidden(card)
# 返回: {"show": False}

# 根据可见性过滤Card对象列表
visible_card_ids = ["card1", "card2"]
filtered_cards = game_state_manager.filter_cards_by_visibility(
    cards=[card1, card2, card3], 
    visible_card_ids=visible_card_ids
)
```

### 7. 回合管理

```python
# 进入下一回合
success = await game_state_manager.next_turn(battle_id)

# 设置回合阶段
success = await game_state_manager.set_phase(battle_id, "draw")
```

### 8. 回合阶段管理

```python
# 检查阶段是否有效
is_valid = game_state_manager.is_valid_phase("draw")

# 获取阶段描述
description = game_state_manager.get_phase_description("battle_attack")
# 返回: "攻击阶段"

# 检查是否为战斗子阶段
is_battle = game_state_manager.is_battle_subphase("battle_attack")
# 返回: True
```

### 9. 场面区域管理

```python
# 检查场面区域是否有效
is_valid = game_state_manager.is_valid_field_area("hand")

# 获取场面区域描述
description = game_state_manager.get_field_area_description("v")
# 返回: "先导者"
```

### 10. 游戏状态验证

```python
# 验证游戏状态的有效性
is_valid, errors = await game_state_manager.validate_game_state(game_state)

if not is_valid:
    print(f"游戏状态无效: {errors}")
```

### 11. 断线重连支持

```python
# 获取用于重连的游戏状态
reconnect_state = await game_state_manager.get_game_state_for_reconnect(
    battle_id=battle_id,
    player_id=player_id
)
```

### 12. 游戏结束清理

```python
# 游戏结束时清理状态
await game_state_manager.cleanup_game_state(battle_id)
```

## 游戏状态结构

游戏状态是一个JSON对象，包含以下主要字段：

```json
{
    "battle_id": "对战ID",
    "room_id": "房间ID",
    "player1_id": "玩家1的user_id",
    "player2_id": "玩家2的user_id",
    "first_player": "优先出牌的玩家user_id",
    "turn_number": 1,
    "current_player": "当前回合的玩家user_id",
    "phase": "回合阶段名称",
    "player1_field": {
        "ride": [{"id": "card1", "name": "骑升卡"}],
        "deck": [{"id": "card2", "name": "卡组卡"}],
        "hand": [{"id": "card3", "name": "手牌卡"}],
        "v": [{"id": "card4", "name": "先导者"}],
        "leftfront": [],
        "leftback": [],
        "rightfront": [],
        "rightback": [],
        "vback": [],
        "damage": [],
        "instruction": [],
        "trigger": [],
        "coa": [],
        "g": [],
        "gdeck": [{"id": "card5", "name": "g卡组卡"}],
        "token": [],
        "seal": [],
        "effect": {}
    },
    "player2_field": {
        "ride": [],
        "deck": [],
        "hand": [],
        "v": [],
        "leftfront": [],
        "leftback": [],
        "rightfront": [],
        "rightback": [],
        "vback": [],
        "damage": [],
        "instruction": [],
        "trigger": [],
        "coa": [],
        "g": [],
        "gdeck": [],
        "token": [],
        "seal": [],
        "effect": {}
    },
    "created_at": "创建时间",
    "updated_at": "更新时间"
}
```

### 字段说明

- **battle_id**: 对战记录的唯一标识
- **room_id**: 房间ID
- **player1_id**: 第一个玩家的用户ID
- **player2_id**: 第二个玩家的用户ID
- **first_player**: 优先出牌的玩家ID（通常是先手玩家）
- **turn_number**: 当前回合数，从1开始
- **current_player**: 当前正在行动的玩家ID
- **phase**: 当前回合的阶段（必须是预定义的阶段之一）
- **player1_field**: 玩家1的场面情况，包含所有卡牌区域和永续效果
- **player2_field**: 玩家2的场面情况，包含所有卡牌区域和永续效果

### 场面区域说明

每个玩家的场面包含16个区域：

**卡牌区域（数组格式）**：
- `ride`: 骑升轴 - 存放骑升卡牌
- `deck`: 卡组 - 存放剩余卡牌
- `hand`: 手牌 - 存放手牌
- `v`: 先导者 - 存放先导者卡牌
- `leftfront`: 左前 - 左前卫位置
- `leftback`: 左后 - 左后卫位置
- `rightfront`: 右前 - 右前卫位置
- `rightback`: 右后 - 右后卫位置
- `vback`: v后 - 先导者后方位置
- `damage`: 伤害区 - 存放伤害卡牌
- `instruction`: 指令区 - 存放指令卡牌
- `trigger`: 判定区 - 存放触发卡牌
- `coa`: 纹章 - 存放纹章卡牌
- `g`: g区 - 存放g区卡牌
- `gdeck`: g卡组 - 存放g卡组卡牌
- `token`: 衍生物 - 存放衍生物卡牌
- `seal`: 封存 - 存放封存卡牌

**效果区域（对象格式）**：
- `effect`: 永续效果 - 存放永续效果（JSON格式，默认为空对象）

## 回合阶段流转

游戏支持以下回合阶段，每个玩家的回合依次流转：

1. **reset** - 重置阶段：回合开始时的重置操作
2. **draw** - 抽卡阶段：玩家抽卡
3. **ride** - 骑升阶段：玩家进行骑升操作
4. **main** - 主要阶段：玩家进行主要操作
5. **battle** - 战斗阶段：进入战斗流程
   - **battle_start** - 战斗开始
   - **battle_attack** - 攻击阶段
   - **battle_defence** - 防御阶段
   - **battle_trigger** - 触发阶段
   - **battle_damage** - 伤害阶段
   - **battle_end** - 战斗结束
6. **turnend** - 回合结束：回合结束时的清理操作

## 集成到现有代码

### 在 BattleService 中使用

```python
from src.core.services.game_state_manager import GameStateManager

class BattleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.game_state_manager = GameStateManager(db)
    
    async def create_battle_from_room(self, room_id: UUID, battle_type: str = "casual") -> Battle:
        # 创建对战记录
        battle = Battle(...)
        self.db.add(battle)
        await self.db.commit()
        await self.db.refresh(battle)
        
        # 初始化游戏状态（根据房间ID自动获取玩家和卡组信息）
        initial_game_state = await self.game_state_manager.initialize_game_state(
            battle_id=battle.id,
            room_id=room_id
        )
        
        return battle
    
    # 便捷的游戏状态管理方法
    async def get_game_state(self, battle_id: UUID) -> Optional[Dict[str, Any]]:
        """获取游戏状态"""
        return await self.game_state_manager.load_game_state(battle_id)
    
    async def update_game_state(self, battle_id: UUID, updates: Dict[str, Any]) -> bool:
        """更新游戏状态"""
        return await self.game_state_manager.update_game_state(battle_id, updates)
    
    async def get_player_field(self, battle_id: UUID, player_id: UUID) -> Optional[Dict[str, Any]]:
        """获取玩家场面"""
        return await self.game_state_manager.get_player_field(battle_id, player_id)
    
    async def update_player_field(self, battle_id: UUID, player_id: UUID, field_data: Dict[str, Any]) -> bool:
        """更新玩家场面"""
        return await self.game_state_manager.update_player_field(battle_id, player_id, field_data)
    
    async def next_turn(self, battle_id: UUID) -> bool:
        """进入下一回合"""
        return await self.game_state_manager.next_turn(battle_id)
    
    async def set_phase(self, battle_id: UUID, phase: str) -> bool:
        """设置回合阶段"""
        return await self.game_state_manager.set_phase(battle_id, phase)
    
    async def record_battle_action(self, battle_id: UUID, player_id: UUID, 
                                 action_type: str, action_data: Dict[str, Any],
                                 record_game_state: bool = True) -> BattleAction:
        """记录对战操作（包含游戏状态）"""
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
        # ... 保存到数据库
        return battle_action
```

### 使用示例

```python
# 创建对战并自动初始化游戏状态
battle_service = BattleService(db_session)
battle = await battle_service.create_battle_from_room(room_id, "casual")

# 获取游戏状态
game_state = await battle_service.get_game_state(battle.id)

# 更新游戏状态
success = await battle_service.update_game_state(battle.id, {
    "turn_number": 2,
    "current_player": str(player2_id),
    "phase": "draw"
})

# 获取玩家场面
player_field = await battle_service.get_player_field(battle.id, player_id)

# 更新玩家场面
success = await battle_service.update_player_field(battle.id, player_id, new_field_data)

# 进入下一回合
success = await battle_service.next_turn(battle.id)

# 设置回合阶段
success = await battle_service.set_phase(battle.id, "battle")

# 记录操作（包含游戏状态）
await battle_service.record_battle_action(
    battle_id=battle.id,
    player_id=player_id,
    action_type="play_card",
    action_data={"card_id": "card1", "target_area": "leftfront"},
    record_game_state=True  # 记录操作后的游戏状态
)
```

## 错误处理

所有方法都包含适当的错误处理和日志记录：

```python
try:
    result = await game_state_manager.save_game_state(battle_id, game_state)
    if not result:
        logger.error("保存游戏状态失败")
        # 处理错误
except Exception as e:
    logger.error(f"游戏状态操作异常: {str(e)}")
    # 处理异常
```

## 注意事项

1. **玩家数量**: 卡牌游戏严格限制为2个玩家，初始化时会验证玩家数量
2. **回合阶段**: 只能使用预定义的回合阶段，无效阶段会被拒绝
3. **场面区域**: 只能使用预定义的场面区域，无效区域会被拒绝
4. **Card对象**: 所有卡牌区域中的元素都必须是Card对象格式
5. **可见性控制**: 使用Card对象的show字段控制卡牌信息的可见性
6. **数据库事务**: 所有数据库操作都在事务中执行，确保数据一致性
7. **状态验证**: 建议在关键操作前验证游戏状态的有效性
8. **场面数据**: 所有卡牌区域都是数组格式，永续效果是对象格式
9. **回合管理**: 回合数从1开始，每次玩家2的回合结束后回合数+1
10. **阶段管理**: 回合阶段是字符串格式，必须使用预定义的阶段名称
11. **战斗子阶段**: 战斗阶段包含多个子阶段，可以通过 `is_battle_subphase()` 方法检查
12. **卡牌能力**: ability_list字段存放卡牌的能力列表，参考card和cardability的关系
13. **卡牌效果**: normal_effect和additional_ability字段用于存储卡牌效果
14. **特殊状态**: status字段用于存储卡牌的特殊状态（如武装、强化等）
15. **初始化逻辑**: 初始化时会自动根据room_id获取玩家和卡组信息
16. **卡组映射**: deck_zone映射关系：ride->ride, main->deck, g->gdeck, token->token
17. **卡牌数量**: 根据deck_card的quantity字段添加多个Card对象
18. **图片属性**: 使用deck_card中的image字段作为Card的image属性
19. **性能考虑**: 频繁的状态更新可能影响性能，考虑批量更新或缓存机制
20. **数据备份**: 重要的游戏状态变更应该记录到 `BattleAction` 表中用于回放
```

### 在 WebSocket 处理中使用

```python
async def handle_game_action(websocket, message):
    battle_id = message.get("battle_id")
    player_id = message.get("player_id")
    action_type = message.get("action_type")
    
    # 创建BattleService实例
    battle_service = BattleService(db_session)
    
    # 加载当前游戏状态
    game_state = await battle_service.get_game_state(battle_id)
    if not game_state:
        await websocket.send_json({"error": "游戏状态不存在"})
        return
    
    # 处理游戏逻辑
    if action_type == "play_card":
        # 从手牌移动到场上
        hand_cards = await battle_service.game_state_manager.get_player_field_area(battle_id, player_id, "hand")
        
        # 找到要使用的卡牌
        card_id = message.get("card_id")
        target_area = message.get("target_area")  # 如 "leftfront"
        
        # 从手牌中移除卡牌
        new_hand = [card for card in hand_cards if card.get("id") != card_id]
        await battle_service.game_state_manager.update_player_field_area(battle_id, player_id, "hand", new_hand)
        
        # 添加到场上位置
        if battle_service.game_state_manager.is_valid_field_area(target_area):
            current_area = await battle_service.game_state_manager.get_player_field_area(battle_id, player_id, target_area)
            
            # 找到原始卡牌信息
            original_card = next((card for card in hand_cards if card.get("id") == card_id), None)
            if original_card:
                # 创建新的Card对象，可能添加状态或效果
                new_card = battle_service.game_state_manager.create_card_object(
                    card_data=original_card,
                    show=True,
                    ability_list=original_card.get("ability_list", []),
                    status=original_card.get("status", []) + ["已召唤"],
                    normal_effect=original_card.get("normal_effect", {}),
                    additional_ability=original_card.get("additional_ability", [])
                )
                current_area.append(new_card)
                await battle_service.game_state_manager.update_player_field_area(battle_id, player_id, target_area, current_area)
        
        # 记录操作
        await battle_service.record_battle_action(
            battle_id=battle_id,
            player_id=player_id,
            action_type="play_card",
            action_data={"card_id": card_id, "target_area": target_area}
        )
    
    elif action_type == "add_effect":
        # 给卡牌添加效果
        card_id = message.get("card_id")
        area = message.get("area")
        effect = message.get("effect")
        
        if battle_service.game_state_manager.is_valid_field_area(area):
            area_cards = await battle_service.game_state_manager.get_player_field_area(battle_id, player_id, area)
            
            # 找到目标卡牌并添加效果
            for i, card in enumerate(area_cards):
                if card.get("id") == card_id:
                    # 更新卡牌效果
                    updated_card = card.copy()
                    updated_card["normal_effect"] = {**card.get("normal_effect", {}), **effect}
                    area_cards[i] = updated_card
                    await battle_service.game_state_manager.update_player_field_area(battle_id, player_id, area, area_cards)
                    break
        
        # 记录操作
        await battle_service.record_battle_action(
            battle_id=battle_id,
            player_id=player_id,
            action_type="add_effect",
            action_data={"card_id": card_id, "area": area, "effect": effect}
        )
    
    elif action_type == "hide_opponent_cards":
        # 隐藏对手的卡牌（只显示show=False）
        opponent_id = message.get("opponent_id")
        area = message.get("area")
        
        if battle_service.game_state_manager.is_valid_field_area(area):
            opponent_cards = await battle_service.game_state_manager.get_player_field_area(battle_id, opponent_id, area)
            hidden_cards = battle_service.game_state_manager.convert_cards_to_hidden(opponent_cards)
            await battle_service.game_state_manager.update_player_field_area(battle_id, opponent_id, area, hidden_cards)
        
        # 记录操作
        await battle_service.record_battle_action(
            battle_id=battle_id,
            player_id=player_id,
            action_type="hide_opponent_cards",
            action_data={"opponent_id": opponent_id, "area": area}
        )
    
    elif action_type == "end_turn":
        # 进入下一回合
        success = await battle_service.next_turn(battle_id)
        if success:
            # 记录操作
            await battle_service.record_battle_action(
                battle_id=battle_id,
                player_id=player_id,
                action_type="end_turn",
                action_data={}
            )
    
    elif action_type == "set_phase":
        # 设置回合阶段
        phase = message.get("phase")
        if battle_service.game_state_manager.is_valid_phase(phase):
            success = await battle_service.set_phase(battle_id, phase)
            if success:
                # 记录操作
                await battle_service.record_battle_action(
                    battle_id=battle_id,
                    player_id=player_id,
                    action_type="set_phase",
                    action_data={"phase": phase}
                )
    
    # 发送更新后的游戏状态给所有玩家
    updated_game_state = await battle_service.get_game_state(battle_id)
    await websocket.send_json({
        "type": "game_state_update",
        "game_state": updated_game_state
    })
```

### 断线重连处理

```python
async def handle_reconnect(websocket, message):
    battle_id = message.get("battle_id")
    player_id = message.get("player_id")
    
    battle_service = BattleService(db_session)
    
    # 获取用于重连的游戏状态
    reconnect_state = await battle_service.get_game_state_for_reconnect(battle_id, player_id)
    
    if reconnect_state:
        # 发送重连状态
        await websocket.send_json({
            "type": "reconnect_success",
            "game_state": reconnect_state
        })
        
        # 记录重连操作
        await battle_service.record_battle_action(
            battle_id=battle_id,
            player_id=player_id,
            action_type="reconnect",
            action_data={"timestamp": datetime.utcnow().isoformat()},
            record_game_state=False  # 重连不需要记录游戏状态
        )
    else:
        await websocket.send_json({
            "type": "reconnect_failed",
            "error": "无法获取游戏状态"
        })