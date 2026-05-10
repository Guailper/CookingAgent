"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.cache.cache_service import CacheService
from src.cache.rate_limiter import RateLimiter
from src.core.config import get_settings
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
    request: Request,
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Send a registration or login verification code."""

    settings = get_settings()
    cache = CacheService(settings)
    client_id = _request_client_id(request)
    normalized_email = payload.email.strip().lower()
    RateLimiter(cache).require_allowed(
        key=cache.build_key("rate_limit", "email_code", payload.purpose, normalized_email, client_id),
        limit=settings.email_code_rate_limit_count,
        window_seconds=settings.email_code_rate_limit_window_seconds,
        error_code="EMAIL_CODE_RATE_LIMITED",
        message="验证码请求过于频繁，请稍后再试。",
    )

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
    """Register a user and return an access token."""

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
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """Login with password and return an access token."""

    _apply_login_rate_limit(request, payload.email)
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
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """Login with an email verification code and return an access token."""

    _apply_login_rate_limit(request, payload.email)
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
    """Return current signed-in user profile."""

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
    """Update current signed-in user's basic profile."""

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
    """Validate current password and change it."""

    AuthService(db).change_password(
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="密码已更新，请使用新密码登录。")


def _apply_login_rate_limit(request: Request, email: str) -> None:
    settings = get_settings()
    cache = CacheService(settings)
    RateLimiter(cache).require_allowed(
        key=cache.build_key("rate_limit", "login", email.strip().lower(), _request_client_id(request)),
        limit=settings.login_rate_limit_count,
        window_seconds=settings.login_rate_limit_window_seconds,
        error_code="LOGIN_RATE_LIMITED",
        message="登录尝试过于频繁，请稍后再试。",
    )


def _request_client_id(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
