"""Data access helpers for uploaded chat attachments."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.attachment import Attachment


class AttachmentRepository:
    """Encapsulate reads and writes for attachment records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, attachment: Attachment) -> Attachment:
        """Add an attachment to the current transaction."""

        self.db.add(attachment)
        self.db.flush()
        return attachment

    def get_by_public_id(self, public_id: str) -> Attachment | None:
        """Fetch a single attachment by its public business identifier."""

        stmt = select(Attachment).where(Attachment.public_id == public_id)
        return self.db.scalar(stmt)

    def list_by_public_ids_and_conversation_id(
        self,
        public_ids: Iterable[str],
        conversation_id: int,
    ) -> list[Attachment]:
        """Fetch attachments belonging to the same conversation in one query."""

        normalized_ids = [public_id for public_id in public_ids if public_id]
        if not normalized_ids:
            return []

        stmt = select(Attachment).where(
            Attachment.public_id.in_(normalized_ids),
            Attachment.conversation_id == conversation_id,
        )
        return list(self.db.scalars(stmt).all())

    def delete(self, attachment: Attachment) -> None:
        """Delete an attachment inside the current transaction."""

        self.db.delete(attachment)
        self.db.flush()
