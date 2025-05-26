from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import Optional
from src.core.services.auth import AuthService
from src.core.services.captcha import CaptchaService
from src.core.services.sms import SMSService
from src.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.auth import get_current_user, require_admin
import logging
from src.core.services.email import EmailService
from sqlalchemy import select
from src.core.models.user import User
from src.core.models.login_log import LoginLog

router = APIRouter()

logger = logging.getLogger(__name__)

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

@router.get("/captcha")
async def get_captcha(request: Request):
    """获取图形验证码"""
    captcha_service = CaptchaService()
    print(request.session)
    image = await captcha_service.generate(request)
    return Response(content=image.getvalue(), media_type="image/png")

@router.post("/send-sms")
async def send_sms(
    request: Request,
    data: SendSMSRequest,
    db: AsyncSession = Depends(get_session)
):
    """发送短信验证码"""
    # 验证图形验证码
    print(request.session)
    captcha_service = CaptchaService()
    if not await captcha_service.verify(request, data.captcha):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "CAPTCHA_ERROR",
                "message": "图形验证码错误"
            }
        )
    
    # 发送短信验证码
    sms_service = SMSService(db)
    result = await sms_service.send_code(
        mobile=data.mobile,
        scene=data.scene,
        ip=request.client.host
    )
    
    # 如果发送失败（超出限制），返回400状态码
    if not result.get("success", True):
        return JSONResponse(
            status_code=400,
            content=result
        )
    
    # 发送成功，返回200状态码
    return JSONResponse(
        status_code=200,
        content=result
    )

@router.post("/register")
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_session)
):
    """用户注册"""
    auth_service = AuthService(db)
    try:
        # 设置默认密码和昵称
        default_password = "SealJump"
        default_nickname = f"用户{data.mobile[-6:]}"
        
        result = await auth_service.register(
            mobile=data.mobile,
            sms_code=data.sms_code,
            password=default_password,
            nickname=default_nickname,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "REGISTER_SUCCESS",
                "message": "注册成功",
                "data": {
                    "user": result.get("user"),
                    "token": result.get("token")
                }
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "REGISTER_ERROR",
                "message": str(e)
            }
        )

@router.post("/login")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_session)
):
    """用户登录"""
    logger.info("="*50)
    logger.info("登录请求 - 参数:")
    logger.info(f"mobile: {data.mobile}")
    logger.info(f"password: {'*' * len(data.password)}")
    logger.info(f"captcha: {data.captcha}")
    logger.info("请求体原始内容:")
    request_body = await request.json()
    logger.info(f"request body: {request_body}")
    
    auth_service = AuthService(db)
    try:
        result = await auth_service.login(
            request=request,
            mobile=data.mobile,
            password=data.password,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        logger.info("登录成功:")
        logger.info(f"user_id: {result.get('user', {}).get('id')}")
        logger.info(f"token: {result.get('token')[:20]}...")
        logger.info("="*50)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "LOGIN_SUCCESS",
                "message": "登录成功",
                "data": {
                    "user": result.get("user"),
                    "token": result.get("token")
                }
            }
        )
    except ValueError as e:
        logger.error(f"登录失败: {str(e)}")
        logger.error("="*50)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "LOGIN_ERROR",
                "message": str(e)
            }
        )

@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_session)
):
    """用户登出"""
    logger.info("="*50)
    logger.info("登出请求")
    
    # 从请求头获取 token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.error("未提供有效的认证token")
        logger.error("="*50)
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "code": "INVALID_TOKEN",
                "message": "未提供有效的认证token"
            }
        )
    
    token = auth_header.split(" ")[1]
    logger.info(f"token: {token[:20]}...")
    
    auth_service = AuthService(db)
    try:
        await auth_service.logout(token)
        logger.info("登出成功")
        logger.info("="*50)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "LOGOUT_SUCCESS",
                "message": "登出成功"
            }
        )
    except ValueError as e:
        logger.error(f"登出失败: {str(e)}")
        logger.error("="*50)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "LOGOUT_ERROR",
                "message": str(e)
            }
        )

@router.post("/reset-password")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)  # 添加JWT验证
):
    """修改密码"""
    auth_service = AuthService(db)
    try:
        # 验证当前用户是否是手机号对应的用户
        if current_user["mobile"] != data.mobile:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "code": "PERMISSION_DENIED",
                    "message": "无权修改其他用户的密码"
                }
            )
            
        result = await auth_service.reset_password(
            mobile=data.mobile,
            old_password=data.old_password,
            new_password=data.new_password,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "PASSWORD_RESET_SUCCESS",
                "message": "密码修改成功"
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "PASSWORD_RESET_ERROR",
                "message": str(e)
            }
        )

