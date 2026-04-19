"""认证接口实现。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.auth import AuthPayload, AuthResponse, CurrentUserResponse, LoginRequest, RegisterRequest, UserProfile
from src.services.auth_service import AuthService

router = APIRouter()

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
    )
    return AuthResponse(
        message="注册成功。",
        data=AuthPayload(
            access_token=access_token,
            user=UserProfile.model_validate(user),
        ),
    )


@router.post("/login", response_model=AuthResponse, summary="账号登录")
async def login(
    payload: LoginRequest,
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """登录并返回访问令牌。"""

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


@router.get("/me", response_model=CurrentUserResponse, summary="获取当前用户")
async def get_me(current_user=Depends(get_current_user)) -> CurrentUserResponse:
    """返回当前登录用户信息。"""

    return CurrentUserResponse(
        message="获取当前用户成功。",
        data=UserProfile.model_validate(current_user),
    )
