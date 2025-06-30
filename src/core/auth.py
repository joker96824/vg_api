from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.deps import get_db
from src.core.models.user import User
from src.core.services.match import MatchService
import os
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取当前用户信息"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            os.getenv('JWT_SECRET_KEY', 'your-secret-key'),
            algorithms=[os.getenv('JWT_ALGORITHM', 'HS256')]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证信息"
            )
    except JWTError:
        # 尝试从token中提取用户ID来取消匹配
        try:
            # 不验证签名，只解码获取用户ID
            payload = jwt.decode(
                credentials.credentials,
                options={"verify_signature": False}
            )
            user_id = payload.get("sub")
            if user_id:
                await _cancel_user_match(user_id)
        except:
            pass  # 如果无法解析token，忽略错误
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证信息"
        )

    # 查询用户信息
    stmt = select(User).where(User.id == user_id, User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # 用户不存在，取消匹配
        await _cancel_user_match(user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除"
        )

    return {
        "id": str(user.id),
        "mobile": user.mobile,
        "email": user.email,
        "nickname": user.nickname,
        "level": user.level,
        "avatar": user.avatar
    }

async def _cancel_user_match(user_id: str):
    """取消用户匹配状态"""
    try:
        # 获取数据库会话
        async for session in get_db():
            try:
                match_service = MatchService(session)
                result = await match_service.cancel_user_match(user_id)
                if result["success"]:
                    logger.info(f"用户登录失效，已自动取消匹配 - user_id: {user_id}")
                break
            except Exception as e:
                logger.error(f"取消用户匹配时发生错误 - user_id: {user_id}, 错误: {str(e)}")
            finally:
                await session.close()
    except Exception as e:
        logger.error(f"获取数据库会话失败: {str(e)}")

def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """验证管理员权限"""
    if current_user.get("level", 1) < 5:  # 假设level >= 2为管理员
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user 