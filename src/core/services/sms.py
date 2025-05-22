import random
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )

    async def send_code(self, mobile: str, scene: str, ip: str) -> Dict[str, Any]:
        """发送验证码"""
        logger.info(f"开始发送验证码: mobile={mobile}, scene={scene}, ip={ip}")
        
        # 检查手机号发送频率
        mobile_count = self._get_mobile_count(mobile)
        if mobile_count >= 5:  # 每日最多5次
            wait_time = self._get_mobile_wait_time(mobile)
            logger.warning(f"手机号发送频率限制: mobile={mobile}, count={mobile_count}, wait_time={wait_time}")
            return {
                "success": False,
                "code": "MOBILE_LIMIT_EXCEEDED",
                "message": f"该手机号今日发送次数已达上限（{mobile_count}/5次）",
                "wait": wait_time,
                "count": mobile_count,
                "limit": 5
            }

        # 检查IP发送频率
        ip_count = self._get_ip_count(ip)
        if ip_count >= 20:  # 每日最多20次
            wait_time = self._get_ip_wait_time(ip)
            logger.warning(f"IP发送频率限制: ip={ip}, count={ip_count}, wait_time={wait_time}")
            return {
                "success": False,
                "code": "IP_LIMIT_EXCEEDED",
                "message": f"当前IP今日发送次数已达上限（{ip_count}/20次）",
                "wait": wait_time,
                "count": ip_count,
                "limit": 20
            }

        # 生成验证码
        code = self._generate_code()
        logger.info(f"生成验证码: mobile={mobile}, code={code}")
        
        # 存储验证码并增加计数
        self._save_code(mobile, code, scene, ip)
        
        # TODO: 调用短信服务发送验证码
        # 这里需要集成实际的短信服务，如阿里云、腾讯云等
        
        return {
            "success": True,
            "code": "SMS_SENT_SUCCESS",
            "message": "验证码发送成功",
            "wait": 60,
            "count": mobile_count + 1,
            "limit": 5
        }

    async def verify_code(self, mobile: str, code: str, scene: str) -> Dict[str, Any]:
        """验证验证码"""
        key = f"SMS:CODE:{mobile}:{scene}"
        logger.info(f"开始验证验证码: mobile={mobile}, scene={scene}")
        
        try:
            stored_code = self.redis.get(key)
            logger.info(f"Redis中存储的验证码: key={key}, stored_code={stored_code}")
            
            if not stored_code:
                logger.warning(f"验证码不存在: key={key}")
                return {
                    "success": False,
                    "code": "CODE_NOT_FOUND",
                    "message": "验证码不存在或已过期"
                }
                
            if stored_code != code:
                logger.warning(f"验证码不匹配: input={code}, stored={stored_code}")
                return {
                    "success": False,
                    "code": "CODE_MISMATCH",
                    "message": "验证码错误"
                }
                
            # 验证成功后删除验证码
            self.redis.delete(key)
            logger.info(f"验证码验证成功: mobile={mobile}")
            return {
                "success": True,
                "code": "VERIFY_SUCCESS",
                "message": "验证码验证成功"
            }
            
        except Exception as e:
            logger.error(f"验证码验证异常: {str(e)}")
            return {
                "success": False,
                "code": "VERIFY_ERROR",
                "message": "验证码验证过程发生错误"
            }

    def _get_mobile_count(self, mobile: str) -> int:
        """获取手机号今日发送次数"""
        key = f"SMS:MOBILE_COUNT:{mobile}"
        count = self.redis.get(key)
        if not count:
            # 设置过期时间为今天结束
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            ttl = int((today_end - datetime.now()).total_seconds())
            self.redis.setex(key, ttl, 0)
            return 0
        return int(count)

    def _get_ip_count(self, ip: str) -> int:
        """获取IP今日发送次数"""
        key = f"SMS:IP_COUNT:{ip}"
        count = self.redis.get(key)
        if not count:
            # 设置过期时间为今天结束
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            ttl = int((today_end - datetime.now()).total_seconds())
            self.redis.setex(key, ttl, 0)
            return 0
        return int(count)

    def _get_mobile_wait_time(self, mobile: str) -> int:
        """获取手机号等待时间"""
        key = f"SMS:MOBILE_COUNT:{mobile}"
        ttl = self.redis.ttl(key)
        return max(ttl, 60)

    def _get_ip_wait_time(self, ip: str) -> int:
        """获取IP等待时间"""
        key = f"SMS:IP_COUNT:{ip}"
        ttl = self.redis.ttl(key)
        return max(ttl, 60)

    def _generate_code(self) -> str:
        """生成6位数字验证码"""
        return str(random.randint(100000, 999999))

    def _save_code(self, mobile: str, code: str, scene: str, ip: str) -> None:
        """保存验证码到Redis并增加计数"""
        # 保存验证码
        key = f"SMS:CODE:{mobile}:{scene}"
        self.redis.setex(key, 300, code)  # 5分钟过期
        
        # 增加手机号计数
        mobile_key = f"SMS:MOBILE_COUNT:{mobile}"
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        ttl = int((today_end - datetime.now()).total_seconds())
        
        if not self.redis.exists(mobile_key):
            self.redis.setex(mobile_key, ttl, 1)
        else:
            self.redis.incr(mobile_key)
            self.redis.expire(mobile_key, ttl)  # 重新设置过期时间
            
        # 增加IP计数
        ip_key = f"SMS:IP_COUNT:{ip}"
        if not self.redis.exists(ip_key):
            self.redis.setex(ip_key, ttl, 1)
        else:
            self.redis.incr(ip_key)
            self.redis.expire(ip_key, ttl)  # 重新设置过期时间 