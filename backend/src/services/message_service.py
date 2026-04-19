"""消息业务服务。"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.constants import MESSAGE_ROLE_USER, MESSAGE_STATUS_COMPLETED
from src.core.exceptions import AppException
from src.core.security import generate_public_id
from src.db.models.message import Message
from src.db.models.user import User
from src.repositories.conversation_repository import ConversationRepository
from src.repositories.message_repository import MessageRepository


class MessageService:
    """处理消息创建和消息列表查询。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.message_repository = MessageRepository(db)
        self.conversation_repository = ConversationRepository(db)

    def create_user_message(
        self,
        user: User,
        conversation_public_id: str,
        content: str,
        message_type: str,
    ) -> Message:
        """向指定会话写入一条用户消息。"""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")

        normalized_content = content.strip()
        if not normalized_content:
            raise AppException(400, "EMPTY_MESSAGE_CONTENT", "消息内容不能为空。")

        message = Message(
            public_id=generate_public_id("msg"),
            conversation_id=conversation.id,
            user_id=user.id,
            role=MESSAGE_ROLE_USER,
            message_type=message_type,
            content=normalized_content,
            status=MESSAGE_STATUS_COMPLETED,
        )

        conversation.latest_message_at = datetime.utcnow()

        try:
            self.message_repository.create(message)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppException(409, "MESSAGE_CREATE_CONFLICT", "消息创建发生冲突。") from exc

        self.db.refresh(message)
        return message

    def list_conversation_messages(self, user: User, conversation_public_id: str) -> list[Message]:
        """返回当前用户指定会话的消息列表。"""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")

        return self.message_repository.list_by_conversation_id(conversation.id)
