import hashlib
from jose import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models.user import User
from src.core.services.sms import SMSService
import bcrypt

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sms_service = SMSService(session)

    async def register(
        self,
        mobile: str,
        sms_code: str,
        password: str,
        nickname: Optional[str] = None
    ) -> Dict[str, Any]:
        """用户注册"""
        # 验证短信验证码
        if not await self.sms_service.verify_code(mobile, sms_code, "register"):
            raise ValueError("短信验证码错误或已过期")

        # 检查手机号是否已注册
        stmt = select(User).where(User.mobile_hash == self._hash_mobile(mobile))
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("该手机号已注册")

        # 创建用户
        user = User(
            mobile=mobile,
            mobile_hash=self._hash_mobile(mobile),
            password_hash=self._hash_password(password),
            nickname=nickname or f"用户{mobile[-4:]}"
        )
        self.session.add(user)
        await self.session.flush()

        # 生成JWT令牌
        token = self._generate_token(user.id)

        # 创建会话记录
        await self._create_session(user.id, token)

        await self.session.commit()
        return {
            "user": {
                "id": str(user.id),
                "mobile": mobile,
                "nickname": user.nickname
            },
            "token": token
        }

    def _hash_mobile(self, mobile: str) -> str:
        """手机号哈希"""
        return hashlib.sha256(mobile.encode()).hexdigest()

    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def _generate_token(self, user_id: str) -> str:
        """生成JWT令牌"""
        payload = {
            "sub": str(user_id),
            "exp": datetime.utcnow() + timedelta(hours=4),
            "iat": datetime.utcnow()
        }
        return jwt.encode(
            payload,
            os.getenv('JWT_SECRET_KEY', 'your-secret-key'),
            algorithm=os.getenv('JWT_ALGORITHM', 'HS256')
        )

    async def _create_session(self, user_id: str, token: str) -> None:
        """创建会话记录"""
        from src.core.models.session import Session
        session = Session(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            device_fingerprint="",  # 需要从请求中获取
            ip="",  # 需要从请求中获取
            expires_at=datetime.utcnow() + timedelta(hours=4),
            last_activity_at=datetime.utcnow()
        )
        self.session.add(session) 