import random
import redis
import logging
from datetime import datetime, timedelta
from config.settings import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )

    async def send_code(self, email: str, scene: str = "register", ip: str = "") -> dict:
        """发送邮箱验证码
        
        Args:
            email: 邮箱地址
            scene: 场景（register/change_email）
            ip: 请求IP
        """
        # 检查发送频率
        rate_key = f"EMAIL_RATE:{email}"
        if self.redis.exists(rate_key):
            return {
                "success": False,
                "code": "RATE_LIMIT",
                "message": "发送太频繁，请稍后再试"
            }

        # 检查IP限制
        ip_key = f"EMAIL_IP:{ip}"
        ip_count = int(self.redis.get(ip_key) or 0)
        if ip_count >= 20:  # 同一IP每天最多发送20次
            return {
                "success": False,
                "code": "IP_LIMIT",
                "message": "发送次数已达上限"
            }

        # 生成验证码
        code = str(random.randint(100000, 999999))
        
        # 保存验证码
        code_key = f"EMAIL_CODE:{scene}:{email}"
        self.redis.setex(code_key, 300, code)  # 5分钟有效期
        
        # 设置发送频率限制
        self.redis.setex(rate_key, 60, "1")  # 1分钟内不能重复发送
        
        # 更新IP计数
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        ttl = int((today_end - datetime.now()).total_seconds())
        self.redis.incr(ip_key)
        self.redis.expire(ip_key, ttl)

        # TODO: 调用邮件发送服务发送验证码
        # 这里需要实现实际的邮件发送逻辑
        logger.info(f"发送验证码到邮箱 {email}: {code}")

        return {
            "success": True,
            "code": "SEND_SUCCESS",
            "message": "验证码已发送"
        }

    async def verify_code(self, email: str, code: str, scene: str = "register") -> dict:
        """验证邮箱验证码
        
        Args:
            email: 邮箱地址
            code: 验证码
            scene: 场景（register/change_email）
        """
        code_key = f"EMAIL_CODE:{scene}:{email}"
        saved_code = self.redis.get(code_key)
        
        if not saved_code:
            return {
                "success": False,
                "code": "CODE_EXPIRED",
                "message": "验证码已过期"
            }
            
        if code != saved_code:
            return {
                "success": False,
                "code": "CODE_ERROR",
                "message": "验证码错误"
            }
            
        # 验证成功后删除验证码
        self.redis.delete(code_key)
        
        return {
            "success": True,
            "code": "VERIFY_SUCCESS",
            "message": "验证成功"
        } 