"""Email verification code data access layer."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.email_verification_code import EmailVerificationCode


class EmailVerificationCodeRepository:
    """Encapsulates common verification code queries and writes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, verification_code: EmailVerificationCode) -> EmailVerificationCode:
        """Add a new verification code row to the current transaction."""

        self.db.add(verification_code)
        self.db.flush()
        return verification_code

    def get_latest(self, email: str, purpose: str) -> EmailVerificationCode | None:
        """Return the newest code for an email and purpose."""

        stmt = (
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == purpose,
            )
            .order_by(EmailVerificationCode.created_at.desc(), EmailVerificationCode.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get_active(self, email: str, purpose: str, now: datetime) -> EmailVerificationCode | None:
        """Return the newest unexpired and unused code."""

        stmt = (
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == purpose,
                EmailVerificationCode.used_at.is_(None),
                EmailVerificationCode.expires_at > now,
            )
            .order_by(EmailVerificationCode.created_at.desc(), EmailVerificationCode.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)
