"""Conversation summary ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from .conversation import Conversation


class ConversationSummary(Base):
    """Store the model-maintained rolling summary for a long conversation."""

    __tablename__ = "conversation_summaries"
    __table_args__ = (
        Index("idx_conversation_summaries_conversation", "conversation_id"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "conversation rolling summary table",
        },
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="internal primary key",
    )
    conversation_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("conversations.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
        unique=True,
        comment="conversation id",
    )
    conversation_public_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="conversation public business id",
    )
    summary_text: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
        default="",
        server_default=text("''"),
        comment="model generated summary text",
    )
    covered_until_message_public_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="last message public id covered by summary",
    )
    source_message_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="number of messages covered by summary",
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="summary model name",
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
        back_populates="summary",
    )
