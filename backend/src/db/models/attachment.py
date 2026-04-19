"""附件表 ORM 模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Attachment(Base):
    """附件实体，负责保存上传文件的存储信息和解析状态。"""

    __tablename__ = "attachments"
    # 这里补充了常用查询索引，方便按会话、消息和解析状态定位附件。
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
        comment="source message id",
    )

    # 文件基础信息和存储定位字段。
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

    # 解析状态字段，用于跟踪文件是否已经被文本抽取或 OCR 处理。
    parse_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="parse status",
    )

    # 审计字段：记录附件创建与更新时间。
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

    # ORM 关系：一个附件来自一条消息，同时归属于一个会话。
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="attachments",
    )
    message: Mapped["Message"] = relationship(
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
