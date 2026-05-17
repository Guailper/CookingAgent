"""LangChain-oriented context providers for one agent turn."""

from agent.contracts import AgentContextMessage, AgentTurnContext, UserMemoryContextItem
from sqlalchemy.orm import Session

from src.db.models.message import Message
from src.repositories.memory_repository import MemoryRepository
from src.repositories.message_repository import MessageRepository
from src.services.conversation_summary_service import ConversationSummaryService


class AgentContextProvider:
    """Build the complete LangChain-facing context from project storage."""

    def __init__(
        self,
        db: Session,
        *,
        message_repository: MessageRepository,
        summary_service: ConversationSummaryService,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self.db = db
        self.message_repository = message_repository
        self.summary_service = summary_service
        self.memory_repository = memory_repository or MemoryRepository(db)

    def build_turn_context(
        self,
        *,
        conversation_public_id: str,
        conversation_id: int,
        user_public_id: str,
        user_message: Message,
        attachment_public_ids: list[str] | None,
        knowledge_base_public_ids: list[str] | None,
        request_options: dict | None,
    ) -> AgentTurnContext:
        recent_messages = self.message_repository.list_recent_by_conversation_id(
            conversation_id
        )
        conversation_summary = self.summary_service.get_summary_text(conversation_id)
        user_memories = self.memory_repository.list_relevant_by_user(
            user_public_id=user_public_id,
            query=user_message.content,
        )

        return AgentTurnContext(
            conversation_public_id=conversation_public_id,
            user_public_id=user_public_id,
            trigger_message_public_id=user_message.public_id,
            user_message_text=user_message.content,
            conversation_summary=conversation_summary,
            recent_messages=[
                AgentContextMessage(role=message.role, content=message.content)
                for message in recent_messages
            ],
            user_memories=[
                UserMemoryContextItem(
                    public_id=memory.public_id,
                    memory_type=memory.memory_type,
                    content=memory.content,
                    confidence=memory.confidence,
                )
                for memory in user_memories
            ],
            attachment_public_ids=attachment_public_ids or [],
            knowledge_base_public_ids=knowledge_base_public_ids or [],
            request_options=request_options or {},
        )
