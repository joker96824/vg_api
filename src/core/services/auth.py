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
import redis
from config.settings import settings

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sms_service = SMSService(session)
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )

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
            nickname=nickname or f"用户{mobile[-4:]}",
            level=1  # 默认普通用户级别
        )
        self.session.add(user)
        await self.session.flush()

        # 生成JWT令牌
        token = self._generate_token(user.id, user.level)

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
                "nickname": user.nickname,
                "level": user.level
            },
            "token": token
        }

    def _get_password_error_count(self, mobile: str) -> int:
        """获取密码错误次数"""
        key = f"PASSWORD_ERROR:{mobile}"
        count = self.redis.get(key)
        if not count:
            # 设置过期时间为今天结束
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            ttl = int((today_end - datetime.now()).total_seconds())
            self.redis.setex(key, ttl, 0)
            return 0
        return int(count)

    def _increment_password_error(self, mobile: str) -> int:
        """增加密码错误次数"""
        key = f"PASSWORD_ERROR:{mobile}"
        count = self._get_password_error_count(mobile)
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        ttl = int((today_end - datetime.now()).total_seconds())
        
        if count == 0:
            self.redis.setex(key, ttl, 1)
        else:
            self.redis.incr(key)
            self.redis.expire(key, ttl)
            
        return count + 1

    def _is_account_locked(self, mobile: str) -> bool:
        """检查账号是否被锁定"""
        return self._get_password_error_count(mobile) >= 5

    async def login(
        self,
        mobile: str,
        password: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """用户登录"""
        # 检查账号是否被锁定
        if self._is_account_locked(mobile):
            error_count = self._get_password_error_count(mobile)
            wait_time = self.redis.ttl(f"PASSWORD_ERROR:{mobile}")
            raise ValueError(f"账号已被锁定，今日剩余错误次数：{5-error_count}，请{wait_time}秒后重试")

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
            # 增加密码错误次数
            error_count = self._increment_password_error(mobile)
            remaining_attempts = 5 - error_count
            
            # 记录失败的登录日志
            login_log = LoginLog(
                user_id=user.id,
                login_type=2,  # 密码登录
                ip=ip,
                device_info={"user_agent": device_fingerprint},
                status=0,  # 失败
                remark=f"密码错误，剩余尝试次数：{remaining_attempts}"
            )
            self.session.add(login_log)
            await self.session.commit()
            
            if remaining_attempts <= 0:
                raise ValueError("密码错误次数过多，账号已被锁定，请明天再试")
            else:
                raise ValueError(f"密码错误，剩余尝试次数：{remaining_attempts}")

        # 密码正确，清除错误计数
        self.redis.delete(f"PASSWORD_ERROR:{mobile}")

        # 生成JWT令牌
        token = self._generate_token(user.id, user.level)

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
                "nickname": user.nickname,
                "level": user.level
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

    def _generate_token(self, user_id: str, level: int) -> str:
        """生成JWT令牌"""
        payload = {
            "sub": str(user_id),
            "level": level,  # 添加用户级别信息
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

    def _clear_password_error(self, mobile: str) -> None:
        """清除密码错误计数"""
        key = f"PASSWORD_ERROR:{mobile}"
        self.redis.delete(key)
        logger.info(f"已清除手机号 {mobile} 的密码错误计数")

    async def reset_password(
        self,
        mobile: str,
        old_password: str,
        new_password: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """修改密码"""
        # 查找用户
        stmt = select(User).where(User.mobile_hash == self._hash_mobile(mobile))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在")

        # 验证旧密码
        if not self._verify_password(old_password, user.password_hash):
            raise ValueError("旧密码错误")

        # 更新密码
        user.password_hash = self._hash_password(new_password)
        
        # 清除密码错误计数
        self._clear_password_error(mobile)
        
        # 记录密码修改日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=4,  # 密码修改
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark="密码修改成功"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "密码修改成功"
        }

    async def clear_login_errors(self, mobile: str) -> Dict[str, Any]:
        """清除登录错误计数"""
        self._clear_password_error(mobile)
        return {
            "success": True,
            "message": "已清除登录错误计数"
        }

    async def force_reset_password(
        self,
        mobile: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """强制重置密码为默认密码"""
        # 查找用户
        stmt = select(User).where(User.mobile_hash == self._hash_mobile(mobile))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在")

        # 更新密码为默认密码
        default_password = "SealJump"
        user.password_hash = self._hash_password(default_password)
        
        # 清除密码错误计数
        self._clear_password_error(mobile)
        
        # 记录密码重置日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=5,  # 密码重置
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark="密码已重置为默认密码"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "密码已重置为默认密码"
        }

    async def check_session(self, user_id: str, token: str) -> Dict[str, Any]:
        """检查会话状态"""
        # 查找会话记录
        stmt = select(Session).where(
            Session.user_id == user_id,
            Session.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            Session.is_deleted == False,
            Session.expires_at > datetime.utcnow()
        )
        result = await self.session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return {
                "valid": False,
                "message": "会话已过期或无效"
            }
            
        # 计算剩余时间
        remaining_time = (session.expires_at - datetime.utcnow()).total_seconds()
        needs_refresh = remaining_time < 1800  # 剩余时间不足30分钟
        
        return {
            "valid": True,
            "remaining_time": int(remaining_time),
            "needs_refresh": needs_refresh,
            "expires_at": session.expires_at.isoformat()
        }

    async def refresh_token(
        self,
        user_id: str,
        old_token: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """刷新令牌"""
        # 查找用户
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在或已被删除")
            
        # 查找并删除旧会话
        stmt = select(Session).where(
            Session.user_id == user_id,
            Session.token_hash == hashlib.sha256(old_token.encode()).hexdigest(),
            Session.is_deleted == False
        )
        result = await self.session.execute(stmt)
        old_session = result.scalar_one_or_none()
        
        if old_session:
            old_session.is_deleted = True
            
        # 生成新令牌
        new_token = self._generate_token(user.id, user.level)
        
        # 创建新会话
        await self._create_session(user.id, new_token, ip, device_fingerprint)
        
        # 记录令牌刷新日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=6,  # 令牌刷新
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark="令牌刷新成功"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "token": new_token,
            "expires_at": (datetime.utcnow() + timedelta(hours=4)).isoformat()
        } 