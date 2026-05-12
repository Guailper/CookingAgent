"""Data access helpers for conversation summaries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.conversation_summary import ConversationSummary


class ConversationSummaryRepository:
    """Encapsulate rolling summary reads and writes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_conversation_id(self, conversation_id: int) -> ConversationSummary | None:
        stmt = select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
        return self.db.scalar(stmt)

    def create(self, summary: ConversationSummary) -> ConversationSummary:
        self.db.add(summary)
        self.db.flush()
        return summary
