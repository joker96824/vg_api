import asyncio
from sqlalchemy import text
from src.core.database import engine
from src.core.models.card import Card, CardRarity

async def check_tables():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        tables = [row[0] for row in result]
        print('Tables in database:', tables)

if __name__ == "__main__":
    asyncio.run(check_tables()) 