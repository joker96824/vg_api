import random
import string
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from fastapi import Request
import redis
from config.settings import settings

class CaptchaService:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )

    async def generate(self, request: Request) -> BytesIO:
        """生成图形验证码"""
        # 生成随机验证码
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        
        # 创建图片
        width = 120
        height = 40
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        
        # 添加干扰线
        for _ in range(5):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill='gray')
        
        # 添加验证码文字
        for i, char in enumerate(code):
            x = 20 + i * 20
            y = random.randint(5, 15)
            draw.text((x, y), char, fill='black')
        
        # 保存验证码到Redis
        session_id = request.session.get('session_id')
        if not session_id:
            session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            request.session['session_id'] = session_id
            
        self.redis.setex(
            f"CAPTCHA:{session_id}",
            180,  # 3分钟过期
            code
        )
        
        # 返回图片
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    async def verify(self, request: Request, code: str) -> bool:
        """验证图形验证码"""
        session_id = request.session.get('session_id')
        if not session_id:
            return False
            
        key = f"CAPTCHA:{session_id}"
        stored_code = self.redis.get(key)
        
        if not stored_code or stored_code.upper() != code.upper():
            return False
            
        # 验证成功后删除验证码
        self.redis.delete(key)
        return True 