"""Model-based rolling conversation summaries."""

from typing import Any

from agent.factories.model_factory import build_chat_model
from agent.prompts.system_prompts import (
    build_conversation_summary_system_prompt,
    build_conversation_summary_user_prompt,
)
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.config import AgentModelCandidate, Settings, get_settings
from src.core.constants import MESSAGE_ROLE_ASSISTANT, MESSAGE_ROLE_SYSTEM, MESSAGE_ROLE_USER
from src.core.logging import get_logger
from src.db.models.conversation import Conversation
from src.db.models.conversation_summary import ConversationSummary
from src.db.models.message import Message
from src.repositories.conversation_summary_repository import ConversationSummaryRepository
from src.repositories.message_repository import MessageRepository
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class ConversationSummaryService:
    """Maintain a compact model-generated summary for long conversations."""

    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.summary_repository = ConversationSummaryRepository(db)
        self.message_repository = MessageRepository(db)

    def get_summary_text(self, conversation_id: int) -> str | None:
        summary = self.summary_repository.get_by_conversation_id(conversation_id)
        if summary is None:
            return None

        text = (summary.summary_text or "").strip()
        return text or None

    def update_after_answer(self, conversation: Conversation) -> ConversationSummary | None:
        """Update the rolling summary when enough unsummarized messages have accumulated."""

        messages = self.message_repository.list_by_conversation_id(conversation.id)
        if not self._should_update(conversation.id, messages):
            return self.summary_repository.get_by_conversation_id(conversation.id)

        existing_summary = self.summary_repository.get_by_conversation_id(conversation.id)
        unsummarized_messages = self._select_unsummarized_messages(existing_summary, messages)
        if not unsummarized_messages:
            return existing_summary

        summary_text = self._generate_summary(
            existing_summary_text=existing_summary.summary_text if existing_summary else "",
            messages=unsummarized_messages,
        )
        if not summary_text:
            return existing_summary

        latest_message = unsummarized_messages[-1]
        if existing_summary is None:
            existing_summary = ConversationSummary(
                conversation_id=conversation.id,
                conversation_public_id=conversation.public_id,
                summary_text=summary_text,
                covered_until_message_public_id=latest_message.public_id,
                source_message_count=len(messages),
                model_name=self._resolve_model_name(),
            )
            self.summary_repository.create(existing_summary)
        else:
            existing_summary.summary_text = summary_text
            existing_summary.covered_until_message_public_id = latest_message.public_id
            existing_summary.source_message_count = len(messages)
            existing_summary.model_name = self._resolve_model_name()

        self.db.commit()
        return existing_summary

    def _should_update(self, conversation_id: int, messages: list[Message]) -> bool:
        if len(messages) < self._trigger_message_count:
            return False

        existing_summary = self.summary_repository.get_by_conversation_id(conversation_id)
        if existing_summary is None:
            return True

        unsummarized_count = len(self._select_unsummarized_messages(existing_summary, messages))
        return unsummarized_count >= self._batch_message_count

    def _select_unsummarized_messages(
        self,
        existing_summary: ConversationSummary | None,
        messages: list[Message],
    ) -> list[Message]:
        if existing_summary is None or not existing_summary.covered_until_message_public_id:
            return messages

        for index, message in enumerate(messages):
            if message.public_id == existing_summary.covered_until_message_public_id:
                return messages[index + 1 :]

        # 如果游标对应的消息被清理，退回到最近一批消息，避免把整段长会话再次发给模型。
        return messages[-self._batch_message_count :]

    def _generate_summary(
        self,
        *,
        existing_summary_text: str,
        messages: list[Message],
    ) -> str:
        try:
            model = build_chat_model(self.settings, self._resolve_model_candidate())
            response = model.invoke(
                [
                    SystemMessage(content=build_conversation_summary_system_prompt()),
                    HumanMessage(
                        content=build_conversation_summary_user_prompt(
                            existing_summary_text=existing_summary_text,
                            rendered_messages=self._render_messages(messages),
                        )
                    ),
                ]
            )
        except Exception as exc:
            logger.warning("Conversation summary update failed.", exc_info=exc)
            return ""

        return self._normalize_summary_text(getattr(response, "content", response))

    def _resolve_model_candidate(self) -> AgentModelCandidate | None:
        candidates = getattr(self.settings, "agent_model_candidates", None)
        if candidates:
            return candidates[0]
        return None

    def _resolve_model_name(self) -> str | None:
        candidate = self._resolve_model_candidate()
        if candidate is not None:
            return candidate.model_name
        return self.settings.agent_model_name or None

    def _render_messages(self, messages: list[Message]) -> str:
        return "\n\n".join(self._render_message(message) for message in messages)

    @staticmethod
    def _render_message(message: Message) -> str:
        role_label = {
            MESSAGE_ROLE_USER: "用户",
            MESSAGE_ROLE_ASSISTANT: "助手",
            MESSAGE_ROLE_SYSTEM: "系统",
        }.get(message.role, message.role or "未知")
        content = " ".join((message.content or "").split())
        return f"[{role_label}] {content}"

    def _normalize_summary_text(self, content: Any) -> str:
        text = self._content_to_text(content)
        if not text:
            return ""

        max_chars = max(200, self._max_summary_chars)
        return text[:max_chars].strip()

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            return "\n".join(parts).strip()

        return str(content).strip() if content is not None else ""

    @property
    def _trigger_message_count(self) -> int:
        return max(2, int(getattr(self.settings, "agent_summary_trigger_messages", 12)))

    @property
    def _batch_message_count(self) -> int:
        return max(1, int(getattr(self.settings, "agent_summary_batch_messages", 8)))

    @property
    def _max_summary_chars(self) -> int:
        return max(200, int(getattr(self.settings, "agent_summary_max_chars", 1200)))
