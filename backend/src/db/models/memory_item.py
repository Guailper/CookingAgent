"""用户长期记忆 ORM 模型。"""

from datetime import datetime

from sqlalchemy import JSON, Index, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class MemoryItem(Base):
    """保存可复用的用户偏好、忌口、厨具和健康目标。

    第一版使用 user_public_id 作为归属键，避免强依赖用户表内部自增 ID，
    也方便后续把记忆迁移到向量库或独立服务。
    """

    __tablename__ = "memory_items"
    __table_args__ = (
        Index("idx_memory_items_user_type", "user_public_id", "memory_type"),
        Index("idx_memory_items_created_at", "created_at"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "user long-term memory table",
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
    user_public_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="owner user public id",
    )
    conversation_public_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="source conversation public id",
    )
    source_message_public_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="source message public id",
    )
    memory_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="preference, dislike, appliance, health_goal, etc.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="normalized memory content",
    )
    confidence: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="1.0",
        server_default=text("'1.0'"),
        comment="stringified confidence for simple MySQL compatibility",
    )
    extra_metadata: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="additional extraction metadata",
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
