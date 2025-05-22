import hashlib
from jose import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models.user import User
from src.core.models.session import Session
from src.core.models.login_log import LoginLog
from src.core.services.sms import SMSService
import bcrypt
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sms_service = SMSService(session)

    async def register(
        self,
        mobile: str,
        sms_code: str,
        password: str,
        nickname: Optional[str] = None,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """用户注册"""
        # 验证短信验证码
        verify_result = await self.sms_service.verify_code(mobile, sms_code, "register")
        if not verify_result["success"]:
            raise ValueError(verify_result["message"])

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

        # 创建登录日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=1,  # 注册登录
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1  # 成功
        )
        self.session.add(login_log)

        # 创建会话记录
        await self._create_session(user.id, token, ip, device_fingerprint)

        await self.session.commit()
        return {
            "user": {
                "id": str(user.id),
                "mobile": mobile,
                "nickname": user.nickname
            },
            "token": token
        }

    async def login(
        self,
        mobile: str,
        password: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """用户登录"""
        # 查找用户
        stmt = select(User).where(User.mobile_hash == self._hash_mobile(mobile))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            # 记录失败的登录日志
            login_log = LoginLog(
                login_type=2,  # 密码登录
                ip=ip,
                device_info={"user_agent": device_fingerprint},
                status=0,  # 失败
                remark="用户不存在"
            )
            self.session.add(login_log)
            await self.session.commit()
            raise ValueError("用户不存在")

        # 验证密码
        if not self._verify_password(password, user.password_hash):
            # 记录失败的登录日志
            login_log = LoginLog(
                user_id=user.id,
                login_type=2,  # 密码登录
                ip=ip,
                device_info={"user_agent": device_fingerprint},
                status=0,  # 失败
                remark="密码错误"
            )
            self.session.add(login_log)
            await self.session.commit()
            raise ValueError("密码错误")

        # 生成JWT令牌
        token = self._generate_token(user.id)

        # 创建登录日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=2,  # 密码登录
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1  # 成功
        )
        self.session.add(login_log)

        # 创建会话记录
        await self._create_session(user.id, token, ip, device_fingerprint)

        # 更新用户最后登录时间
        user.last_login_at = datetime.utcnow()
        
        await self.session.commit()
        return {
            "user": {
                "id": str(user.id),
                "mobile": user.mobile,
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

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), password_hash.encode())

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

    async def _create_session(
        self,
        user_id: str,
        token: str,
        ip: str,
        device_fingerprint: str
    ) -> None:
        """创建会话记录"""
        session = Session(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            device_fingerprint=device_fingerprint,
            ip=ip,
            expires_at=datetime.utcnow() + timedelta(hours=4),
            last_activity_at=datetime.utcnow()
        )
        self.session.add(session)

    async def logout(self, user_id: str, token: str) -> None:
        """用户登出"""
        # 查找并删除会话记录
        stmt = select(Session).where(
            Session.user_id == user_id,
            Session.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            Session.is_deleted == False
        )
        result = await self.session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            session.is_deleted = True
            await self.session.commit()
            
        # 记录登出日志
        login_log = LoginLog(
            user_id=user_id,
            login_type=3,  # 登出
            ip="",  # 登出时可能没有IP信息
            device_info={},
            status=1  # 成功
        )
        self.session.add(login_log)
        await self.session.commit() 