"""Data access helpers for the messages table."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.db.models.message import Message


class MessageRepository:
    """Encapsulate common message queries and writes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, message: Message) -> Message:
        """Add a message to the current transaction."""

        self.db.add(message)
        self.db.flush()
        return message

    def get_by_id(self, message_id: int) -> Message | None:
        """Fetch a message together with attachments for API serialization."""

        stmt = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.id == message_id)
        )
        return self.db.scalar(stmt)

    def list_by_conversation_id(self, conversation_id: int) -> list[Message]:
        """Return messages in chronological order with attachments preloaded."""

        stmt = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_recent_by_conversation_id(self, conversation_id: int, limit: int = 8) -> list[Message]:
        """Return the latest messages in chronological order for context building."""

        stmt = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(self.db.scalars(stmt).all())
        messages.reverse()
        return messages
