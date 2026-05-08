"""会话业务服务。"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.constants import CONVERSATION_STATUS_ACTIVE, DEFAULT_CONVERSATION_TITLE
from src.core.exceptions import AppException
from src.core.security import generate_public_id
from src.db.models.conversation import Conversation
from src.db.models.user import User
from src.repositories.conversation_repository import ConversationRepository


class ConversationService:
    """处理会话创建、列表查询和详情查询。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversation_repository = ConversationRepository(db)

    def create_conversation(self, user: User, title: str) -> Conversation:
        """创建一个新会话。"""

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
        return conversation

    def list_conversations(self, user: User) -> list[Conversation]:
        """返回当前用户的会话列表。"""

        return self.conversation_repository.list_by_user_id(user.id)

    def get_conversation(self, user: User, conversation_public_id: str) -> Conversation:
        """返回当前用户的指定会话。"""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")
        return conversation
