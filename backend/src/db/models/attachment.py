"""Attachment ORM model used for chat message uploads."""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.constants import ATTACHMENT_KIND_DOCUMENT, PARSE_STATUS_PENDING
from src.db.base import Base


class Attachment(Base):
    """Persist uploaded files before and after they are bound to a chat message."""

    __tablename__ = "attachments"
    __table_args__ = (
        Index("idx_attachments_conversation_id", "conversation_id"),
        Index("idx_attachments_message_id", "message_id"),
        Index("idx_attachments_parse_status", "parse_status"),
        Index("idx_attachments_file_hash", "file_hash"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "attachment table",
        },
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="internal primary key",
    )
    public_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="public business id",
    )
    conversation_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("conversations.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
        comment="conversation id",
    )
    # The message binding happens after upload succeeds, so this field must allow NULL.
    message_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("messages.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=True,
        comment="bound message id",
    )

    original_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="original file name",
    )
    stored_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="stored file name",
    )
    file_ext: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="file extension",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="mime type",
    )
    file_size: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
        comment="file size in bytes",
    )
    attachment_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ATTACHMENT_KIND_DOCUMENT,
        server_default=text(f"'{ATTACHMENT_KIND_DOCUMENT}'"),
        comment="attachment kind",
    )
    storage_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="local",
        server_default=text("'local'"),
        comment="storage provider",
    )
    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="storage path",
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="file hash",
    )
    parse_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PARSE_STATUS_PENDING,
        server_default=text(f"'{PARSE_STATUS_PENDING}'"),
        comment="parse status",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="created time",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="updated time",
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="attachments",
    )
    message: Mapped[Optional["Message"]] = relationship(
        "Message",
        back_populates="attachments",
    )
    parse_result: Mapped[Optional["ParseResult"]] = relationship(
        "ParseResult",
        back_populates="attachment",
        passive_deletes=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            "Attachment("
            f"id={self.id!r}, "
            f"public_id={self.public_id!r}, "
            f"mime_type={self.mime_type!r}, "
            f"parse_status={self.parse_status!r}"
            ")"
        )
