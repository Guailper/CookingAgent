"""Business logic for creating and listing conversation messages."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.constants import (
    INPUT_SOURCE_KEYBOARD,
    MESSAGE_ROLE_USER,
    MESSAGE_STATUS_COMPLETED,
    MESSAGE_TYPE_TEXT,
)
from src.core.exceptions import AppException
from src.core.security import generate_public_id
from src.db.models.message import Message
from src.db.models.user import User
from src.repositories.attachment_repository import AttachmentRepository
from src.repositories.conversation_repository import ConversationRepository
from src.repositories.message_repository import MessageRepository


class MessageService:
    """Handle message creation, attachment binding, and message listing."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.message_repository = MessageRepository(db)
        self.attachment_repository = AttachmentRepository(db)
        self.conversation_repository = ConversationRepository(db)

    def create_user_message(
        self,
        *,
        user: User,
        conversation_public_id: str,
        content: str,
        attachment_public_ids: Iterable[str] | None = None,
        extra_metadata: Mapping[str, Any] | None = None,
    ) -> Message:
        """Create a text user message and bind any uploaded attachments atomically."""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")

        normalized_content = content.strip()
        normalized_attachment_ids = self._normalize_attachment_ids(attachment_public_ids)
        normalized_extra_metadata = self._normalize_user_message_metadata(extra_metadata)

        if not normalized_content and not normalized_attachment_ids:
            raise AppException(400, "EMPTY_MESSAGE_CONTENT", "消息内容和附件不能同时为空。")

        message = Message(
            public_id=generate_public_id("msg"),
            conversation_id=conversation.id,
            user_id=user.id,
            role=MESSAGE_ROLE_USER,
            message_type=MESSAGE_TYPE_TEXT,
            content=normalized_content,
            status=MESSAGE_STATUS_COMPLETED,
            extra_metadata=normalized_extra_metadata,
        )

        conversation.latest_message_at = datetime.utcnow()

        try:
            self.message_repository.create(message)
            self._bind_attachments(
                conversation_id=conversation.id,
                message_id=message.id,
                attachment_public_ids=normalized_attachment_ids,
            )
            self.db.commit()
        except AppException:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise AppException(409, "MESSAGE_CREATE_CONFLICT", "消息创建时发生冲突。") from exc

        bound_message = self.message_repository.get_by_id(message.id)
        if bound_message is None:
            raise AppException(500, "MESSAGE_LOAD_FAILED", "消息创建成功，但回读消息失败。")

        return bound_message

    def list_conversation_messages(self, user: User, conversation_public_id: str) -> list[Message]:
        """Return all messages in a conversation owned by the current user."""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")

        return self.message_repository.list_by_conversation_id(conversation.id)

    def _bind_attachments(
        self,
        *,
        conversation_id: int,
        message_id: int,
        attachment_public_ids: list[str],
    ) -> None:
        """Bind uploaded attachments to the newly created message."""

        if not attachment_public_ids:
            return

        attachments = self.attachment_repository.list_by_public_ids_and_conversation_id(
            attachment_public_ids,
            conversation_id,
        )
        attachments_by_id = {attachment.public_id: attachment for attachment in attachments}

        missing_ids = [attachment_id for attachment_id in attachment_public_ids if attachment_id not in attachments_by_id]
        if missing_ids:
            raise AppException(
                404,
                "ATTACHMENT_NOT_FOUND",
                f"以下附件不存在或不属于当前会话：{', '.join(missing_ids)}",
            )

        for attachment_id in attachment_public_ids:
            attachment = attachments_by_id[attachment_id]
            if attachment.message_id is not None and attachment.message_id != message_id:
                raise AppException(
                    409,
                    "ATTACHMENT_ALREADY_BOUND",
                    f"附件 {attachment.public_id} 已经绑定到其他消息。",
                )

            attachment.message_id = message_id

    @staticmethod
    def _normalize_user_message_metadata(
        extra_metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Keep message metadata dict-shaped and default text input to keyboard."""

        if extra_metadata is None:
            return {"input_source": INPUT_SOURCE_KEYBOARD}

        normalized_metadata = {
            key: value for key, value in extra_metadata.items() if value is not None
        }
        if not normalized_metadata:
            return {"input_source": INPUT_SOURCE_KEYBOARD}

        normalized_metadata.setdefault("input_source", INPUT_SOURCE_KEYBOARD)
        return normalized_metadata

    def _normalize_attachment_ids(self, attachment_public_ids: Iterable[str] | None) -> list[str]:
        """Preserve input order while removing duplicates and empty values."""

        if attachment_public_ids is None:
            return []

        normalized_ids: list[str] = []
        seen: set[str] = set()
        for public_id in attachment_public_ids:
            candidate = public_id.strip()
            if not candidate or candidate in seen:
                continue
            normalized_ids.append(candidate)
            seen.add(candidate)

        return normalized_ids
