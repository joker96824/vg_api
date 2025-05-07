import asyncio
from src.core.database import engine, Base
from src.core.models.card import Card, CardRarity
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def import_test_data():
    # 创建会话
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # 创建测试卡牌
        card1 = Card(
            card_code="VG-TD01/001",
            name_cn="花椰菜",
            name_en="Cauliflower",
            card_power=5000,
            card_type="NORMAL",
            trigger_type="NONE",
            nation="ROYAL_PALADIN",
            clan="ROYAL_PALADIN",
            race="HUMAN",
            grade=0,
            skill="【自】：这个单位登场到R时，通过【费用】[计数爆发1]，抽1张卡。",
            flavor_text="「我的名字是花椰菜。请多关照！」",
            image_url="https://example.com/cards/vg-td01-001.jpg"
        )
        
        card2 = Card(
            card_code="VG-TD01/002",
            name_cn="光之剑 圣剑",
            name_en="Sword of Light, Excalibur",
            card_power=9000,
            card_type="NORMAL",
            trigger_type="NONE",
            nation="ROYAL_PALADIN",
            clan="ROYAL_PALADIN",
            race="WEAPON",
            grade=1,
            skill="【自】：这个单位登场到V时，通过【费用】[计数爆发1]，这个回合中，这个单位的力量+5000。",
            flavor_text="「这就是传说中的圣剑吗...」",
            image_url="https://example.com/cards/vg-td01-002.jpg"
        )
        
        # 添加卡牌稀有度
        rarity1 = CardRarity(
            card=card1,
            pack_name="TD01",
            rarity="R"
        )
        
        rarity2 = CardRarity(
            card=card2,
            pack_name="TD01",
            rarity="R"
        )
        
        # 添加到会话
        session.add_all([card1, card2, rarity1, rarity2])
        
        # 提交事务
        await session.commit()
        
        print("测试数据导入成功！")

if __name__ == "__main__":
    asyncio.run(import_test_data()) 