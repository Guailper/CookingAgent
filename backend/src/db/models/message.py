"""Chat message ORM model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.constants import MESSAGE_STATUS_COMPLETED, MESSAGE_TYPE_TEXT
from src.db.base import Base


class Message(Base):
    """Store user, assistant, and system messages inside a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
        Index("idx_messages_user_id", "user_id"),
        Index("idx_messages_role", "role"),
        Index("idx_messages_type", "message_type"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "message table",
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
    user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="SET NULL", onupdate="RESTRICT"),
        nullable=True,
        comment="sender user id",
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="message role",
    )
    message_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MESSAGE_TYPE_TEXT,
        server_default=text(f"'{MESSAGE_TYPE_TEXT}'"),
        comment="message type",
    )
    # LONGTEXT allows long transcripts and attachment-related summaries later on.
    # Voice input is persisted as transcribed text rather than raw audio.
    content: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
        default="",
        server_default=text("''"),
        comment="message content",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MESSAGE_STATUS_COMPLETED,
        server_default=text(f"'{MESSAGE_STATUS_COMPLETED}'"),
        comment="message status",
    )
    extra_metadata: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="extra metadata",
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
        back_populates="messages",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="messages",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="message",
        passive_deletes=True,
        order_by="Attachment.created_at",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="message",
        passive_deletes=True,
        order_by="AgentRun.created_at",
    )

    def __repr__(self) -> str:
        return (
            "Message("
            f"id={self.id!r}, "
            f"public_id={self.public_id!r}, "
            f"role={self.role!r}, "
            f"message_type={self.message_type!r}"
            ")"
        )
