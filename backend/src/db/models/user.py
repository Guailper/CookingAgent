"""用户表 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class User(Base):
    """系统用户实体，负责保存账号身份、登录信息和基础状态。"""

    __tablename__ = "users"
    # 这里补充了与建表 SQL 对应的索引和 MySQL 表级配置。
    __table_args__ = (
        Index("idx_users_status", "status"),
        Index("idx_users_created_at", "created_at"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "user table",
        },
    )

    # 主键和对外业务标识。
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

    # 用户基础信息与登录凭据。
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="username or nickname",
    )
    email: Mapped[str] = mapped_column(
        String(191),
        nullable=False,
        unique=True,
        comment="login email",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="password hash",
    )

    # 账号状态和最近一次登录时间，便于做风控和运营管理。
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="user status",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="last login time",
    )

    # 审计字段：记录创建时间和最后更新时间。
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

    # ORM 关系：一个用户可以拥有多个会话、消息和 Agent 运行记录。
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        passive_deletes=True,
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="user",
        passive_deletes=True,
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="user",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            "User("
            f"id={self.id!r}, "
            f"public_id={self.public_id!r}, "
            f"email={self.email!r}, "
            f"status={self.status!r}"
            ")"
        )
