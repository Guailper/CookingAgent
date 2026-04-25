"""Business orchestration for the MVP agent chat flow."""

from datetime import datetime
from typing import Any

from agent.context_builder import build_agent_context
from agent.orchestrator import AgentOrchestrator
from agent.prompts import ERROR_FALLBACK_REPLY
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.constants import (
    AGENT_RUN_STATUS_COMPLETED,
    AGENT_RUN_STATUS_FAILED,
    AGENT_RUN_STATUS_RUNNING,
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_STATUS_COMPLETED,
    MESSAGE_TYPE_TEXT,
)
from src.core.exceptions import AppException
from src.core.security import generate_public_id
from src.db.models.agent_run import AgentRun
from src.db.models.message import Message
from src.db.models.user import User
from src.repositories.agent_run_repository import AgentRunRepository
from src.repositories.conversation_repository import ConversationRepository
from src.repositories.message_repository import MessageRepository
from src.services.message_service import MessageService


class AgentService:
    """Create a user message, run the MVP agent, then persist the assistant reply."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.message_service = MessageService(db)
        self.message_repository = MessageRepository(db)
        self.agent_run_repository = AgentRunRepository(db)
        self.conversation_repository = ConversationRepository(db)
        self.orchestrator = AgentOrchestrator()

    def chat(
        self,
        *,
        user: User,
        conversation_public_id: str,
        content: str,
        attachment_public_ids: list[str] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> tuple[Message, Message, AgentRun]:
        """Run one complete MVP agent turn and return persisted ORM objects."""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")

        user_message = self.message_service.create_user_message(
            user=user,
            conversation_public_id=conversation_public_id,
            content=content,
            attachment_public_ids=attachment_public_ids,
            extra_metadata=extra_metadata,
        )

        recent_messages = self.message_repository.list_recent_by_conversation_id(conversation.id)
        context = build_agent_context(
            conversation_public_id=conversation.public_id,
            user_public_id=user.public_id,
            trigger_message_public_id=user_message.public_id,
            user_message_text=user_message.content,
            recent_messages=recent_messages,
        )

        started_at = datetime.utcnow()
        try:
            result = self.orchestrator.run(context)
            agent_run = AgentRun(
                public_id=generate_public_id("run"),
                conversation_id=conversation.id,
                message_id=user_message.id,
                user_id=user.id,
                intent_type=result.intent_type,
                workflow_name=result.workflow_name,
                run_status=AGENT_RUN_STATUS_RUNNING,
                model_name=result.model_name,
                input_snapshot=self._build_input_snapshot(context),
                started_at=started_at,
            )
            self.agent_run_repository.create(agent_run)

            assistant_message = Message(
                public_id=generate_public_id("msg"),
                conversation_id=conversation.id,
                user_id=None,
                role=MESSAGE_ROLE_ASSISTANT,
                message_type=MESSAGE_TYPE_TEXT,
                content=result.reply_text,
                status=MESSAGE_STATUS_COMPLETED,
                extra_metadata={
                    "reply_type": "agent_text",
                    "intent_type": result.intent_type,
                    "workflow_name": result.workflow_name,
                },
            )
            self.message_repository.create(assistant_message)

            agent_run.run_status = AGENT_RUN_STATUS_COMPLETED
            agent_run.output_snapshot = result.output_snapshot or {"reply_type": "text"}
            agent_run.completed_at = datetime.utcnow()
            conversation.latest_message_at = datetime.utcnow()
            self.db.commit()
        except AppException as exc:
            self.db.rollback()
            return self._persist_failure_round(
                user=user,
                conversation_id=conversation.id,
                user_message=user_message,
                started_at=started_at,
                error_code=exc.code,
                error_message=exc.message,
            )
        except IntegrityError as exc:
            self.db.rollback()
            return self._persist_failure_round(
                user=user,
                conversation_id=conversation.id,
                user_message=user_message,
                started_at=started_at,
                error_code="AGENT_PERSIST_CONFLICT",
                error_message="智能体回复落库时发生冲突。",
            )
        except Exception as exc:
            self.db.rollback()
            return self._persist_failure_round(
                user=user,
                conversation_id=conversation.id,
                user_message=user_message,
                started_at=started_at,
                error_code="AGENT_RUNTIME_FAILED",
                error_message=str(exc),
            )

        assistant_message = self.message_repository.get_by_id(assistant_message.id)
        refreshed_agent_run = self.agent_run_repository.get_by_id(agent_run.id)
        if assistant_message is None or refreshed_agent_run is None:
            raise AppException(500, "AGENT_RESULT_LOAD_FAILED", "智能体回复成功，但结果回读失败。")

        return user_message, assistant_message, refreshed_agent_run

    def _persist_failure_round(
        self,
        *,
        user: User,
        conversation_id: int,
        user_message: Message,
        started_at: datetime,
        error_code: str,
        error_message: str,
    ) -> tuple[Message, Message, AgentRun]:
        """Persist a failed run and a fallback assistant message for user continuity."""

        conversation = self.conversation_repository.get_by_id(conversation_id)
        if conversation is None:
            raise AppException(500, "CONVERSATION_LOAD_FAILED", "智能体失败后无法回读会话。")

        failed_run = AgentRun(
            public_id=generate_public_id("run"),
            conversation_id=conversation.id,
            message_id=user_message.id,
            user_id=user.id,
            intent_type="simple_chat",
            workflow_name="simple_chat_workflow",
            run_status=AGENT_RUN_STATUS_FAILED,
            model_name=None,
            input_snapshot={
                "trigger_message_public_id": user_message.public_id,
                "user_message_text": user_message.content,
            },
            output_snapshot={"reply_type": "fallback_text"},
            error_code=error_code,
            error_message=error_message,
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )
        self.agent_run_repository.create(failed_run)

        assistant_message = Message(
            public_id=generate_public_id("msg"),
            conversation_id=conversation.id,
            user_id=None,
            role=MESSAGE_ROLE_ASSISTANT,
            message_type=MESSAGE_TYPE_TEXT,
            content=ERROR_FALLBACK_REPLY,
            status=MESSAGE_STATUS_COMPLETED,
            extra_metadata={
                "reply_type": "fallback_text",
                "intent_type": "simple_chat",
                "workflow_name": "simple_chat_workflow",
            },
        )
        self.message_repository.create(assistant_message)
        conversation.latest_message_at = datetime.utcnow()
        self.db.commit()

        refreshed_assistant_message = self.message_repository.get_by_id(assistant_message.id)
        refreshed_failed_run = self.agent_run_repository.get_by_id(failed_run.id)
        if refreshed_assistant_message is None or refreshed_failed_run is None:
            raise AppException(500, "AGENT_FAILURE_RESULT_LOAD_FAILED", "智能体失败兜底结果回读失败。")

        return user_message, refreshed_assistant_message, refreshed_failed_run

    @staticmethod
    def _build_input_snapshot(context: Any) -> dict[str, Any]:
        """Keep a small, debuggable input snapshot for the agent run record."""

        return {
            "conversation_public_id": context.conversation_public_id,
            "user_public_id": context.user_public_id,
            "trigger_message_public_id": context.trigger_message_public_id,
            "user_message_text": context.user_message_text,
            "recent_messages": [
                {"role": message.role, "content": message.content}
                for message in context.recent_messages
            ],
        }
