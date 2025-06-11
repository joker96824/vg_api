from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from fastapi import UploadFile
from .response import ResponseCode, SuccessResponse, ErrorResponse

class SendSMSRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    captcha: str
    scene: str = "register"

class RegisterRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    sms_code: str = Field(pattern=r'^\d{6}$')

class LoginRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    password: str = Field(min_length=8, max_length=32)
    captcha: Optional[str] = None  # 图形验证码，选填

class LogoutRequest(BaseModel):
    token: str

class ResetPasswordRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    old_password: str = Field(min_length=8, max_length=32)
    new_password: str = Field(min_length=8, max_length=32)

class ClearLoginErrorsRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')

class ForceResetPasswordRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')

class CheckSessionRequest(BaseModel):
    token: str

class RefreshTokenRequest(BaseModel):
    token: str

class UpdateNicknameRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=32)

class UpdateMobileRequest(BaseModel):
    new_mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    sms_code: str = Field(pattern=r'^\d{6}$')
    captcha: str

class UpdateAvatarRequest(BaseModel):
    avatar_url: str = Field(..., description="头像URL地址")

class UploadAvatarRequest(BaseModel):
    """上传头像请求模型"""
    file: UploadFile = Field(..., description="头像文件")

class SendEmailRequest(BaseModel):
    email: str = Field(pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    captcha: str
    scene: str = Field(..., description="验证码场景：register-注册, reset_password-重置密码, update_email-修改邮箱")

class RegisterByEmailRequest(BaseModel):
    email: str = Field(pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    email_code: str = Field(pattern=r'^\d{6}$')

class LoginByEmailRequest(BaseModel):
    email: str = Field(pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    password: str = Field(min_length=8, max_length=32)
    captcha: Optional[str] = None  # 图形验证码，选填

class ResetPasswordByEmailRequest(BaseModel):
    email: str = Field(pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    old_password: str = Field(min_length=8, max_length=32)
    new_password: str = Field(min_length=8, max_length=32)

class ForceResetPasswordByEmailRequest(BaseModel):
    email: str = Field(pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

class UpdateEmailRequest(BaseModel):
    new_email: str = Field(pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    email_code: str = Field(pattern=r'^\d{6}$')
    captcha: str

class SendResetPasswordEmailRequest(BaseModel):
    email: str = Field(..., description="邮箱地址")
    captcha: str = Field(..., description="图形验证码")

class ResetPasswordWithEmailRequest(BaseModel):
    email: str = Field(..., description="邮箱地址")
    email_code: str = Field(..., description="邮箱验证码")
    new_password: str = Field(..., min_length=6, max_length=20, description="新密码")

# 认证相关响应数据结构
class AuthUser(BaseModel):
    id: str
    mobile: Optional[str] = None
    email: Optional[str] = None
    nickname: str
    level: Optional[int] = None
    avatar: Optional[str] = None

class AuthToken(BaseModel):
    user: AuthUser
    token: str

# 统一响应类型
AuthSuccessResponse = SuccessResponse[AuthToken]
AuthUserSuccessResponse = SuccessResponse[AuthUser]
AuthSimpleSuccessResponse = SuccessResponse[Dict[str, Any]]

class UpdateUserLevelRequest(BaseModel):
    """更新用户等级请求模型"""
    user_id: str = Field(..., description="目标用户ID")
    new_level: int = Field(..., description="新的用户等级", ge=1, le=8)

class UserListResponse(BaseModel):
    """用户列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[AuthUser] = Field(..., description="用户列表") 