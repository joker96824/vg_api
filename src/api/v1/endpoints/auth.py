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

router = APIRouter()

class SendSMSRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    captcha: str
    scene: str = "register"

class RegisterRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    sms_code: str = Field(pattern=r'^\d{6}$')
    password: str = Field(min_length=8, max_length=32)
    nickname: Optional[str] = None

class LoginRequest(BaseModel):
    mobile: str = Field(pattern=r'^1[3-9]\d{9}$')
    password: str = Field(min_length=8, max_length=32)

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

@router.get("/captcha")
async def get_captcha(request: Request):
    """获取图形验证码"""
    captcha_service = CaptchaService()
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
        result = await auth_service.register(
            mobile=data.mobile,
            sms_code=data.sms_code,
            password=data.password,
            nickname=data.nickname,
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
    auth_service = AuthService(db)
    try:
        result = await auth_service.login(
            mobile=data.mobile,
            password=data.password,
            ip=request.client.host,
            device_fingerprint=request.headers.get("User-Agent", "")
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
    data: LogoutRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """用户登出"""
    auth_service = AuthService(db)
    try:
        await auth_service.logout(
            user_id=current_user["id"],
            token=data.token
        )
        
        return JSONResponse(content={
            "success": True,
            "message": "登出成功"
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset-password")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_session)
):
    """修改密码"""
    auth_service = AuthService(db)
    try:
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
    data: ClearLoginErrorsRequest,
    db: AsyncSession = Depends(get_session)
):
    """清除登录错误计数"""
    auth_service = AuthService(db)
    try:
        result = await auth_service.clear_login_errors(data.mobile)
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