from typing import TypeVar, Generic
from pydantic import BaseModel, Field
from enum import Enum

class ResponseCode(str, Enum):
    """响应状态码"""
    SUCCESS = "SUCCESS"  # 成功
    CREATE_SUCCESS = "CREATE_SUCCESS"  # 创建成功
    UPDATE_SUCCESS = "UPDATE_SUCCESS"  # 更新成功
    DELETE_SUCCESS = "DELETE_SUCCESS"  # 删除成功
    NOT_FOUND = "NOT_FOUND"  # 资源不存在
    FORBIDDEN = "FORBIDDEN"  # 无权访问
    UNAUTHORIZED = "UNAUTHORIZED"  # 未认证
    SERVER_ERROR = "SERVER_ERROR"  # 服务器错误
    VALIDATION_ERROR = "VALIDATION_ERROR"  # 验证错误
    PARAM_ERROR = "PARAM_ERROR"  # 参数错误
    CAPTCHA_ERROR = "CAPTCHA_ERROR"  # 验证码错误
    SMS_ERROR = "SMS_ERROR"  # 短信错误
    EMAIL_ERROR = "EMAIL_ERROR"  # 邮件错误
    LOGIN_ERROR = "LOGIN_ERROR"  # 登录错误
    REGISTER_ERROR = "REGISTER_ERROR"  # 注册错误
    RESET_PASSWORD_ERROR = "RESET_PASSWORD_ERROR"  # 重置密码错误
    TOKEN_ERROR = "TOKEN_ERROR"  # Token错误
    SESSION_ERROR = "SESSION_ERROR"  # 会话错误
    USER_NOT_FOUND = "USER_NOT_FOUND"  # 用户不存在
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"  # 用户已存在
    PASSWORD_ERROR = "PASSWORD_ERROR"  # 密码错误
    MOBILE_ERROR = "MOBILE_ERROR"  # 手机号错误
    EMAIL_NOT_FOUND = "EMAIL_NOT_FOUND"  # 邮箱不存在
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"  # 邮箱已存在
    MOBILE_NOT_FOUND = "MOBILE_NOT_FOUND"  # 手机号不存在
    MOBILE_ALREADY_EXISTS = "MOBILE_ALREADY_EXISTS"  # 手机号已存在
    LOGIN_ERROR_COUNT_EXCEEDED = "LOGIN_ERROR_COUNT_EXCEEDED"  # 登录错误次数超限
    LOGIN_ERROR_TIME_NOT_EXPIRED = "LOGIN_ERROR_TIME_NOT_EXPIRED"  # 登录错误时间未到
    LOGIN_ERROR_TIME_EXPIRED = "LOGIN_ERROR_TIME_EXPIRED"  # 登录错误时间已到
    LOGIN_ERROR_COUNT_RESET = "LOGIN_ERROR_COUNT_RESET"  # 登录错误次数重置
    LOGIN_ERROR_COUNT_NOT_RESET = "LOGIN_ERROR_COUNT_NOT_RESET"  # 登录错误次数未重置
    LOGIN_ERROR_COUNT_RESET_TIME_NOT_EXPIRED = "LOGIN_ERROR_COUNT_RESET_TIME_NOT_EXPIRED"  # 登录错误次数重置时间未到
    LOGIN_ERROR_COUNT_RESET_TIME_EXPIRED = "LOGIN_ERROR_COUNT_RESET_TIME_EXPIRED"  # 登录错误次数重置时间已到
    LOGIN_ERROR_COUNT_RESET_TIME_NOT_EXPIRED_AND_COUNT_NOT_RESET = "LOGIN_ERROR_COUNT_RESET_TIME_NOT_EXPIRED_AND_COUNT_NOT_RESET"  # 登录错误次数重置时间未到且次数未重置
    LOGIN_ERROR_COUNT_RESET_TIME_EXPIRED_AND_COUNT_NOT_RESET = "LOGIN_ERROR_COUNT_RESET_TIME_EXPIRED_AND_COUNT_NOT_RESET"  # 登录错误次数重置时间已到且次数未重置
    LOGIN_ERROR_COUNT_RESET_TIME_NOT_EXPIRED_AND_COUNT_RESET = "LOGIN_ERROR_COUNT_RESET_TIME_NOT_EXPIRED_AND_COUNT_RESET"  # 登录错误次数重置时间未到且次数已重置
    LOGIN_ERROR_COUNT_RESET_TIME_EXPIRED_AND_COUNT_RESET = "LOGIN_ERROR_COUNT_RESET_TIME_EXPIRED_AND_COUNT_RESET"  # 登录错误次数重置时间已到且次数已重置

# 通用响应模型
T = TypeVar('T')

class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(..., description="是否成功")
    code: str = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")

class SuccessResponse(BaseResponse, Generic[T]):
    """成功响应模型"""
    data: T = Field(..., description="响应数据")

    @classmethod
    def create(cls, code: str, message: str, data: T) -> "SuccessResponse[T]":
        return cls(
            success=True,
            code=code,
            message=message,
            data=data
        )

class ErrorResponse(BaseResponse):
    """错误响应模型"""
    @classmethod
    def create(cls, code: str, message: str) -> "ErrorResponse":
        return cls(
            success=False,
            code=code,
            message=message
        ) 