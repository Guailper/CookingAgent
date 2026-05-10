"""Conversation business service."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.cache.cache_service import CacheService
from src.core.config import get_settings
from src.core.constants import CONVERSATION_STATUS_ACTIVE, DEFAULT_CONVERSATION_TITLE
from src.core.exceptions import AppException
from src.core.security import generate_public_id
from src.db.models.conversation import Conversation
from src.db.models.user import User
from src.repositories.conversation_repository import ConversationRepository
from src.schemas.conversation import ConversationItem


class ConversationService:
    """Handle conversation creation, list queries, and detail queries."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.cache = CacheService(self.settings)
        self.conversation_repository = ConversationRepository(db)

    def create_conversation(self, user: User, title: str) -> Conversation:
        """Create a new conversation."""

        normalized_title = title.strip() or DEFAULT_CONVERSATION_TITLE
        conversation = Conversation(
            public_id=generate_public_id("conv"),
            user_id=user.id,
            title=normalized_title,
            status=CONVERSATION_STATUS_ACTIVE,
        )

        try:
            self.conversation_repository.create(conversation)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppException(409, "CONVERSATION_CREATE_CONFLICT", "会话创建发生冲突。") from exc

        self.db.refresh(conversation)
        self.cache.delete(self._conversation_list_key(user.id))
        return conversation

    def list_conversations(self, user: User) -> list[Conversation] | list[dict]:
        """Return current user's conversations ordered by recent activity."""

        cache_key = self._conversation_list_key(user.id)
        cached_items = self.cache.get_json(cache_key)
        if isinstance(cached_items, list):
            return cached_items

        conversations = self.conversation_repository.list_by_user_id(user.id)
        self.cache.set_json(
            cache_key,
            [ConversationItem.model_validate(item).model_dump(mode="json") for item in conversations],
            self.settings.conversation_cache_ttl_seconds,
        )
        return conversations

    def get_conversation(self, user: User, conversation_public_id: str) -> Conversation:
        """Return a conversation only when it belongs to the current user."""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")
        return conversation

    def _conversation_list_key(self, user_id: int) -> str:
        return self.cache.build_key("conversations", "user", user_id)
