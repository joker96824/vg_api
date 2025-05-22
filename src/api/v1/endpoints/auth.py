from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import Optional
from src.core.services.auth import AuthService
from src.core.services.captcha import CaptchaService
from src.core.services.sms import SMSService
from src.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

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
        raise HTTPException(status_code=400, detail="图形验证码错误")
    
    # 发送短信验证码
    sms_service = SMSService(db)
    result = await sms_service.send_code(data.mobile, data.scene)
    
    return JSONResponse(content={
        "success": True,
        "wait": result.get("wait", 60)
    })

@router.post("/register")
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_session)
):
    """用户注册"""
    auth_service = AuthService(db)
    result = await auth_service.register(
        mobile=data.mobile,
        sms_code=data.sms_code,
        password=data.password,
        nickname=data.nickname
    )
    
    return JSONResponse(content={
        "success": True,
        "user": result.get("user"),
        "token": result.get("token")
    }) 