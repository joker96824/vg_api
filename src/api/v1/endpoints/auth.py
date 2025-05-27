from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from typing import Optional
from src.core.services.auth import AuthService
from src.core.services.captcha import CaptchaService
from src.core.services.sms import SMSService
from src.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.auth import get_current_user, require_admin
from src.core.services.email import EmailService
from sqlalchemy import select
from src.core.models.user import User
from src.core.models.login_log import LoginLog
from src.core.utils.logger import APILogger
from src.core.schemas.auth import (
    SendSMSRequest, RegisterRequest, LoginRequest, LogoutRequest,
    ResetPasswordRequest, ClearLoginErrorsRequest, ForceResetPasswordRequest,
    CheckSessionRequest, RefreshTokenRequest, UpdateNicknameRequest,
    UpdateMobileRequest, UpdateAvatarRequest, SendEmailRequest,
    RegisterByEmailRequest, LoginByEmailRequest, ResetPasswordByEmailRequest,
    ForceResetPasswordByEmailRequest, UpdateEmailRequest,
    SendResetPasswordEmailRequest, ResetPasswordWithEmailRequest
)

router = APIRouter()

@router.get("/captcha")
async def get_captcha(request: Request):
    """获取图形验证码"""
    try:
        APILogger.log_request(
            "获取图形验证码",
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        captcha_service = CaptchaService()
        image = await captcha_service.generate(request)
        
        APILogger.log_response(
            "获取图形验证码",
            操作结果="成功"
        )
        
        return Response(content=image.getvalue(), media_type="image/png")
    except Exception as e:
        APILogger.log_error("获取图形验证码", e, IP=request.client.host)
        raise HTTPException(status_code=500, detail=f"获取验证码失败: {str(e)}")

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
    try:
        APILogger.log_request(
            "用户注册",
            手机号=data.mobile,
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        # 设置默认密码和昵称
        default_password = "SealJump"
        default_nickname = f"用户{data.mobile[-6:]}"
        
        auth_service = AuthService(db)
        result = await auth_service.register(
            mobile=data.mobile,
            sms_code=data.sms_code,
            password=default_password,
            nickname=default_nickname,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "用户注册",
            用户ID=result.get("user", {}).get("id"),
            操作结果="成功"
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
        APILogger.log_warning(
            "用户注册",
            "注册失败",
            手机号=data.mobile,
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "用户登录",
            手机号=data.mobile,
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        auth_service = AuthService(db)
        result = await auth_service.login(
            request=request,
            mobile=data.mobile,
            password=data.password,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "用户登录",
            用户ID=result.get("user", {}).get("id"),
            操作结果="成功"
        )
        
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
        APILogger.log_warning(
            "用户登录",
            "登录失败",
            手机号=data.mobile,
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "用户登出",
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        # 从请求头获取 token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            APILogger.log_warning(
                "用户登出",
                "未提供有效的认证token",
                IP=request.client.host
            )
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "code": "INVALID_TOKEN",
                    "message": "未提供有效的认证token"
                }
            )
        
        token = auth_header.split(" ")[1]
        auth_service = AuthService(db)
        await auth_service.logout(token)
        
        APILogger.log_response(
            "用户登出",
            操作结果="成功"
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "LOGOUT_SUCCESS",
                "message": "登出成功"
            }
        )
    except ValueError as e:
        APILogger.log_warning(
            "用户登出",
            "登出失败",
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "清除登录错误计数",
            用户ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        # 从token中获取用户标识（手机号或邮箱）
        account = current_user.get("mobile") or current_user.get("email")
        if not account:
            APILogger.log_warning(
                "清除登录错误计数",
                "无效的用户信息",
                用户ID=current_user["id"]
            )
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "code": "INVALID_USER",
                    "message": "无效的用户信息"
                }
            )
            
        result = await auth_service.clear_login_errors(account)
        
        APILogger.log_response(
            "清除登录错误计数",
            用户ID=current_user["id"],
            操作结果="成功"
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "CLEAR_ERRORS_SUCCESS",
                "message": "已清除登录错误计数"
            }
        )
    except ValueError as e:
        APILogger.log_warning(
            "清除登录错误计数",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "强制重置密码",
            管理员ID=current_user["id"],
            目标手机号=data.mobile,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.force_reset_password(
            mobile=data.mobile,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "强制重置密码",
            管理员ID=current_user["id"],
            目标手机号=data.mobile,
            操作结果="成功"
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
        APILogger.log_warning(
            "强制重置密码",
            "操作失败",
            管理员ID=current_user["id"],
            目标手机号=data.mobile,
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "检查会话状态",
            用户ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.check_session(
            user_id=current_user["id"],
            token=data.token
        )
        
        APILogger.log_response(
            "检查会话状态",
            用户ID=current_user["id"],
            会话状态=result.get("status")
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
        APILogger.log_warning(
            "检查会话状态",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "刷新令牌",
            用户ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.refresh_token(
            user_id=current_user["id"],
            old_token=data.token,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "刷新令牌",
            用户ID=current_user["id"],
            操作结果="成功"
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
        APILogger.log_warning(
            "刷新令牌",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
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
    current_user: dict = Depends(get_current_user)
):
    """修改用户昵称"""
    try:
        APILogger.log_request(
            "修改用户昵称",
            用户ID=current_user["id"],
            新昵称=data.nickname,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.update_nickname(
            user_id=current_user["id"],
            new_nickname=data.nickname,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "修改用户昵称",
            用户ID=current_user["id"],
            新昵称=data.nickname,
            操作结果="成功"
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
        APILogger.log_warning(
            "修改用户昵称",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
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
    current_user: dict = Depends(get_current_user)
):
    """修改手机号"""
    try:
        APILogger.log_request(
            "修改手机号",
            用户ID=current_user["id"],
            新手机号=data.new_mobile,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.update_mobile(
            request=request,
            user_id=current_user["id"],
            new_mobile=data.new_mobile,
            sms_code=data.sms_code,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "修改手机号",
            用户ID=current_user["id"],
            新手机号=data.new_mobile,
            操作结果="成功"
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
        APILogger.log_warning(
            "修改手机号",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "邮箱注册",
            邮箱=data.email,
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        # 设置默认密码和昵称
        default_password = "SealJump"
        default_nickname = f"用户{data.email.split('@')[0]}"
        
        auth_service = AuthService(db)
        result = await auth_service.register_by_email(
            email=data.email,
            email_code=data.email_code,
            password=default_password,
            nickname=default_nickname,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "邮箱注册",
            用户ID=result.get("user", {}).get("id"),
            操作结果="成功"
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
        APILogger.log_warning(
            "邮箱注册",
            "注册失败",
            邮箱=data.email,
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "邮箱登录",
            邮箱=data.email,
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        auth_service = AuthService(db)
        result = await auth_service.login_by_email(
            request=request,
            email=data.email,
            password=data.password,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "邮箱登录",
            用户ID=result.get("user", {}).get("id"),
            操作结果="成功"
        )
        
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
        APILogger.log_warning(
            "邮箱登录",
            "登录失败",
            邮箱=data.email,
            错误信息=str(e)
        )
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
    try:
        APILogger.log_request(
            "验证邮箱验证码并重置密码",
            邮箱=data.email,
            IP=request.client.host
        )
        
        # 验证邮箱验证码
        email_service = EmailService()
        verify_result = await email_service.verify_code(
            email=data.email,
            code=data.email_code,
            scene="reset_password"
        )
        
        if not verify_result.get("success", True):
            APILogger.log_warning(
                "验证邮箱验证码并重置密码",
                "验证码验证失败",
                邮箱=data.email
            )
            return JSONResponse(
                status_code=400,
                content=verify_result
            )
        
        # 重置密码
        auth_service = AuthService(db)
        # 查找用户
        stmt = select(User).where(User.email_hash == auth_service._hash_email(data.email))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            APILogger.log_warning(
                "验证邮箱验证码并重置密码",
                "用户不存在",
                邮箱=data.email
            )
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
        
        APILogger.log_response(
            "验证邮箱验证码并重置密码",
            用户ID=user.id,
            操作结果="成功"
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "code": "RESET_PASSWORD_SUCCESS",
                "message": "密码重置成功"
            }
        )
    except ValueError as e:
        APILogger.log_warning(
            "验证邮箱验证码并重置密码",
            "操作失败",
            邮箱=data.email,
            错误信息=str(e)
        )
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