"""Database session helpers and lightweight startup schema compatibility."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.core.logging import get_logger
from src.db.base import Base, SessionLocal, engine, get_db
from src.db.models import import_all_models

logger = get_logger(__name__)


def _ensure_attachment_feature_columns() -> None:
    """Patch legacy attachments tables so upload-before-send keeps working locally.

    `create_all()` only creates missing tables. It does not evolve existing schemas,
    so older local databases would miss the new `attachment_kind` column and still
    keep `message_id` as NOT NULL. We fix just those two feature-specific columns
    here to keep development startup smooth without introducing a full migration flow.
    """

    inspector = inspect(engine)
    if not inspector.has_table("attachments"):
        return

    columns = {column["name"]: column for column in inspector.get_columns("attachments")}
    statements: list[str] = []

    if "attachment_kind" not in columns:
        statements.append(
            """
            ALTER TABLE attachments
            ADD COLUMN attachment_kind VARCHAR(32) NOT NULL DEFAULT 'document'
            COMMENT 'Attachment kind: document or image'
            AFTER file_size
            """
        )

    message_id = columns.get("message_id")
    if message_id is not None and not message_id.get("nullable", False):
        statements.append(
            """
            ALTER TABLE attachments
            MODIFY COLUMN message_id BIGINT UNSIGNED NULL
            COMMENT 'Bound message ID, nullable until a message is sent'
            """
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    logger.info("Legacy attachment schema compatibility updates applied.")


def create_all_tables() -> None:
    """Import models, create missing tables, then patch local legacy schemas."""

    import_all_models()
    Base.metadata.create_all(bind=engine)
    _ensure_attachment_feature_columns()
    logger.info("All registered tables have been created or already exist.")


def get_session_factory():
    """Return the SQLAlchemy session factory for scripts or background work."""

    return SessionLocal
