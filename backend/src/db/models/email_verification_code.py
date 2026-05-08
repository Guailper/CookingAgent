"""Email verification code ORM model."""

from datetime import datetime

from sqlalchemy import Index, Integer, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class EmailVerificationCode(Base):
    """Stores short-lived email verification codes for registration and login."""

    __tablename__ = "email_verification_codes"
    __table_args__ = (
        Index("idx_email_codes_email_purpose", "email", "purpose"),
        Index("idx_email_codes_expires_at", "expires_at"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "email verification code table",
        },
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="internal primary key",
    )
    email: Mapped[str] = mapped_column(
        String(191),
        nullable=False,
        comment="target email address",
    )
    purpose: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="verification purpose: register or login",
    )
    code_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="hashed verification code",
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="failed verification attempts",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        comment="code expiration time",
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="time when the code was consumed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="created time",
    )

    def __repr__(self) -> str:
        return (
            "EmailVerificationCode("
            f"id={self.id!r}, "
            f"email={self.email!r}, "
            f"purpose={self.purpose!r}, "
            f"expires_at={self.expires_at!r}"
            ")"
        )
