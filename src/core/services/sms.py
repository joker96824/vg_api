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

    async def send_code(self, mobile: str, scene: str) -> Dict[str, Any]:
        """发送验证码"""
        logger.info(f"开始发送验证码: mobile={mobile}, scene={scene}")
        
        # 检查发送频率
        if not self._check_rate_limit(mobile):
            wait_time = self._get_wait_time(mobile)
            logger.warning(f"发送频率限制: mobile={mobile}, wait_time={wait_time}")
            return {"wait": wait_time}

        # 生成验证码
        code = self._generate_code()
        logger.info(f"生成验证码: mobile={mobile}, code={code}")
        
        # 存储验证码
        self._save_code(mobile, code, scene)
        
        # TODO: 调用短信服务发送验证码
        # 这里需要集成实际的短信服务，如阿里云、腾讯云等
        
        return {"wait": 60}

    async def verify_code(self, mobile: str, code: str, scene: str) -> bool:
        """验证验证码"""
        key = f"SMS:CODE:{mobile}:{scene}"
        logger.info(f"开始验证验证码: mobile={mobile}, scene={scene}")
        
        try:
            stored_code = self.redis.get(key)
            logger.info(f"Redis中存储的验证码: key={key}, stored_code={stored_code}")
            
            if not stored_code:
                logger.warning(f"验证码不存在: key={key}")
                return False
                
            if stored_code != code:
                logger.warning(f"验证码不匹配: input={code}, stored={stored_code}")
                return False
                
            # 验证成功后删除验证码
            self.redis.delete(key)
            logger.info(f"验证码验证成功: mobile={mobile}")
            return True
            
        except Exception as e:
            logger.error(f"验证码验证异常: {str(e)}")
            return False

    def _check_rate_limit(self, mobile: str) -> bool:
        """检查发送频率限制"""
        key = f"SMS:LIMIT:{mobile}"
        count = self.redis.get(key)
        
        if count and int(count) >= 5:  # 每日最多5次
            return False
            
        # 增加计数
        if not count:
            self.redis.setex(key, 86400, 1)  # 24小时过期
        else:
            self.redis.incr(key)
            
        return True

    def _get_wait_time(self, mobile: str) -> int:
        """获取等待时间"""
        key = f"SMS:LIMIT:{mobile}"
        ttl = self.redis.ttl(key)
        return max(ttl, 60)

    def _generate_code(self) -> str:
        """生成6位数字验证码"""
        return str(random.randint(100000, 999999))

    def _save_code(self, mobile: str, code: str, scene: str) -> None:
        """保存验证码到Redis"""
        key = f"SMS:CODE:{mobile}:{scene}"
        try:
            self.redis.setex(key, 300, code)  # 5分钟过期
            logger.info(f"验证码保存成功: key={key}")
        except Exception as e:
            logger.error(f"验证码保存失败: {str(e)}")
            raise 