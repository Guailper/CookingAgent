"""API 依赖项定义。

这里集中放 FastAPI 接口层会复用的依赖函数，例如数据库会话、
当前用户、权限校验等，避免这些逻辑散落在每个端点文件里。
"""

from collections.abc import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.constants import USER_STATUS_ACTIVE
from src.core.exceptions import AppException
from src.core.security import TokenValidationError, decode_access_token
from src.db.models.user import User
from src.db.session import get_db
from src.services.auth_service import AuthService

security_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    """向接口层暴露数据库会话依赖。"""

    yield from get_db()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    """解析 Bearer Token 并返回当前登录用户。"""

    if credentials is None:
        raise AppException(401, "AUTH_REQUIRED", "当前请求缺少访问令牌。")

    settings = get_settings()
    try:
        payload = decode_access_token(credentials.credentials, settings.app_secret_key)
    except TokenValidationError as exc:
        raise AppException(401, "INVALID_ACCESS_TOKEN", str(exc)) from exc

    user_public_id = payload["sub"]
    user = AuthService(db).get_user_by_public_id(user_public_id)
    if user is None:
        raise AppException(401, "USER_NOT_FOUND", "访问令牌对应的用户不存在。")
    if user.status != USER_STATUS_ACTIVE:
        raise AppException(403, "USER_DISABLED", "当前用户状态不可用。")

    return user
