"""Agent 运行记录表 ORM 模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class AgentRun(Base):
    """Agent 运行记录实体，负责保存一次工作流执行的输入、输出与状态。"""

    __tablename__ = "agent_runs"
    # 这里对齐了运行记录表的核心索引，方便按会话、消息、用户和状态查询。
    __table_args__ = (
        Index("idx_agent_runs_conversation_created", "conversation_id", "created_at"),
        Index("idx_agent_runs_message_id", "message_id"),
        Index("idx_agent_runs_user_id", "user_id"),
        Index("idx_agent_runs_status", "run_status"),
        Index("idx_agent_runs_intent_type", "intent_type"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "agent run table",
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
    message_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("messages.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
        comment="trigger message id",
    )
    user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="SET NULL", onupdate="RESTRICT"),
        nullable=True,
        comment="related user id",
    )

    # 运行识别和路由信息。
    intent_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="intent type",
    )
    workflow_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="workflow name",
    )
    run_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="run status",
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="model name",
    )

    # 运行输入输出和错误信息。
    input_snapshot: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="input snapshot",
    )
    output_snapshot: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="output snapshot",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="error code",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="error message",
    )

    # 运行耗时和审计字段。
    started_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="started time",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="completed time",
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

    # ORM 关系：一条运行记录归属于一个会话，并由一条消息触发，可选关联一个用户。
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="agent_runs",
    )
    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="agent_runs",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="agent_runs",
    )

    def __repr__(self) -> str:
        return (
            "AgentRun("
            f"id={self.id!r}, "
            f"public_id={self.public_id!r}, "
            f"intent_type={self.intent_type!r}, "
            f"run_status={self.run_status!r}"
            ")"
        )
