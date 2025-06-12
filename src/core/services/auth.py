import hashlib
from jose import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models.user import User
from src.core.models.session import Session
from src.core.models.login_log import LoginLog
from src.core.services.sms import SMSService
import bcrypt
import logging
import redis
from config.settings import settings
from src.core.services.captcha import CaptchaService
from fastapi import Request, UploadFile
from src.core.services.email import EmailService
from uuid import UUID

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
        password: str = "SealJump",  # 设置默认密码
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
            nickname=nickname or f"用户{mobile[-6:]}"  # 使用手机号后6位
        )
        self.session.add(user)
        await self.session.flush()

        # 生成JWT令牌
        token = await self._generate_token(user.id, user.level)

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

    def _get_password_error_count(self, account: str) -> int:
        """获取密码错误次数"""
        key = f"PASSWORD_ERROR:{account}"
        count = self.redis.get(key)
        if not count:
            # 设置过期时间为今天结束
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            ttl = int((today_end - datetime.now()).total_seconds())
            self.redis.setex(key, ttl, 0)
            return 0
        return int(count)

    def _increment_password_error(self, account: str) -> int:
        """增加密码错误次数"""
        key = f"PASSWORD_ERROR:{account}"
        count = self._get_password_error_count(account)
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        ttl = int((today_end - datetime.now()).total_seconds())
        
        if count == 0:
            self.redis.setex(key, ttl, 1)
        else:
            self.redis.incr(key)
            self.redis.expire(key, ttl)
            
        return count + 1

    def _is_account_locked(self, account: str) -> bool:
        """检查账号是否被锁定"""
        return self._get_password_error_count(account) >= 5

    async def login(
        self,
        request: Request,
        mobile: str,
        password: str,
        captcha: Optional[str] = None,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """用户登录"""
        # 检查是否需要图形验证码
        captcha_key = f"LOGIN_CAPTCHA:{mobile}"
        captcha_required = self.redis.exists(captcha_key)
        
        # 如果需要图形验证码但未提供
        if captcha_required and not captcha:
            raise ValueError("需要图形验证码")
            
        # 如果提供了图形验证码，验证它
        if captcha:
            captcha_service = CaptchaService()
            if not await captcha_service.verify(request, captcha):
                raise ValueError("图形验证码错误")
            # 验证成功后删除验证码
            self.redis.delete(captcha_key)

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
            
            # 如果密码错误，设置需要图形验证码
            self.redis.setex(captcha_key, 300, "1")  # 5分钟内需要图形验证码
            
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

        # 密码正确，清除错误计数和图形验证码要求
        self.redis.delete(f"PASSWORD_ERROR:{mobile}")
        self.redis.delete(captcha_key)

        # 生成JWT令牌
        token = await self._generate_token(user.id, user.level)

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

    async def _generate_token(self, user_id: str, level: int, expires_hours: int = 4) -> str:
        """生成JWT令牌
        
        Args:
            user_id: 用户ID
            level: 用户级别
            expires_hours: token有效期（小时），默认4小时
        """
        # 查找用户信息
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在")
            
        payload = {
            "sub": str(user_id),
            "level": level,
            "mobile": user.mobile,
            "email": user.email,
            "nickname": user.nickname,
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
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

    async def _delete_session(self, token: str) -> None:
        """删除会话记录"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stmt = select(Session).where(
            Session.token_hash == token_hash,
            Session.is_deleted == False
        )
        result = await self.session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            session.is_deleted = True
            await self.session.commit()
            logger.info(f"已删除会话记录，token_hash: {token_hash[:10]}...")

    async def logout(self, token: str) -> None:
        """用户登出"""
        try:
            # 验证token
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET_KEY', 'your-secret-key'),
                algorithms=[os.getenv('JWT_ALGORITHM', 'HS256')]
            )
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("无效的token")
            
            # 删除会话
            await self._delete_session(token)
            
        except jwt.ExpiredSignatureError:
            raise ValueError("token已过期")
        except jwt.JWTError:
            raise ValueError("无效的token")

    def _clear_password_error(self, account: str) -> None:
        """清除密码错误计数"""
        key = f"PASSWORD_ERROR:{account}"
        self.redis.delete(key)
        logger.info(f"已清除 {account} 的密码错误计数")

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
            
        # 生成新令牌，有效期为40分钟
        new_token = await self._generate_token(user.id, user.level, expires_hours=40/60)
        
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
            "user": {
                "id": str(user.id),
                "mobile": user.mobile,
                "email": user.email,
                "nickname": user.nickname,
                "level": user.level
            },
            "token": new_token,
            "expires_at": (datetime.utcnow() + timedelta(hours=40/60)).isoformat()
        }

    async def update_nickname(
        self,
        user_id: str,
        new_nickname: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """修改用户昵称"""
        # 查找用户
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在或已被删除")
            
        # 更新昵称
        user.nickname = new_nickname
        
        # 记录修改日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=7,  # 修改昵称
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"昵称修改为：{new_nickname}"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "昵称修改成功",
            "data": {
                "nickname": new_nickname
            }
        }

    async def update_mobile(
        self,
        request: Request,
        user_id: str,
        new_mobile: str,
        sms_code: str,
        captcha: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """修改手机号"""
        # 验证图形验证码
        captcha_service = CaptchaService()
        if not await captcha_service.verify(request, captcha):
            raise ValueError("图形验证码错误")
            
        # 验证短信验证码
        verify_result = await self.sms_service.verify_code(new_mobile, sms_code, "change_mobile")
        if not verify_result["success"]:
            raise ValueError(verify_result["message"])
            
        # 检查新手机号是否已被使用
        stmt = select(User).where(User.mobile_hash == self._hash_mobile(new_mobile))
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("该手机号已被使用")
            
        # 查找用户
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在或已被删除")
            
        # 更新手机号
        old_mobile = user.mobile
        user.mobile = new_mobile
        user.mobile_hash = self._hash_mobile(new_mobile)
        
        # 记录修改日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=8,  # 修改手机号
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"手机号从 {old_mobile} 修改为 {new_mobile}"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "手机号修改成功",
            "data": {
                "mobile": new_mobile
            }
        }

    async def update_avatar(
        self,
        user_id: str,
        avatar_url: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """修改用户头像"""
        # 查找用户
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在或已被删除")
            
        # 更新头像
        user.avatar = avatar_url
        
        # 记录修改日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=9,  # 修改头像
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"头像已更新"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "头像修改成功",
            "data": {
                "avatar": avatar_url
            }
        }

    async def upload_avatar(
        self,
        user_id: str,
        file: UploadFile,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """上传用户头像
        
        Args:
            user_id: 用户ID
            file: 上传的文件
            ip: 用户IP
            device_fingerprint: 设备指纹
            
        Returns:
            Dict[str, Any]: 包含上传结果的字典
        """
        # 验证文件类型
        if not file.content_type.startswith('image/'):
            raise ValueError("只支持上传图片文件")
            
        # 验证文件大小（限制为2MB）
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB
        while chunk := await file.read(chunk_size):
            file_size += len(chunk)
            if file_size > 2 * 1024 * 1024:  # 2MB
                raise ValueError("文件大小不能超过2MB")
                
        # 重置文件指针
        await file.seek(0)
        
        # 生成文件名
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in ['jpg', 'jpeg', 'png', 'gif']:
            raise ValueError("只支持jpg、jpeg、png、gif格式的图片")
            
        # 生成唯一的文件名
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"avatar_{user_id}_{timestamp}_Unaudited.{file_ext}"
        
        # 保存文件
        upload_dir = os.path.join(settings.UPLOAD_DIR, 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, 'wb') as f:
            while chunk := await file.read(chunk_size):
                f.write(chunk)
                
        # 生成访问URL
        avatar_url = f"/uploads/avatars/{filename}"
        
        # 更新用户头像
        return await self.update_avatar(
            user_id=user_id,
            avatar_url=avatar_url,
            ip=ip,
            device_fingerprint=device_fingerprint
        )

    def _hash_email(self, email: str) -> str:
        """邮箱哈希"""
        return hashlib.sha256(email.encode()).hexdigest()

    async def register_by_email(
        self,
        email: str,
        email_code: str,
        password: str = "SealJump",  # 设置默认密码
        nickname: Optional[str] = None,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """邮箱注册"""
        # 验证邮箱验证码
        email_service = EmailService()
        verify_result = await email_service.verify_code(email, email_code, "register")
        if not verify_result["success"]:
            raise ValueError(verify_result["message"])

        # 检查邮箱是否已注册
        stmt = select(User).where(User.email_hash == self._hash_email(email))
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("该邮箱已注册")

        # 创建用户
        user = User(
            email=email,
            email_hash=self._hash_email(email),
            password_hash=self._hash_password(password),
            nickname=nickname or f"用户{email.split('@')[0]}"  # 使用邮箱用户名部分
        )
        self.session.add(user)
        await self.session.flush()

        # 生成JWT令牌
        token = await self._generate_token(user.id, user.level)

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
                "email": email,
                "nickname": user.nickname,
                "level": user.level
            },
            "token": token
        }

    async def login_by_email(
        self,
        request: Request,
        email: str,
        password: str,
        captcha: Optional[str] = None,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """邮箱登录"""
        # 检查是否需要图形验证码
        captcha_key = f"LOGIN_CAPTCHA:{email}"
        captcha_required = self.redis.exists(captcha_key)
        
        # 如果需要图形验证码但未提供
        if captcha_required and not captcha:
            raise ValueError("需要图形验证码")
            
        # 如果提供了图形验证码，验证它
        if captcha:
            captcha_service = CaptchaService()
            if not await captcha_service.verify(request, captcha):
                raise ValueError("图形验证码错误")
            # 验证成功后删除验证码
            self.redis.delete(captcha_key)

        # 检查账号是否被锁定
        if self._is_account_locked(email):
            error_count = self._get_password_error_count(email)
            wait_time = self.redis.ttl(f"PASSWORD_ERROR:{email}")
            raise ValueError(f"账号已被锁定，今日剩余错误次数：{5-error_count}，请{wait_time}秒后重试")

        # 查找用户
        stmt = select(User).where(User.email_hash == self._hash_email(email))
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
            error_count = self._increment_password_error(email)
            remaining_attempts = 5 - error_count
            
            # 如果密码错误，设置需要图形验证码
            self.redis.setex(captcha_key, 300, "1")  # 5分钟内需要图形验证码
            
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

        # 密码正确，清除错误计数和图形验证码要求
        self.redis.delete(f"PASSWORD_ERROR:{email}")
        self.redis.delete(captcha_key)

        # 生成JWT令牌
        token = await self._generate_token(user.id, user.level)

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
                "email": user.email,
                "nickname": user.nickname,
                "level": user.level
            },
            "token": token
        }

    async def reset_password_by_email(
        self,
        email: str,
        old_password: str,
        new_password: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """通过邮箱修改密码"""
        # 查找用户
        stmt = select(User).where(User.email_hash == self._hash_email(email))
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
        self._clear_password_error(email)
        
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

    async def force_reset_password_by_email(
        self,
        email: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """强制重置邮箱用户的密码为默认密码"""
        # 查找用户
        stmt = select(User).where(User.email_hash == self._hash_email(email))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在")

        # 更新密码为默认密码
        default_password = "SealJump"
        user.password_hash = self._hash_password(default_password)
        
        # 清除密码错误计数
        self._clear_password_error(email)
        
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

    async def update_email(
        self,
        request: Request,
        user_id: str,
        new_email: str,
        email_code: str,
        captcha: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """修改邮箱"""
        # 验证图形验证码
        captcha_service = CaptchaService()
        if not await captcha_service.verify(request, captcha):
            raise ValueError("图形验证码错误")
            
        # 验证邮箱验证码
        email_service = EmailService()
        verify_result = await email_service.verify_code(new_email, email_code, "change_email")
        if not verify_result["success"]:
            raise ValueError(verify_result["message"])
            
        # 检查新邮箱是否已被使用
        stmt = select(User).where(User.email_hash == self._hash_email(new_email))
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("该邮箱已被使用")
            
        # 查找用户
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("用户不存在或已被删除")
            
        # 更新邮箱
        old_email = user.email
        user.email = new_email
        user.email_hash = self._hash_email(new_email)
        
        # 记录修改日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=10,  # 修改邮箱
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"邮箱从 {old_email} 修改为 {new_email}"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "邮箱修改成功",
            "data": {
                "email": new_email
            }
        }

    async def check_email_exists(self, email: str) -> bool:
        """检查邮箱是否存在"""
        stmt = select(User).where(User.email_hash == self._hash_email(email))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_all_users(self) -> Dict[str, Any]:
        """获取所有用户信息"""
        # 查询所有未删除的用户
        stmt = select(User).where(User.is_deleted == False)
        result = await self.session.execute(stmt)
        users = result.scalars().all()
        
        # 转换为响应格式
        user_list = []
        for user in users:
            user_list.append({
                "id": str(user.id),
                "mobile": user.mobile,
                "email": user.email,
                "nickname": user.nickname,
                "level": user.level,
                "avatar": user.avatar
            })
            
        return {
            "total": len(user_list),
            "items": user_list
        }

    async def update_user_level(
        self,
        target_user_id: str,
        new_level: int,
        operator_id: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """更新用户等级"""
        # 查找目标用户
        stmt = select(User).where(User.id == target_user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("目标用户不存在或已被删除")
            
        # 更新用户等级
        old_level = user.level
        user.level = new_level
        
        # 记录修改日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=11,  # 修改用户等级
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"用户等级从 {old_level} 修改为 {new_level}，操作者ID：{operator_id}"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "用户等级修改成功",
            "data": {
                "user_id": str(user.id),
                "old_level": old_level,
                "new_level": new_level
            }
        }

    async def search_users(self, keyword: str, user_id: UUID) -> List[User]:
        """搜索用户"""
        try:
            # 尝试将关键词转换为UUID
            keyword_uuid = UUID(keyword)
            uuid_match = User.id == keyword_uuid
        except ValueError:
            # 如果转换失败，则不添加UUID匹配条件
            uuid_match = False

        # 构建查询条件
        conditions = [
            or_(
                User.email.ilike(f"%{keyword}%"),
                User.nickname.ilike(f"%{keyword}%"),
                uuid_match
            ),
            User.is_deleted == False,
            User.id != user_id
        ]

        # 获取数据
        result = await self.session.execute(
            select(User)
            .where(and_(*conditions))
            .order_by(desc(User.create_time))
        )
        users = result.scalars().all()
        
        # 将UUID转换为字符串
        for user in users:
            user.id = str(user.id)
            
        return users

    async def update_file_status(
        self,
        filename: str,
        new_status: str,
        operator_id: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """更新文件状态
        
        Args:
            filename: 文件名
            new_status: 新状态（'Valid' 或 'Unvalid'）
            operator_id: 操作者ID
            ip: 操作者IP
            device_fingerprint: 设备指纹
            
        Returns:
            Dict[str, Any]: 包含操作结果的字典
        """
        # 验证文件名格式
        if not '_Unaudited.' in filename:
            raise ValueError("文件名格式不正确，必须包含_Unaudited.")
            
        # 验证新状态
        if new_status not in ['Valid', 'Unvalid']:
            raise ValueError("新状态必须是'Valid'或'Unvalid'")
            
        # 构建文件路径
        upload_dir = os.path.join(settings.UPLOAD_DIR, 'avatars')
        old_path = os.path.join(upload_dir, filename)
        new_filename = filename.replace('_Unaudited.', f'_{new_status}.')
        new_path = os.path.join(upload_dir, new_filename)
        
        # 检查文件是否存在
        if not os.path.exists(old_path):
            raise ValueError("文件不存在")
            
        # 重命名文件
        try:
            os.rename(old_path, new_path)
        except Exception as e:
            raise ValueError(f"重命名文件失败：{str(e)}")
            
        # 记录操作日志
        login_log = LoginLog(
            user_id=operator_id,
            login_type=12,  # 文件状态更新
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"文件 {filename} 状态更新为 {new_status}"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "message": "文件状态更新成功",
            "data": {
                "old_filename": filename,
                "new_filename": new_filename
            }
        }

    async def get_unaudited_files(
        self,
        operator_id: str,
        ip: str = "",
        device_fingerprint: str = ""
    ) -> Dict[str, Any]:
        """获取所有未审核的文件
        
        Args:
            operator_id: 操作者ID
            ip: 操作者IP
            device_fingerprint: 设备指纹
            
        Returns:
            Dict[str, Any]: 包含未审核文件列表的字典
        """
        # 获取上传目录
        upload_dir = os.path.join(settings.UPLOAD_DIR, 'avatars')
        
        # 获取所有未审核的文件
        unaudited_files = []
        for filename in os.listdir(upload_dir):
            if '_Unaudited.' in filename:
                file_path = os.path.join(upload_dir, filename)
                file_stat = os.stat(file_path)
                unaudited_files.append({
                    "filename": filename,
                    "size": file_stat.st_size,
                    "create_time": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                    "modify_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })
                
        # 记录操作日志
        login_log = LoginLog(
            user_id=operator_id,
            login_type=13,  # 获取未审核文件列表
            ip=ip,
            device_info={"user_agent": device_fingerprint},
            status=1,  # 成功
            remark=f"获取未审核文件列表，共 {len(unaudited_files)} 个文件"
        )
        self.session.add(login_log)
        
        await self.session.commit()
        return {
            "success": True,
            "total": len(unaudited_files),
            "items": unaudited_files
        } 