"""认证相关的请求与响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import TOKEN_TYPE_BEARER


class RegisterRequest(BaseModel):
    """注册请求体。"""

    username: str = Field(..., min_length=2, max_length=100, description="用户名或昵称")
    email: str = Field(..., max_length=191, description="登录邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="明文密码")


class LoginRequest(BaseModel):
    """登录请求体。"""

    email: str = Field(..., max_length=191, description="登录邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="明文密码")


class UserProfile(BaseModel):
    """返回给前端的用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    username: str
    email: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuthPayload(BaseModel):
    """登录或注册成功后的数据主体。"""

    access_token: str
    token_type: str = TOKEN_TYPE_BEARER
    user: UserProfile


class AuthResponse(BaseModel):
    """登录或注册响应。"""

    message: str
    data: AuthPayload


class CurrentUserResponse(BaseModel):
    """当前用户信息响应。"""

    message: str
    data: UserProfile
