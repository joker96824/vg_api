from pydantic_settings import BaseSettings

class EmailSettings(BaseSettings):
    """邮件配置"""
    SMTP_SERVER: str = "smtp.qq.com"
    SMTP_PORT: int = 587
    SENDER_EMAIL: str = ""  # 您的QQ邮箱
    SENDER_PASSWORD: str = ""  # 您的QQ邮箱授权码
    
    class Config:
        env_file = ".env"
        env_prefix = "EMAIL_"
        extra = "allow"  # 允许额外的字段

email_settings = EmailSettings() 