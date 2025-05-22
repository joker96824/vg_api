from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_session
from src.core.models.user import User
import os

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_session)
) -> Dict:
    """
    获取当前用户信息
    """
    try:
        # 验证token
        token = credentials.credentials
        payload = jwt.decode(
            token,
            os.getenv('JWT_SECRET_KEY', 'your-secret-key'),
            algorithms=[os.getenv('JWT_ALGORITHM', 'HS256')]
        )
        
        # 检查token是否过期
        exp = payload.get('exp')
        if not exp or datetime.utcnow().timestamp() > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token已过期"
            )
            
        # 获取用户信息
        user_id = payload.get('sub')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的Token"
            )
            
        # 查询用户
        stmt = select(User).where(
            User.id == user_id,
            User.is_deleted == False
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
            
        return {
            "id": str(user.id),
            "mobile": user.mobile,
            "nickname": user.nickname
        }
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的Token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) 