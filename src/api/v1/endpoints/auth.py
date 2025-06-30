from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import JSONResponse, Response
from typing import Optional, List
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
    SendResetPasswordEmailRequest, ResetPasswordWithEmailRequest,
    AuthSuccessResponse, AuthUserSuccessResponse, AuthSimpleSuccessResponse,
    AuthUser, AuthToken, UpdateUserLevelRequest, UserListResponse,
    UpdateFileStatusRequest, FileListResponse
)
from src.core.schemas.response import ResponseCode, ErrorResponse, SuccessResponse
from uuid import UUID
from src.core.deps import get_db

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

@router.post("/send-sms", response_model=AuthSimpleSuccessResponse)
async def send_sms(
    request: Request,
    data: SendSMSRequest,
    db: AsyncSession = Depends(get_db)
):
    """发送短信验证码"""
    # 验证图形验证码
    captcha_service = CaptchaService()
    if not await captcha_service.verify(request, data.captcha):
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message="图形验证码错误"
        )
    
    # 发送短信验证码
    sms_service = SMSService(db)
    result = await sms_service.send_code(
        mobile=data.mobile,
        scene=data.scene,
        ip=request.client.host
    )
    
    # 如果发送失败（超出限制），返回错误响应
    if not result.get("success", True):
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=result.get("message", "发送失败")
        )
    
    # 发送成功，返回成功响应
    return AuthSimpleSuccessResponse.create(
        code=ResponseCode.SUCCESS,
        message="发送成功",
        data=result
    )

