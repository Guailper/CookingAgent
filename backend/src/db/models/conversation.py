"""会话表 ORM 模型。"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Conversation(Base):
    """会话实体，负责保存用户的一次连续交互上下文。"""

    __tablename__ = "conversations"
    # 这里对齐了建表 SQL 里的组合索引和 MySQL 表级配置。
    __table_args__ = (
        Index("idx_conversations_user_created", "user_id", "created_at"),
        Index("idx_conversations_user_latest", "user_id", "latest_message_at"),
        Index("idx_conversations_status", "status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "conversation table",
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
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
        comment="owner user id",
    )

    # 会话基本信息，用于列表展示和状态管理。
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="新对话",
        server_default=text("'新对话'"),
        comment="conversation title",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="conversation status",
    )
    latest_message_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="latest message time",
    )

    # 审计字段：记录会话创建与更新时间。
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

    # ORM 关系：一个会话属于一个用户，并可关联多条消息和附件。
    user: Mapped["User"] = relationship(
        "User",
        back_populates="conversations",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        passive_deletes=True,
        order_by="Message.created_at",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="conversation",
        passive_deletes=True,
        order_by="Attachment.created_at",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="conversation",
        passive_deletes=True,
        order_by="AgentRun.created_at",
    )

    def __repr__(self) -> str:
        return (
            "Conversation("
            f"id={self.id!r}, "
            f"public_id={self.public_id!r}, "
            f"user_id={self.user_id!r}, "
            f"status={self.status!r}"
            ")"
        )
