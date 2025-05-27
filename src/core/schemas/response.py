from typing import TypeVar, Generic
from pydantic import BaseModel, Field

class ResponseCode:
    """响应码定义"""
    SUCCESS = "SUCCESS"
    CREATE_SUCCESS = "CREATE_SUCCESS"
    UPDATE_SUCCESS = "UPDATE_SUCCESS"
    DELETE_SUCCESS = "DELETE_SUCCESS"
    INVALID_PARAMS = "INVALID_PARAMS"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    SERVER_ERROR = "SERVER_ERROR"

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