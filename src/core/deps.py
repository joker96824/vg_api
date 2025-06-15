from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_session

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖函数"""
    async for session in get_session():
        try:
            yield session
        finally:
            await session.close() 