"""Authentication business service."""

from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.cache.cache_service import CacheService
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
    """Handle registration, login, email verification codes, and token issuance."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.user_repository = UserRepository(db)
        self.email_code_repository = EmailVerificationCodeRepository(db)
        self.email_service = EmailService(self.settings)
        self.cache = CacheService(self.settings)

    def send_email_code(self, email: str, purpose: str) -> None:
        """Generate and send an email verification code."""

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
        self._ensure_email_code_can_be_sent(normalized_email, purpose, now)

        code = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = self._hash_email_code(normalized_email, purpose, code)

        try:
            self.email_service.send_verification_code(
                email=normalized_email,
                code=code,
                purpose=purpose,
                expires_minutes=EMAIL_CODE_EXPIRE_MINUTES,
            )
            self._store_email_code(
                email=normalized_email,
                purpose=purpose,
                code_hash=code_hash,
                created_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def register_user(self, username: str, email: str, password: str, email_code: str) -> tuple[User, str]:
        """Register a new user and return an access token."""

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
        self._cache_user(user)
        return user, self._issue_access_token(user)

    def login_user(self, email: str, password: str) -> tuple[User, str]:
        """Validate password credentials and return an access token."""

        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            raise AppException(401, "INVALID_CREDENTIALS", "邮箱或密码不正确。")

        self._touch_last_login(user)
        return user, self._issue_access_token(user)

    def login_user_with_email_code(self, email: str, email_code: str) -> tuple[User, str]:
        """Validate an email verification code and return an access token."""

        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)
        if user is None:
            raise AppException(404, "EMAIL_NOT_REGISTERED", "该邮箱尚未注册。")

        self._consume_email_code(normalized_email, EMAIL_CODE_PURPOSE_LOGIN, email_code)
        self._touch_last_login(user)
        return user, self._issue_access_token(user)

    def update_user_profile(self, user: User, username: str) -> User:
        """Update current user's basic profile."""

        normalized_username = username.strip()
        if not normalized_username:
            raise AppException(400, "INVALID_USERNAME", "用户名不能为空。")

        managed_user = self._load_managed_user(user)
        managed_user.username = normalized_username
        self.db.commit()
        self.db.refresh(managed_user)
        self._cache_user(managed_user)
        return managed_user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Validate and change the current user's password."""

        managed_user = self._load_managed_user(user)
        if not verify_password(current_password, managed_user.password_hash):
            raise AppException(400, "INVALID_CURRENT_PASSWORD", "当前密码不正确。")

        if len(new_password.strip()) < 8:
            raise AppException(400, "WEAK_PASSWORD", "新密码至少需要 8 位字符。")

        managed_user.password_hash = hash_password(new_password)
        self.db.commit()
        self._cache_user(managed_user)

    def get_user_by_public_id(self, public_id: str) -> User | None:
        """Fetch a user by public id, using a short Redis snapshot when available."""

        cached_user = self._get_cached_user(public_id)
        if cached_user is not None:
            return cached_user

        user = self.user_repository.get_by_public_id(public_id)
        if user is not None:
            self._cache_user(user)
        return user

    def _consume_email_code(self, email: str, purpose: str, raw_code: str) -> None:
        """Validate and consume a one-time email verification code."""

        normalized_code = raw_code.strip()
        if self.cache.available:
            self._consume_redis_email_code(email, purpose, normalized_code)
            return

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
        self._cache_user(user)

    def _ensure_email_code_can_be_sent(self, email: str, purpose: str, now: datetime) -> None:
        if self.cache.available:
            wait_seconds = self.cache.ttl(self._email_code_cooldown_key(email, purpose))
            if wait_seconds is not None:
                raise AppException(
                    429,
                    "EMAIL_CODE_TOO_FREQUENT",
                    f"验证码发送过于频繁，请 {wait_seconds} 秒后再试。",
                    {"wait_seconds": wait_seconds},
                )
            return

        latest_code = self.email_code_repository.get_latest(email, purpose)
        if latest_code is None:
            return

        elapsed_seconds = (now - latest_code.created_at).total_seconds()
        if elapsed_seconds >= EMAIL_CODE_RESEND_INTERVAL_SECONDS:
            return

        wait_seconds = min(
            EMAIL_CODE_RESEND_INTERVAL_SECONDS,
            max(1, int(EMAIL_CODE_RESEND_INTERVAL_SECONDS - elapsed_seconds)),
        )
        raise AppException(
            429,
            "EMAIL_CODE_TOO_FREQUENT",
            f"验证码发送过于频繁，请 {wait_seconds} 秒后再试。",
            {"wait_seconds": wait_seconds},
        )

    def _store_email_code(
        self,
        *,
        email: str,
        purpose: str,
        code_hash: str,
        created_at: datetime,
    ) -> None:
        if self.cache.available:
            self.cache.set_json(
                self._email_code_key(email, purpose),
                {
                    "email": email,
                    "purpose": purpose,
                    "code_hash": code_hash,
                    "failed_attempts": 0,
                    "created_at": created_at,
                },
                EMAIL_CODE_EXPIRE_MINUTES * 60,
            )
            self.cache.set_json(
                self._email_code_cooldown_key(email, purpose),
                {"created_at": created_at},
                EMAIL_CODE_RESEND_INTERVAL_SECONDS,
            )
            return

        verification_code = EmailVerificationCode(
            email=email,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=created_at + timedelta(minutes=EMAIL_CODE_EXPIRE_MINUTES),
            created_at=created_at,
        )
        self.email_code_repository.create(verification_code)

    def _consume_redis_email_code(self, email: str, purpose: str, raw_code: str) -> None:
        code_key = self._email_code_key(email, purpose)
        payload = self.cache.get_json(code_key)
        if not isinstance(payload, dict):
            raise AppException(400, "EMAIL_CODE_INVALID_OR_EXPIRED", "验证码无效或已过期。")

        failed_attempts = int(payload.get("failed_attempts") or 0)
        if failed_attempts >= EMAIL_CODE_MAX_VERIFY_ATTEMPTS:
            self.cache.delete(code_key)
            raise AppException(400, "EMAIL_CODE_LOCKED", "验证码错误次数过多，请重新获取。")

        expected_hash = self._hash_email_code(email, purpose, raw_code)
        stored_hash = str(payload.get("code_hash") or "")
        if not hmac.compare_digest(expected_hash, stored_hash):
            payload["failed_attempts"] = failed_attempts + 1
            self.cache.set_json(
                code_key,
                payload,
                self.cache.ttl(code_key) or EMAIL_CODE_EXPIRE_MINUTES * 60,
            )
            raise AppException(400, "EMAIL_CODE_INVALID_OR_EXPIRED", "验证码无效或已过期。")

        self.cache.delete(code_key)

    def _cache_user(self, user: User) -> None:
        self.cache.set_json(
            self._user_key(user.public_id),
            {
                "id": user.id,
                "public_id": user.public_id,
                "username": user.username,
                "email": user.email,
                "status": user.status,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            },
            self.settings.current_user_cache_ttl_seconds,
        )

    def _get_cached_user(self, public_id: str) -> User | None:
        payload = self.cache.get_json(self._user_key(public_id))
        if not isinstance(payload, dict):
            return None

        try:
            user = User(
                id=int(payload["id"]),
                public_id=str(payload["public_id"]),
                username=str(payload["username"]),
                email=str(payload["email"]),
                password_hash="",
                status=str(payload["status"]),
            )
            user.last_login_at = self._parse_datetime(payload.get("last_login_at"))
            user.created_at = self._parse_datetime(payload.get("created_at")) or datetime.utcnow()
            user.updated_at = self._parse_datetime(payload.get("updated_at")) or datetime.utcnow()
        except (KeyError, TypeError, ValueError):
            self.cache.delete(self._user_key(public_id))
            return None

        return user

    def _load_managed_user(self, user: User) -> User:
        managed_user = self.user_repository.get_by_public_id(user.public_id)
        if managed_user is None:
            raise AppException(401, "USER_NOT_FOUND", "访问令牌对应的用户不存在。")
        return managed_user

    def _issue_access_token(self, user: User) -> str:
        """Generate a signed access token."""

        return create_access_token(
            subject=user.public_id,
            secret_key=self.settings.app_secret_key,
            expires_minutes=self.settings.access_token_expire_minutes,
        )

    def _hash_email_code(self, email: str, purpose: str, code: str) -> str:
        """Hash verification codes before storage."""

        payload = f"{email}:{purpose}:{code}".encode("utf-8")
        return hmac.new(
            self.settings.app_secret_key.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    def _email_code_key(self, email: str, purpose: str) -> str:
        return self.cache.build_key("email_code", purpose, email)

    def _email_code_cooldown_key(self, email: str, purpose: str) -> str:
        return self.cache.build_key("email_code_cooldown", purpose, email)

    def _user_key(self, public_id: str) -> str:
        return self.cache.build_key("user", "public_id", public_id)

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

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