@router.post("/clear-login-errors")
async def clear_login_errors(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """清除登录错误计数"""
    auth_service = AuthService(db)
    try:
        # 从token中获取用户标识（手机号或邮箱）
        account = current_user.get("mobile") or current_user.get("email")
        if not account:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "code": "INVALID_USER",
                    "message": "无效的用户信息"
                }
            )
            
        result = await auth_service.clear_login_errors(account)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "CLEAR_ERRORS_SUCCESS",
                "message": "已清除登录错误计数"
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "CLEAR_ERRORS_ERROR",
                "message": str(e)
            }
        )

@router.post("/force-reset-password")
async def force_reset_password(
    request: Request,
    data: ForceResetPasswordRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin)
):
    """强制重置密码为默认密码"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.force_reset_password(
            mobile=data.mobile,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "PASSWORD_RESET_SUCCESS",
                "message": "密码已重置为默认密码"
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "PASSWORD_RESET_ERROR",
                "message": str(e)
            }
        )

@router.post("/check-session")
async def check_session(
    request: Request,
    data: CheckSessionRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """检查会话状态"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.check_session(
            user_id=current_user["id"],
            token=data.token
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "SESSION_CHECK_SUCCESS",
                "data": result
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "SESSION_CHECK_ERROR",
                "message": str(e)
            }
        )

@router.post("/refresh-token")
async def refresh_token(
    request: Request,
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """刷新令牌"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.refresh_token(
            user_id=current_user["id"],
            old_token=data.token,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "TOKEN_REFRESH_SUCCESS",
                "data": result
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "TOKEN_REFRESH_ERROR",
                "message": str(e)
            }
        )

@router.post("/update-nickname")
async def update_nickname(
    request: Request,
    data: UpdateNicknameRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)  # 从JWT令牌中获取当前用户信息
):
    """修改用户昵称"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.update_nickname(
            user_id=current_user["id"],
            new_nickname=data.nickname,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")  # 获取设备信息
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "NICKNAME_UPDATE_SUCCESS",
                "message": "昵称修改成功",
                "data": result["data"]
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "NICKNAME_UPDATE_ERROR",
                "message": str(e)
            }
        )

@router.post("/update-mobile")
async def update_mobile(
    request: Request,
    data: UpdateMobileRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)  # 从JWT令牌中获取当前用户信息
):
    """修改手机号"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.update_mobile(
            request=request,
            user_id=current_user["id"],
            new_mobile=data.new_mobile,
            sms_code=data.sms_code,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")  # 获取设备信息
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "MOBILE_UPDATE_SUCCESS",
                "message": "手机号修改成功",
                "data": result["data"]
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "MOBILE_UPDATE_ERROR",
                "message": str(e)
            }
        )

@router.post("/update-avatar")
async def update_avatar(
    request: Request,
    data: UpdateAvatarRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)  # 从JWT令牌中获取当前用户信息
):
    """修改用户头像"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.update_avatar(
            user_id=current_user["id"],
            avatar_url=data.avatar_url,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")  # 获取设备信息
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "AVATAR_UPDATE_SUCCESS",
                "message": "头像修改成功",
                "data": result["data"]
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "AVATAR_UPDATE_ERROR",
                "message": str(e)
            }
        )

@router.post("/send-email")
async def send_email(
    request: Request,
    data: SendEmailRequest,
    db: AsyncSession = Depends(get_session)
):
    """发送邮箱验证码"""
    # 验证图形验证码
    captcha_service = CaptchaService()
    if not await captcha_service.verify(request, data.captcha):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "CAPTCHA_ERROR",
                "message": "图形验证码错误"
            }
        )
    
    # 验证场景是否有效
    valid_scenes = ["register", "reset_password", "update_email"]
    if data.scene not in valid_scenes:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "INVALID_SCENE",
                "message": "无效的验证码场景"
            }
        )
    
    # 如果是重置密码场景，验证邮箱是否存在
    if data.scene == "reset_password":
        auth_service = AuthService(db)
        if not await auth_service.check_email_exists(data.email):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "code": "EMAIL_NOT_EXISTS",
                    "message": "该邮箱未注册"
                }
            )
    
    # 发送邮箱验证码
    email_service = EmailService()
    result = await email_service.send_code(
        email=data.email,
        scene=data.scene,
        ip=request.client.host
    )
    
    # 如果发送失败（超出限制），返回400状态码
    if not result.get("success", True):
        return JSONResponse(
            status_code=400,
            content=result
        )
    
    # 发送成功，返回200状态码
    return JSONResponse(
        status_code=200,
        content=result
    )

