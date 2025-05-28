import random
import redis
import logging
from datetime import datetime, timedelta
from config.settings import settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import List, Optional

from ..config.email_config import email_settings

logger = logging.getLogger(__name__)

class EmailService:
    """邮件服务"""
    
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        # 从settings加载邮件配置
        self.smtp_server = settings.EMAIL_SMTP_SERVER
        self.smtp_port = settings.EMAIL_SMTP_PORT
        self.sender_email = settings.EMAIL_SENDER_EMAIL
        self.sender_password = settings.EMAIL_SENDER_PASSWORD

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
        if ip_count >= 50:  # 同一IP每天最多发送50次
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

        # 发送验证码邮件
        await self.send_verification_code(email, code)
        
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

    async def send_email(
        self,
        to_email: str,
        subject: str,
        content: str,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件内容
            cc_emails: 抄送邮箱列表
            bcc_emails: 密送邮箱列表
            
        Returns:
            bool: 是否发送成功
        """
        try:
            # 创建邮件对象
            msg = MIMEMultipart()
            
            # 添加基本邮件头
            msg['From'] = f"SealJump <{self.sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 添加额外的邮件头以提高可信度
            msg['Message-ID'] = f"<{datetime.now().strftime('%Y%m%d%H%M%S')}@{self.smtp_server}>"
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
            msg['X-Mailer'] = 'SealJump Mailer'
            msg['X-Priority'] = '1'  # 高优先级
            msg['X-MSMail-Priority'] = 'High'
            msg['Importance'] = 'high'
            
            # 添加抄送和密送
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            if bcc_emails:
                msg['Bcc'] = ', '.join(bcc_emails)
                
            # 添加邮件内容
            msg.attach(MIMEText(content, 'html', 'utf-8'))
            
            # 创建SSL上下文
            import ssl
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # 使用SMTP_SSL连接服务器并发送
            server = smtplib.SMTP_SSL(
                self.smtp_server,
                self.smtp_port,
                timeout=30,
                context=context,
                local_hostname='localhost'
            )
            
            try:
                server.login(self.sender_email, self.sender_password)
                
                # 获取所有收件人
                recipients = [to_email]
                if cc_emails:
                    recipients.extend(cc_emails)
                if bcc_emails:
                    recipients.extend(bcc_emails)
                
                server.sendmail(self.sender_email, recipients, msg.as_string())
                return True
            finally:
                try:
                    server.quit()
                except:
                    pass
        except Exception as e:
            logger.error(f"发送邮件失败: {str(e)}")
            return False

    async def send_verification_code(self, to_email: str, code: str) -> bool:
        """发送验证码邮件
        
        Args:
            to_email: 收件人邮箱
            code: 验证码
            
        Returns:
            bool: 是否发送成功
        """
        subject = "验证码 - 海豹乐园"
        content = f"""
        <html>
            <body>
                <h2>海豹乐园</h2>
                <p>您好，</p>
                <p>您的验证码是：<strong>{code}</strong></p>
                <p>验证码有效期为5分钟，请尽快使用。</p>
                <p>如果这不是您的操作，请忽略此邮件。</p>
                <br>
                <p>此致</p>
                <p>海豹团队</p>
            </body>
        </html>
        """
        return await self.send_email(to_email, subject, content)
        
    async def send_password_reset(self, to_email: str, reset_link: str) -> bool:
        """发送密码重置邮件
        
        Args:
            to_email: 收件人邮箱
            reset_link: 重置密码链接
            
        Returns:
            bool: 是否发送成功
        """
        subject = "密码重置 - 海豹乐园"
        content = f"""
        <html>
            <body>
                <h2>密码重置</h2>
                <p>您好，</p>
                <p>我们收到了重置您密码的请求。请点击下面的链接重置密码：</p>
                <p><a href="{reset_link}">{reset_link}</a></p>
                <p>此链接有效期为30分钟。</p>
                <p>如果这不是您的操作，请忽略此邮件。</p>
                <br>
                <p>此致</p>
                <p>海豹团队</p>
            </body>
        </html>
        """
        return await self.send_email(to_email, subject, content) 