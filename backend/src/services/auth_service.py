"""认证业务服务。"""

from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.constants import (
    EMAIL_CODE_EXPIRE_MINUTES,
    EMAIL_CODE_MAX_VERIFY_ATTEMPTS,
    EMAIL_CODE_PURPOSE_LOGIN,
    EMAIL_CODE_PURPOSE_REGISTER,
    EMAIL_CODE_RESEND_INTERVAL_SECONDS,
    USER_STATUS_ACTIVE,
)
from src.core.exceptions import AppException
from src.core.security import create_access_token, generate_public_id, hash_password, verify_password
from src.db.models.email_verification_code import EmailVerificationCode
from src.db.models.user import User
from src.repositories.email_verification_code_repository import EmailVerificationCodeRepository
from src.repositories.user_repository import UserRepository
from src.services.email_service import EmailService


class AuthService:
    """处理用户注册、登录、邮箱验证码和令牌签发。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.user_repository = UserRepository(db)
        self.email_code_repository = EmailVerificationCodeRepository(db)
        self.email_service = EmailService(self.settings)

    def send_email_code(self, email: str, purpose: str) -> None:
        """生成并发送邮箱验证码。"""

        normalized_email = self._normalize_email(email)
        self._validate_email_code_purpose(purpose)

        if purpose == EMAIL_CODE_PURPOSE_REGISTER:
            existing_user = self.user_repository.get_by_email(normalized_email)
            if existing_user is not None:
                raise AppException(409, "EMAIL_ALREADY_EXISTS", "该邮箱已被注册。")

        if purpose == EMAIL_CODE_PURPOSE_LOGIN:
            existing_user = self.user_repository.get_by_email(normalized_email)
            if existing_user is None:
                raise AppException(404, "EMAIL_NOT_REGISTERED", "该邮箱尚未注册。")

        now = datetime.utcnow()
        latest_code = self.email_code_repository.get_latest(normalized_email, purpose)
        if latest_code is not None:
            elapsed_seconds = (now - latest_code.created_at).total_seconds()
            if elapsed_seconds < EMAIL_CODE_RESEND_INTERVAL_SECONDS:
                wait_seconds = int(EMAIL_CODE_RESEND_INTERVAL_SECONDS - elapsed_seconds)
                raise AppException(
                    429,
                    "EMAIL_CODE_TOO_FREQUENT",
                    f"验证码发送过于频繁，请 {wait_seconds} 秒后再试。",
                    {"wait_seconds": wait_seconds},
                )

        code = f"{secrets.randbelow(1_000_000):06d}"
        verification_code = EmailVerificationCode(
            email=normalized_email,
            purpose=purpose,
            code_hash=self._hash_email_code(normalized_email, purpose, code),
            expires_at=now + timedelta(minutes=EMAIL_CODE_EXPIRE_MINUTES),
        )

        self.email_code_repository.create(verification_code)
        self.db.commit()

        self.email_service.send_verification_code(
            email=normalized_email,
            code=code,
            purpose=purpose,
            expires_minutes=EMAIL_CODE_EXPIRE_MINUTES,
        )

    def register_user(self, username: str, email: str, password: str, email_code: str) -> tuple[User, str]:
        """注册新用户并返回访问令牌。"""

        normalized_username = username.strip()
        normalized_email = self._normalize_email(email)
        if not normalized_username:
            raise AppException(400, "INVALID_USERNAME", "用户名不能为空。")

        self._consume_email_code(normalized_email, EMAIL_CODE_PURPOSE_REGISTER, email_code)

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
        """校验密码登录信息并返回访问令牌。"""

        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            raise AppException(401, "INVALID_CREDENTIALS", "邮箱或密码不正确。")

        self._touch_last_login(user)
        return user, self._issue_access_token(user)

    def login_user_with_email_code(self, email: str, email_code: str) -> tuple[User, str]:
        """校验邮箱验证码并返回访问令牌。"""

        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)
        if user is None:
            raise AppException(404, "EMAIL_NOT_REGISTERED", "该邮箱尚未注册。")

        self._consume_email_code(normalized_email, EMAIL_CODE_PURPOSE_LOGIN, email_code)
        self._touch_last_login(user)
        return user, self._issue_access_token(user)

    def update_user_profile(self, user: User, username: str) -> User:
        """更新当前用户的基础资料。"""

        normalized_username = username.strip()
        if not normalized_username:
            raise AppException(400, "INVALID_USERNAME", "用户名不能为空。")

        user.username = normalized_username
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """校验旧密码后修改当前用户密码。"""

        if not verify_password(current_password, user.password_hash):
            raise AppException(400, "INVALID_CURRENT_PASSWORD", "当前密码不正确。")

        if len(new_password.strip()) < 8:
            raise AppException(400, "WEAK_PASSWORD", "新密码至少需要 8 位字符。")

        user.password_hash = hash_password(new_password)
        self.db.commit()

    def get_user_by_public_id(self, public_id: str) -> User | None:
        """根据业务 ID 查询用户。"""

        return self.user_repository.get_by_public_id(public_id)

    def _consume_email_code(self, email: str, purpose: str, raw_code: str) -> None:
        """校验并消费验证码。

        验证码一旦校验成功就立即标记为已使用，避免同一个验证码重复注册或重复登录。
        """

        normalized_code = raw_code.strip()
        now = datetime.utcnow()
        verification_code = self.email_code_repository.get_active(email, purpose, now)
        if verification_code is None:
            raise AppException(400, "EMAIL_CODE_INVALID_OR_EXPIRED", "验证码无效或已过期。")

        if verification_code.failed_attempts >= EMAIL_CODE_MAX_VERIFY_ATTEMPTS:
            verification_code.used_at = now
            self.db.commit()
            raise AppException(400, "EMAIL_CODE_LOCKED", "验证码错误次数过多，请重新获取。")

        expected_hash = self._hash_email_code(email, purpose, normalized_code)
        if not hmac.compare_digest(expected_hash, verification_code.code_hash):
            verification_code.failed_attempts += 1
            self.db.commit()
            raise AppException(400, "EMAIL_CODE_INVALID_OR_EXPIRED", "验证码无效或已过期。")

        verification_code.used_at = now
        self.db.flush()

    def _touch_last_login(self, user: User) -> None:
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)

    def _issue_access_token(self, user: User) -> str:
        """为用户生成访问令牌。"""

        return create_access_token(
            subject=user.public_id,
            secret_key=self.settings.app_secret_key,
            expires_minutes=self.settings.access_token_expire_minutes,
        )

    def _hash_email_code(self, email: str, purpose: str, code: str) -> str:
        """使用应用密钥哈希验证码，避免数据库泄露时暴露明文验证码。"""

        payload = f"{email}:{purpose}:{code}".encode("utf-8")
        return hmac.new(
            self.settings.app_secret_key.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise AppException(400, "INVALID_EMAIL", "邮箱不能为空。")
        return normalized_email

    @staticmethod
    def _validate_email_code_purpose(purpose: str) -> None:
        if purpose not in {EMAIL_CODE_PURPOSE_REGISTER, EMAIL_CODE_PURPOSE_LOGIN}:
            raise AppException(400, "INVALID_EMAIL_CODE_PURPOSE", "验证码用途不正确。")
