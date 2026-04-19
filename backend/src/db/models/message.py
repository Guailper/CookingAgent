"""消息表 ORM 模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Message(Base):
    """消息实体，负责保存会话中的文本、多模态和系统消息。"""

    __tablename__ = "messages"
    # 这里对齐了消息表的查询索引，方便按会话、角色和消息类型检索。
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

    # 主键和外键字段。
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

    # 消息主体字段。
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="message role",
    )
    message_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="text",
        server_default=text("'text'"),
        comment="message type",
    )
    content: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
        comment="message content",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
        server_default=text("'completed'"),
        comment="message status",
    )
    extra_metadata: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="extra metadata",
    )

    # 审计字段：记录消息创建与更新时间。
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

    # ORM 关系：一条消息属于一个会话，可选关联一个用户，并可挂多个附件。
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
