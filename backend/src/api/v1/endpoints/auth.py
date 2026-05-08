"""认证接口实现。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.auth import (
    AuthPayload,
    AuthResponse,
    ChangePasswordRequest,
    CurrentUserResponse,
    EmailCodeLoginRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    SendEmailCodeRequest,
    UpdateUserProfileRequest,
    UserProfile,
)
from src.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/email-code/send",
    response_model=MessageResponse,
    summary="发送邮箱验证码",
)
async def send_email_code(
    payload: SendEmailCodeRequest,
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """发送注册或登录使用的邮箱验证码。"""

    AuthService(db).send_email_code(
        email=payload.email,
        purpose=payload.purpose,
    )
    return MessageResponse(message="验证码已发送，请查收邮箱。")


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
    summary="注册账号",
)
async def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """注册用户并返回登录令牌。"""

    user, access_token = AuthService(db).register_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        email_code=payload.email_code,
    )
    return AuthResponse(
        message="注册成功。",
        data=AuthPayload(
            access_token=access_token,
            user=UserProfile.model_validate(user),
        ),
    )


@router.post("/login", response_model=AuthResponse, summary="密码登录")
async def login(
    payload: LoginRequest,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """密码登录并返回访问令牌。"""

    user, access_token = AuthService(db).login_user(
        email=payload.email,
        password=payload.password,
    )
    return AuthResponse(
        message="登录成功。",
        data=AuthPayload(
            access_token=access_token,
            user=UserProfile.model_validate(user),
        ),
    )


@router.post("/email-code/login", response_model=AuthResponse, summary="邮箱验证码登录")
async def login_with_email_code(
    payload: EmailCodeLoginRequest,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """邮箱验证码登录并返回访问令牌。"""

    user, access_token = AuthService(db).login_user_with_email_code(
        email=payload.email,
        email_code=payload.email_code,
    )
    return AuthResponse(
        message="登录成功。",
        data=AuthPayload(
            access_token=access_token,
            user=UserProfile.model_validate(user),
        ),
    )


@router.get("/me", response_model=CurrentUserResponse, summary="获取当前用户")
async def get_me(current_user=Depends(get_current_user)) -> CurrentUserResponse:
    """返回当前登录用户信息。"""

    return CurrentUserResponse(
        message="获取当前用户成功。",
        data=UserProfile.model_validate(current_user),
    )


@router.patch("/me", response_model=CurrentUserResponse, summary="更新当前用户资料")
async def update_me(
    payload: UpdateUserProfileRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CurrentUserResponse:
    """更新当前登录用户的昵称等基础资料。"""

    user = AuthService(db).update_user_profile(
        user=current_user,
        username=payload.username,
    )
    return CurrentUserResponse(
        message="用户资料已更新。",
        data=UserProfile.model_validate(user),
    )


@router.patch("/password", response_model=MessageResponse, summary="修改当前用户密码")
async def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """校验当前密码后修改当前登录用户密码。"""

    AuthService(db).change_password(
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="密码已更新，请使用新密码登录。")