@router.post("/register-by-email")
async def register_by_email(
    request: Request,
    data: RegisterByEmailRequest,
    db: AsyncSession = Depends(get_session)
):
    """邮箱注册"""
    auth_service = AuthService(db)
    try:
        # 设置默认密码和昵称
        default_password = "SealJump"
        default_nickname = f"用户{data.email.split('@')[0]}"
        
        result = await auth_service.register_by_email(
            email=data.email,
            email_code=data.email_code,
            password=default_password,
            nickname=default_nickname,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "REGISTER_SUCCESS",
                "message": "注册成功",
                "data": {
                    "user": result.get("user"),
                    "token": result.get("token")
                }
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "REGISTER_ERROR",
                "message": str(e)
            }
        )

@router.post("/login-by-email")
async def login_by_email(
    request: Request,
    data: LoginByEmailRequest,
    db: AsyncSession = Depends(get_session)
):
    """邮箱登录"""
    logger.info("="*50)
    logger.info("邮箱登录请求 - 参数:")
    logger.info(f"email: {data.email}")
    logger.info(f"password: {'*' * len(data.password)}")
    logger.info(f"captcha: {data.captcha}")
    logger.info("请求体原始内容:")
    request_body = await request.json()
    logger.info(f"request body: {request_body}")
    
    auth_service = AuthService(db)
    try:
        result = await auth_service.login_by_email(
            request=request,
            email=data.email,
            password=data.password,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        logger.info("登录成功:")
        logger.info(f"user_id: {result.get('user', {}).get('id')}")
        logger.info(f"token: {result.get('token')[:20]}...")
        logger.info("="*50)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "LOGIN_SUCCESS",
                "message": "登录成功",
                "data": {
                    "user": result.get("user"),
                    "token": result.get("token")
                }
            }
        )
    except ValueError as e:
        logger.error(f"登录失败: {str(e)}")
        logger.error("="*50)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "LOGIN_ERROR",
                "message": str(e)
            }
        )

@router.post("/reset-password-by-email")
async def reset_password_by_email(
    request: Request,
    data: ResetPasswordByEmailRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """通过邮箱修改密码"""
    auth_service = AuthService(db)
    try:
        # 验证当前用户是否是邮箱对应的用户
        if current_user["email"] != data.email:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "code": "PERMISSION_DENIED",
                    "message": "无权修改其他用户的密码"
                }
            )
            
        result = await auth_service.reset_password_by_email(
            email=data.email,
            old_password=data.old_password,
            new_password=data.new_password,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "PASSWORD_RESET_SUCCESS",
                "message": "密码修改成功"
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "PASSWORD_RESET_ERROR",
                "message": str(e)
            }
        )

@router.post("/force-reset-password/verify")
async def verify_and_reset_password(
    request: Request,
    data: ResetPasswordWithEmailRequest,
    db: AsyncSession = Depends(get_session)
):
    """验证邮箱验证码并重置密码"""
    # 验证邮箱验证码
    email_service = EmailService()
    verify_result = await email_service.verify_code(
        email=data.email,
        code=data.email_code,
        scene="reset_password"
    )
    
    if not verify_result.get("success", True):
        return JSONResponse(
            status_code=400,
            content=verify_result
        )
    
    # 重置密码
    auth_service = AuthService(db)
    try:
        # 查找用户
        stmt = select(User).where(User.email_hash == auth_service._hash_email(data.email))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "code": "USER_NOT_EXISTS",
                    "message": "用户不存在"
                }
            )
            
        # 直接更新密码
        user.password_hash = auth_service._hash_password(data.new_password)
        
        # 清除密码错误计数
        auth_service._clear_password_error(data.email)
        
        # 记录密码重置日志
        login_log = LoginLog(
            user_id=user.id,
            login_type=5,  # 密码重置
            ip=request.client.host,
            device_info={"user_agent": request.headers.get("User-Agent", "")},
            status=1,  # 成功
            remark="通过邮箱验证码重置密码"
        )
        db.add(login_log)
        
        await db.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "RESET_PASSWORD_SUCCESS",
                "message": "密码重置成功"
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "RESET_PASSWORD_ERROR",
                "message": str(e)
            }
        )

@router.post("/update-email")
async def update_email(
    request: Request,
    data: UpdateEmailRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """修改邮箱"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.update_email(
            request=request,
            user_id=current_user["id"],
            new_email=data.new_email,
            email_code=data.email_code,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "EMAIL_UPDATE_SUCCESS",
                "message": "邮箱修改成功",
                "data": result["data"]
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "EMAIL_UPDATE_ERROR",
                "message": str(e)
            }
        ) 