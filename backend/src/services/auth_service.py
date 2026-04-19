"""认证业务服务。"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.constants import USER_STATUS_ACTIVE
from src.core.exceptions import AppException
from src.core.security import create_access_token, generate_public_id, hash_password, verify_password
from src.db.models.user import User
from src.repositories.user_repository import UserRepository


class AuthService:
    """处理用户注册、登录和令牌签发。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.user_repository = UserRepository(db)

    def register_user(self, username: str, email: str, password: str) -> tuple[User, str]:
        """注册新用户并返回访问令牌。"""

        normalized_username = username.strip()
        normalized_email = email.strip().lower()
        if not normalized_username:
            raise AppException(400, "INVALID_USERNAME", "用户名不能为空。")

        existing_user = self.user_repository.get_by_email(normalized_email)
        if existing_user is not None:
            raise AppException(409, "EMAIL_ALREADY_EXISTS", "该邮箱已被注册。")

        user = User(
            public_id=generate_public_id("user"),
            username=normalized_username,
            email=normalized_email,
            password_hash=hash_password(password),
            status=USER_STATUS_ACTIVE,
        )

        try:
            self.user_repository.create(user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppException(409, "USER_CREATE_CONFLICT", "用户创建发生冲突。") from exc

        self.db.refresh(user)
        return user, self._issue_access_token(user)

    def login_user(self, email: str, password: str) -> tuple[User, str]:
        """校验登录信息并返回访问令牌。"""

        normalized_email = email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            raise AppException(401, "INVALID_CREDENTIALS", "邮箱或密码不正确。")

        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user, self._issue_access_token(user)

    def get_user_by_public_id(self, public_id: str) -> User | None:
        """根据业务 ID 查询用户。"""

        return self.user_repository.get_by_public_id(public_id)

    def _issue_access_token(self, user: User) -> str:
        """为用户生成访问令牌。"""

        return create_access_token(
            subject=user.public_id,
            secret_key=self.settings.app_secret_key,
            expires_minutes=self.settings.access_token_expire_minutes,
        )
