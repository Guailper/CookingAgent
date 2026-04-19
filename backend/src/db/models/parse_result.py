"""附件解析结果表 ORM 模型。"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ParseResult(Base):
    """附件解析结果实体，负责保存文本抽取、OCR 和结构化输出。"""

    __tablename__ = "parse_results"
    # 这里补充了状态类索引，便于查询解析进度和向量化处理进度。
    __table_args__ = (
        Index("idx_parse_results_status", "parse_status"),
        Index("idx_parse_results_embedding_status", "embedding_status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
            "comment": "parse result table",
        },
    )

    # 主键和附件外键。attachment_id 唯一，表示一个附件只对应一条解析结果。
    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="internal primary key",
    )
    attachment_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("attachments.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
        unique=True,
        comment="attachment id",
    )

    # 解析执行信息。
    parser_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="parser name",
    )
    parse_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
        server_default=text("'completed'"),
        comment="parse status",
    )
    embedding_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="embedding status",
    )

    # 解析结果正文和结构化产物。
    raw_text: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="raw extracted text",
    )
    structured_result: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="structured parse result",
    )
    ocr_result: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="ocr result",
    )

    # 耗时相关字段，便于排查性能问题和失败阶段。
    started_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="parse started time",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="parse completed time",
    )

    # 审计字段：记录解析记录创建与更新时间。
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

    # ORM 关系：一条解析结果只属于一个附件。
    attachment: Mapped["Attachment"] = relationship(
        "Attachment",
        back_populates="parse_result",
    )

    def __repr__(self) -> str:
        return (
            "ParseResult("
            f"id={self.id!r}, "
            f"attachment_id={self.attachment_id!r}, "
            f"parse_status={self.parse_status!r}, "
            f"embedding_status={self.embedding_status!r}"
            ")"
        )