@router.post("/register", response_model=AuthSuccessResponse)
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
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
        
        return AuthSuccessResponse.create(
            code=ResponseCode.CREATE_SUCCESS,
            message="注册成功",
            data=AuthToken(
                user=AuthUser(**result["user"]),
                token=result["token"]
            )
        )
    except ValueError as e:
        APILogger.log_warning(
            "用户注册",
            "注册失败",
            手机号=data.mobile,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/login", response_model=AuthSuccessResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db)
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
        
        return AuthSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="登录成功",
            data=AuthToken(
                user=AuthUser(**result["user"]),
                token=result["token"]
            )
        )
    except ValueError as e:
        APILogger.log_warning(
            "用户登录",
            "登录失败",
            手机号=data.mobile,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/logout")
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """用户登出"""
    try:
        APILogger.log_request(
            "用户登出",
            用户ID=current_user["id"],
            IP=request.client.host,
            设备信息=request.headers.get("User-Agent", "")
        )
        
        auth_service = AuthService(db)
        await auth_service.logout(current_user["id"])
        
        APILogger.log_response(
            "用户登出",
            用户ID=current_user["id"],
            操作结果="成功"
        )
        
        return {"message": "登出成功"}
    except Exception as e:
        APILogger.log_error(
            "用户登出",
            e,
            用户ID=current_user["id"]
        )
        return {"message": "登出失败"}

@router.post("/reset-password", response_model=AuthSimpleSuccessResponse)
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """修改密码"""
    auth_service = AuthService(db)
    try:
        # 验证当前用户是否是手机号对应的用户
        if current_user["mobile"] != data.mobile:
            return ErrorResponse.create(
                code=ResponseCode.PERMISSION_DENIED,
                message="无权修改其他用户的密码"
            )
            
        result = await auth_service.reset_password(
            mobile=data.mobile,
            old_password=data.old_password,
            new_password=data.new_password,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="密码修改成功",
            data={}
        )
    except ValueError as e:
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/clear-login-errors", response_model=AuthSimpleSuccessResponse)
async def clear_login_errors(
    request: Request,
    db: AsyncSession = Depends(get_db),
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
            return ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message="无效的用户信息"
            )
            
        result = await auth_service.clear_login_errors(account)
        
        APILogger.log_response(
            "清除登录错误计数",
            用户ID=current_user["id"],
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="已清除登录错误计数",
            data={}
        )
    except ValueError as e:
        APILogger.log_warning(
            "清除登录错误计数",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/force-reset-password", response_model=AuthSimpleSuccessResponse)
async def force_reset_password(
    request: Request,
    data: ForceResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
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
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="密码已重置为默认密码",
            data={}
        )
    except ValueError as e:
        APILogger.log_warning(
            "强制重置密码",
            "操作失败",
            管理员ID=current_user["id"],
            目标手机号=data.mobile,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/check-session", response_model=AuthSimpleSuccessResponse)
async def check_session(
    request: Request,
    data: CheckSessionRequest,
    db: AsyncSession = Depends(get_db),
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
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="会话检查成功",
            data=result
        )
    except ValueError as e:
        APILogger.log_warning(
            "检查会话状态",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/refresh-token", response_model=AuthSuccessResponse)
async def refresh_token(
    request: Request,
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
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
        
        return AuthSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="令牌刷新成功",
            data=AuthToken(
                user=AuthUser(**result["user"]),
                token=result["token"]
            )
        )
    except ValueError as e:
        APILogger.log_warning(
            "刷新令牌",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/update-nickname", response_model=AuthSimpleSuccessResponse)
async def update_nickname(
    request: Request,
    data: UpdateNicknameRequest,
    db: AsyncSession = Depends(get_db),
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
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="昵称修改成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "修改用户昵称",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/update-mobile", response_model=AuthSimpleSuccessResponse)
async def update_mobile(
    request: Request,
    data: UpdateMobileRequest,
    db: AsyncSession = Depends(get_db),
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
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="手机号修改成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "修改手机号",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/update-avatar", response_model=AuthSimpleSuccessResponse)
async def update_avatar(
    request: Request,
    data: UpdateAvatarRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """修改用户头像"""
    try:
        APILogger.log_request(
            "修改用户头像",
            用户ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.update_avatar(
            user_id=current_user["id"],
            avatar_url=data.avatar_url,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "修改用户头像",
            用户ID=current_user["id"],
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="头像修改成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "修改用户头像",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/upload-avatar", response_model=AuthSimpleSuccessResponse)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """上传用户头像"""
    try:
        APILogger.log_request(
            "上传用户头像",
            用户ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.upload_avatar(
            user_id=current_user["id"],
            file=file,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "上传用户头像",
            用户ID=current_user["id"],
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="头像上传成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "上传用户头像",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )

@router.post("/send-email", response_model=AuthSimpleSuccessResponse)
async def send_email(
    request: Request,
    data: SendEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """发送邮箱验证码"""
    try:
        APILogger.log_request(
            "发送邮箱验证码",
            邮箱=data.email,
            IP=request.client.host
        )
        
        # 验证图形验证码
        captcha_service = CaptchaService()
        if not await captcha_service.verify(request, data.captcha):
            return ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message="图形验证码错误"
            )
        
        # 验证场景是否有效
        valid_scenes = ["register", "reset_password", "update_email"]
        if data.scene not in valid_scenes:
            return ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message="无效的验证码场景"
            )
        
        # 如果是重置密码场景，验证邮箱是否存在
        if data.scene == "reset_password":
            auth_service = AuthService(db)
            if not await auth_service.check_email_exists(data.email):
                return ErrorResponse.create(
                    code=ResponseCode.PARAM_ERROR,
                    message="该邮箱未注册"
                )
        
        # 发送邮箱验证码
        email_service = EmailService()
        result = await email_service.send_code(
            email=data.email,
            scene=data.scene,
            ip=request.client.host
        )
        
        # 如果发送失败（超出限制），返回错误响应
        if not result.get("success", True):
            return ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=result.get("message", "发送失败")
            )
        
        APILogger.log_response(
            "发送邮箱验证码",
            邮箱=data.email,
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="发送成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("发送邮箱验证码", e, IP=request.client.host)
        return ErrorResponse.create(
            code=ResponseCode.SERVER_ERROR,
            message=str(e)
        )

@router.post("/register-by-email", response_model=AuthSuccessResponse)
async def register_by_email(
    request: Request,
    data: RegisterByEmailRequest,
    db: AsyncSession = Depends(get_db)
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
        
        return AuthSuccessResponse.create(
            code=ResponseCode.CREATE_SUCCESS,
            message="注册成功",
            data=AuthToken(
                user=AuthUser(**result["user"]),
                token=result["token"]
            )
        )
    except ValueError as e:
        APILogger.log_warning(
            "邮箱注册",
            "注册失败",
            邮箱=data.email,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/login-by-email", response_model=AuthSuccessResponse)
async def login_by_email(
    request: Request,
    data: LoginByEmailRequest,
    db: AsyncSession = Depends(get_db)
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
        
        return AuthSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="登录成功",
            data=AuthToken(
                user=AuthUser(**result["user"]),
                token=result["token"]
            )
        )
    except ValueError as e:
        APILogger.log_warning(
            "邮箱登录",
            "登录失败",
            邮箱=data.email,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/reset-password-by-email", response_model=AuthSimpleSuccessResponse)
async def reset_password_by_email(
    request: Request,
    data: ResetPasswordByEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """通过邮箱修改密码"""
    try:
        APILogger.log_request(
            "通过邮箱修改密码",
            用户ID=current_user["id"],
            邮箱=data.email,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        # 验证当前用户是否是邮箱对应的用户
        if current_user["email"] != data.email:
            return ErrorResponse.create(
                code=ResponseCode.PERMISSION_DENIED,
                message="无权修改其他用户的密码"
            )
            
        result = await auth_service.reset_password_by_email(
            email=data.email,
            old_password=data.old_password,
            new_password=data.new_password,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "通过邮箱修改密码",
            用户ID=current_user["id"],
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="密码修改成功",
            data={}
        )
    except ValueError as e:
        APILogger.log_warning(
            "通过邮箱修改密码",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/force-reset-password/verify", response_model=AuthSimpleSuccessResponse)
async def verify_and_reset_password(
    request: Request,
    data: ResetPasswordWithEmailRequest,
    db: AsyncSession = Depends(get_db)
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
            return ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=verify_result.get("message", "验证码验证失败")
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
            return ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message="用户不存在"
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
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="密码重置成功",
            data={}
        )
    except ValueError as e:
        APILogger.log_warning(
            "验证邮箱验证码并重置密码",
            "操作失败",
            邮箱=data.email,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.post("/update-email", response_model=AuthSimpleSuccessResponse)
async def update_email(
    request: Request,
    data: UpdateEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """修改邮箱"""
    try:
        APILogger.log_request(
            "修改邮箱",
            用户ID=current_user["id"],
            新邮箱=data.new_email,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.update_email(
            request=request,
            user_id=current_user["id"],
            new_email=data.new_email,
            email_code=data.email_code,
            captcha=data.captcha,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "修改邮箱",
            用户ID=current_user["id"],
            新邮箱=data.new_email,
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="邮箱修改成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "修改邮箱",
            "操作失败",
            用户ID=current_user["id"],
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.get("/users", response_model=SuccessResponse[UserListResponse])
async def get_all_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取所有用户信息（需要level=9权限）"""
    try:
        # 检查权限
        if current_user.get("level", 1) != 9:
            APILogger.log_warning(
                "获取所有用户",
                "权限不足",
                用户ID=current_user["id"],
                当前等级=current_user.get("level", 1)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="需要最高管理员权限"
                ).dict()
            )

        APILogger.log_request(
            "获取所有用户",
            用户ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.get_all_users()
        
        APILogger.log_response(
            "获取所有用户",
            用户ID=current_user["id"],
            总记录数=result["total"]
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取用户列表成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("获取所有用户", e, 用户ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取用户列表失败: {str(e)}"
            ).dict()
        )

@router.put("/users/level", response_model=AuthSimpleSuccessResponse)
async def update_user_level(
    request: Request,
    data: UpdateUserLevelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """更新用户等级（需要level=9权限）"""
    try:
        # 检查权限
        if current_user.get("level", 1) != 9:
            APILogger.log_warning(
                "更新用户等级",
                "权限不足",
                用户ID=current_user["id"],
                当前等级=current_user.get("level", 1)
            )
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse.create(
                    code=ResponseCode.FORBIDDEN,
                    message="需要最高管理员权限"
                ).dict()
            )

        APILogger.log_request(
            "更新用户等级",
            操作者ID=current_user["id"],
            目标用户ID=data.user_id,
            新等级=data.new_level,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.update_user_level(
            target_user_id=data.user_id,
            new_level=data.new_level,
            operator_id=current_user["id"],
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "更新用户等级",
            操作者ID=current_user["id"],
            目标用户ID=data.user_id,
            新等级=data.new_level,
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="用户等级修改成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "更新用户等级",
            "操作失败",
            操作者ID=current_user["id"],
            目标用户ID=data.user_id,
            错误信息=str(e)
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.create(
                code=ResponseCode.PARAM_ERROR,
                message=str(e)
            ).dict()
        )
    except Exception as e:
        APILogger.log_error("更新用户等级", e, 操作者ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"更新用户等级失败: {str(e)}"
            ).dict()
        )

@router.get("/search", response_model=List[AuthUser])
async def search_users(
    keyword: str = Query(..., description="搜索关键词"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """搜索用户"""
    service = AuthService(db)
    users = await service.search_users(keyword, current_user["id"])
    return users

@router.put("/files/status", response_model=AuthSimpleSuccessResponse)
async def update_file_status(
    request: Request,
    data: UpdateFileStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """更新文件状态（需要level=5权限）"""
    try:
        APILogger.log_request(
            "更新文件状态",
            操作者ID=current_user["id"],
            文件名=data.filename,
            新状态=data.new_status,
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.update_file_status(
            filename=data.filename,
            new_status=data.new_status,
            operator_id=current_user["id"],
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "更新文件状态",
            操作者ID=current_user["id"],
            文件名=data.filename,
            新状态=data.new_status,
            操作结果="成功"
        )
        
        return AuthSimpleSuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="文件状态更新成功",
            data=result["data"]
        )
    except ValueError as e:
        APILogger.log_warning(
            "更新文件状态",
            "操作失败",
            操作者ID=current_user["id"],
            文件名=data.filename,
            错误信息=str(e)
        )
        return ErrorResponse.create(
            code=ResponseCode.PARAM_ERROR,
            message=str(e)
        )

@router.get("/files/unaudited", response_model=SuccessResponse[FileListResponse])
async def get_unaudited_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """获取所有未审核的文件（需要level=5权限）"""
    try:
        APILogger.log_request(
            "获取未审核文件列表",
            操作者ID=current_user["id"],
            IP=request.client.host
        )
        
        auth_service = AuthService(db)
        result = await auth_service.get_unaudited_files(
            operator_id=current_user["id"],
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
        )
        
        APILogger.log_response(
            "获取未审核文件列表",
            操作者ID=current_user["id"],
            文件数量=result["total"]
        )
        
        return SuccessResponse.create(
            code=ResponseCode.SUCCESS,
            message="获取未审核文件列表成功",
            data=result
        )
    except Exception as e:
        APILogger.log_error("获取未审核文件列表", e, 操作者ID=current_user["id"])
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.create(
                code=ResponseCode.SERVER_ERROR,
                message=f"获取未审核文件列表失败: {str(e)}"
            ).dict()
        )

@router.get("/me")
async def get_current_user(
    db: AsyncSession = Depends(get_db)
):
    # This method is not provided in the original file or the code block
    # It's assumed to exist as it's called in the code block
    # Implement the logic to return the current user
    pass 