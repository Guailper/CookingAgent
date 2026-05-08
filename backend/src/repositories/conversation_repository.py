"""Data access helpers for the conversations table."""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.db.models.conversation import Conversation


class ConversationRepository:
    """Encapsulate common conversation reads and writes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, conversation: Conversation) -> Conversation:
        """Add a conversation to the current transaction."""

        self.db.add(conversation)
        self.db.flush()
        return conversation

    def get_by_id(self, conversation_id: int) -> Conversation | None:
        """Fetch a conversation by its internal primary key."""

        return self.db.get(Conversation, conversation_id)

    def list_by_user_id(self, user_id: int) -> list[Conversation]:
        """Return the current user's conversations ordered by recent activity."""

        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.latest_message_at), desc(Conversation.created_at))
        )
        return list(self.db.scalars(stmt).all())

    def get_by_public_id_and_user_id(self, public_id: str, user_id: int) -> Conversation | None:
        """Fetch a conversation only when it belongs to the given user."""

        stmt = select(Conversation).where(
            Conversation.public_id == public_id,
            Conversation.user_id == user_id,
        )
        return self.db.scalar(stmt)
