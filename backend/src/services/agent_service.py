"""Business orchestration for the LangChain-backed agent chat flow."""

from datetime import datetime
from typing import Any

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from agent.fallback import ERROR_FALLBACK_REPLY, build_fallback_result
from agent.memory.context_providers import AgentContextProvider
from agent.orchestration import AgentOrchestrator
from agent.runner import LangChainAgentRunner
from agent.workflows.memory_update_workflow import MemoryUpdateWorkflow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.cache.cache_service import CacheService
from src.core.constants import (
    AGENT_RUN_STATUS_COMPLETED,
    AGENT_RUN_STATUS_FAILED,
    AGENT_RUN_STATUS_PENDING,
    AGENT_RUN_STATUS_RUNNING,
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_STATUS_COMPLETED,
    MESSAGE_TYPE_TEXT,
)
from src.core.exceptions import AppException
from src.core.logging import get_logger
from src.core.security import generate_public_id
from src.db.models.agent_run import AgentRun
from src.db.models.message import Message
from src.db.models.user import User
from src.repositories.agent_run_repository import AgentRunRepository
from src.repositories.conversation_repository import ConversationRepository
from src.repositories.message_repository import MessageRepository
from src.services.conversation_summary_service import ConversationSummaryService
from src.services.message_service import MessageService

logger = get_logger(__name__)


class AgentService:
    """Coordinate one complete streamed agent chat round."""


    def __init__(self, db: Session) -> None:
        self.db = db
        self.message_service = MessageService(db)
        self.message_repository = MessageRepository(db)
        self.agent_run_repository = AgentRunRepository(db)
        self.conversation_repository = ConversationRepository(db)
        self.agent_runner = LangChainAgentRunner()
        self.cache = CacheService(self.agent_runner.settings)
        self.agent_orchestrator = AgentOrchestrator(db, runner=self.agent_runner)
        self.conversation_summary_service = ConversationSummaryService(
            db,
            settings=self.agent_runner.settings,
        )
        self.context_provider = AgentContextProvider(
            db,
            message_repository=self.message_repository,
            summary_service=self.conversation_summary_service,
        )


    def chat_stream(
        self,
        *,
        user: User,
        conversation_public_id: str,
        content: str,
        attachment_public_ids: list[str] | None = None,
        knowledge_base_public_ids: list[str] | None = None,
        request_options: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ):
        """Run one agent turn and yield stream events for the frontend."""

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "Conversation not found.")

        user_message = self.message_service.create_user_message(
            user=user,
            conversation_public_id=conversation_public_id,
            content=content,
            attachment_public_ids=attachment_public_ids,
            extra_metadata=extra_metadata,
        )
        yield {"event": "user_message", "data": user_message}

        context = self.context_provider.build_turn_context(
            conversation_public_id=conversation.public_id,
            conversation_id=conversation.id,
            user_public_id=user.public_id,
            user_message=user_message,
            attachment_public_ids=attachment_public_ids,
            knowledge_base_public_ids=self._resolve_knowledge_base_ids(
                knowledge_base_public_ids
            ),
            request_options=request_options,
        )

        started_at = datetime.utcnow()
        agent_run = self._create_pending_run(
            conversation_id=conversation.id,
            user_id=user.id,
            user_message=user_message,
            context=context,
        )
        yield {"event": "agent_run", "data": agent_run}

        result: AgentTurnResult | None = None
        try:
            self._mark_run_running(agent_run, started_at)
            for event in self.agent_orchestrator.stream(context):
                event_name = event.get("event")
                if event_name == "delta":
                    yield event
                    continue
                if event_name == "final":
                    event_result = event.get("data")
                    if isinstance(event_result, AgentTurnResult):
                        result = event_result

            if result is None:
                raise AppException(
                    502,
                    "AGENT_EMPTY_RESPONSE",
                    "LangChain Agent did not return a final streamed result.",
                )
            self._ensure_non_empty_agent_result(result)
        except AppException as exc:
            self.db.rollback()
            logger.warning(
                "Streamed LangChain agent failed and will use local fallback.",
                extra={
                    "conversation_public_id": conversation.public_id,
                    "trigger_message_public_id": user_message.public_id,
                    "agent_run_public_id": agent_run.public_id,
                    "error_code": exc.code,
                    "error_message": exc.message,
                    "model_provider": self.agent_runner.settings.agent_model_provider,
                    "model_name": self.agent_runner.resolve_model_name(),
                },
            )
            user_message, assistant_message, refreshed_agent_run = self._persist_fallback_round(
                conversation_id=conversation.id,
                user_message=user_message,
                agent_run_id=agent_run.id,
                context=context,
                started_at=started_at,
                error_code=exc.code,
                error_message=exc.message,
                error_detail=exc.detail,
            )
            yield {"event": "delta", "data": {"content": assistant_message.content}}
            yield {
                "event": "done",
                "data": {
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "agent_run": refreshed_agent_run,
                },
            }
            return
        except IntegrityError as exc:
            self.db.rollback()
            logger.exception("Agent persistence failed before fallback could complete.", exc_info=exc)
            user_message, assistant_message, refreshed_agent_run = self._persist_hard_failure_round(
                conversation_id=conversation.id,
                user_message=user_message,
                agent_run_id=agent_run.id,
                started_at=started_at,
                error_code="AGENT_PERSIST_CONFLICT",
                error_message="Agent persistence conflict.",
            )
            yield {"event": "delta", "data": {"content": assistant_message.content}}
            yield {
                "event": "done",
                "data": {
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "agent_run": refreshed_agent_run,
                },
            }
            return
        except Exception as exc:
            self.db.rollback()
            logger.exception("Unexpected streamed agent runtime failure before fallback.", exc_info=exc)
            user_message, assistant_message, refreshed_agent_run = self._persist_fallback_round(
                conversation_id=conversation.id,
                user_message=user_message,
                agent_run_id=agent_run.id,
                context=context,
                started_at=started_at,
                error_code="AGENT_RUNTIME_FAILED",
                error_message=str(exc),
            )
            yield {"event": "delta", "data": {"content": assistant_message.content}}
            yield {
                "event": "done",
                "data": {
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "agent_run": refreshed_agent_run,
                },
            }
            return

        assistant_message = self._persist_success_round(
            conversation_id=conversation.id,
            agent_run=agent_run,
            result=result,
        )
        self._try_update_conversation_summary(conversation_id=conversation.id)
        self._try_update_memory_after_answer(context=context, result=result)
        refreshed_agent_run = self.agent_run_repository.get_by_id(agent_run.id)
        if refreshed_agent_run is None:
            raise AppException(500, "AGENT_RESULT_LOAD_FAILED", "Agent result saved but could not be loaded.")

        yield {
            "event": "done",
            "data": {
                "user_message": user_message,
                "assistant_message": assistant_message,
                "agent_run": refreshed_agent_run,
            },
        }

    def _try_update_memory_after_answer(
        self,
        *,
        context: AgentTurnContext,
        result: AgentTurnResult,
    ) -> None:
        """Update memory as a non-critical side effect after an answer."""



        if result.intent_type != "answer":
            return

        try:
            MemoryUpdateWorkflow(self.db).run(
                context,
                ActionIntent(
                    intent_type="memory_update",
                    confidence=0.5,
                    source="answer_side_effect",
                    reason="Update long-term memory after a successful answer.",
                ),
            )
        except Exception as exc:
            self.db.rollback()
            logger.warning("Memory side-effect update failed.", exc_info=exc)

    def _try_update_conversation_summary(self, *, conversation_id: int) -> None:
        """Update rolling summary as a non-critical side effect after a successful answer."""

        try:
            conversation = self.conversation_repository.get_by_id(conversation_id)
            if conversation is None:
                return
            self.conversation_summary_service.update_after_answer(conversation)
        except Exception as exc:
            self.db.rollback()
            logger.warning("Conversation summary side-effect update failed.", exc_info=exc)

    def _resolve_knowledge_base_ids(
        self,
        knowledge_base_public_ids: list[str] | None,
    ) -> list[str]:
        """Merge explicit knowledge bases with default knowledge bases."""


        merged_ids: list[str] = []
        for public_id in [
            *(knowledge_base_public_ids or []),
            *self.agent_runner.settings.rag_default_knowledge_base_ids,
        ]:
            normalized_id = (public_id or "").strip()
            if normalized_id and normalized_id not in merged_ids:
                merged_ids.append(normalized_id)

        return merged_ids

    @staticmethod
    def _ensure_non_empty_agent_result(result: AgentTurnResult) -> None:
        """Reject empty assistant replies before persistence."""

        if not (result.reply_text or "").strip():
            raise AppException(
                502,
                "AGENT_EMPTY_RESPONSE",
                "Agent returned an empty response.",
            )

    def _create_pending_run(
        self,
        *,
        conversation_id: int,
        user_id: int,
        user_message: Message,
        context: AgentTurnContext,
    ) -> AgentRun:
        """Create a pending agent_run before calling LangChain."""

        agent_run = AgentRun(
            public_id=generate_public_id("run"),
            conversation_id=conversation_id,
            message_id=user_message.id,
            user_id=user_id,
            intent_type="langchain_agent",
            workflow_name="langchain_tool_calling_agent",
            run_status=AGENT_RUN_STATUS_PENDING,
            model_name=self.agent_runner.resolve_model_name(),
            input_snapshot=self._build_input_snapshot(context),
        )
        self.agent_run_repository.create(agent_run)
        self.db.commit()
        return agent_run

    def _mark_run_running(self, agent_run: AgentRun, started_at: datetime) -> None:
        """Mark the run as running before LangChain execution starts."""

        agent_run.run_status = AGENT_RUN_STATUS_RUNNING
        agent_run.started_at = started_at
        self.db.commit()

    def _persist_success_round(
        self,
        *,
        conversation_id: int,
        agent_run: AgentRun,
        result: AgentTurnResult,
    ) -> Message:
        """Persist the assistant reply and mark the run as completed."""

        self._ensure_non_empty_agent_result(result)
        conversation = self.conversation_repository.get_by_id(conversation_id)
        if conversation is None:
            raise AppException(500, "CONVERSATION_LOAD_FAILED", "Conversation could not be loaded after the agent reply.")

        assistant_message = Message(
            public_id=generate_public_id("msg"),
            conversation_id=conversation.id,
            user_id=None,
            role=MESSAGE_ROLE_ASSISTANT,
            message_type=MESSAGE_TYPE_TEXT,
            content=result.reply_text,
            status=MESSAGE_STATUS_COMPLETED,
            extra_metadata=self._build_assistant_metadata(result),
        )
        self.message_repository.create(assistant_message)

        agent_run.run_status = AGENT_RUN_STATUS_COMPLETED
        agent_run.intent_type = result.intent_type
        agent_run.workflow_name = result.workflow_name
        agent_run.model_name = result.model_name
        agent_run.output_snapshot = self._build_output_snapshot(result)
        agent_run.completed_at = datetime.utcnow()
        conversation.latest_message_at = datetime.utcnow()
        self.db.commit()
        self._invalidate_conversation_cache(conversation.public_id, conversation.user_id)

        refreshed_assistant_message = self.message_repository.get_by_id(assistant_message.id)
        if refreshed_assistant_message is None:
            raise AppException(500, "ASSISTANT_MESSAGE_LOAD_FAILED", "Assistant message saved but could not be loaded.")

        return refreshed_assistant_message

    def _persist_fallback_round(
        self,
        *,
        conversation_id: int,
        user_message: Message,
        agent_run_id: int,
        context: AgentTurnContext,
        started_at: datetime,
        error_code: str,
        error_message: str,
        error_detail: Any | None = None,
    ) -> tuple[Message, Message, AgentRun]:
        """Persist a local fallback result after LangChain fails."""

        fallback_result = build_fallback_result(
            context,
            model_name=self.agent_runner.resolve_model_name(),
            failure_code=error_code,
            failure_message=error_message,
        )
        degraded_agent_run = self.agent_run_repository.get_by_id(agent_run_id)
        if degraded_agent_run is None:
            raise AppException(500, "AGENT_RUN_LOAD_FAILED", "Agent run could not be loaded for fallback.")

        degraded_agent_run.error_code = error_code
        degraded_agent_run.error_message = error_message
        degraded_agent_run.started_at = degraded_agent_run.started_at or started_at

        assistant_message = self._persist_success_round(
            conversation_id=conversation_id,
            agent_run=degraded_agent_run,
            result=fallback_result,
        )

        degraded_agent_run = self.agent_run_repository.get_by_id(agent_run_id)
        if degraded_agent_run is None:
            raise AppException(500, "AGENT_RUN_LOAD_FAILED", "Agent run could not be loaded after fallback.")

        degraded_agent_run.error_code = error_code
        degraded_agent_run.error_message = error_message
        degraded_agent_run.output_snapshot = self._build_output_snapshot(fallback_result)
        degraded_agent_run.output_snapshot["degraded"] = True
        degraded_agent_run.output_snapshot["primary_failure_code"] = error_code
        degraded_agent_run.output_snapshot["primary_failure_message"] = error_message
        if isinstance(error_detail, dict):
            model_attempts = error_detail.get("model_fallback_attempts")
            if isinstance(model_attempts, list):
                degraded_agent_run.output_snapshot["model_fallback"] = {
                    "all_failed": True,
                    "attempts": model_attempts,
                }
        degraded_agent_run.completed_at = datetime.utcnow()
        self.db.commit()

        refreshed_run = self.agent_run_repository.get_by_id(degraded_agent_run.id)
        if refreshed_run is None:
            raise AppException(500, "AGENT_FAILURE_RESULT_LOAD_FAILED", "Fallback result could not be loaded.")

        return user_message, assistant_message, refreshed_run

    def _persist_hard_failure_round(
        self,
        *,
        conversation_id: int,
        user_message: Message,
        agent_run_id: int,
        started_at: datetime,
        error_code: str,
        error_message: str,
    ) -> tuple[Message, Message, AgentRun]:
        """Persist the final hard-failure result when fallback also fails."""

        conversation = self.conversation_repository.get_by_id(conversation_id)
        failed_run = self.agent_run_repository.get_by_id(agent_run_id)
        if conversation is None or failed_run is None:
            raise AppException(500, "AGENT_RUN_LOAD_FAILED", "Agent run could not be loaded after failure.")

        failed_run.run_status = AGENT_RUN_STATUS_FAILED
        failed_run.started_at = failed_run.started_at or started_at
        failed_run.completed_at = datetime.utcnow()
        failed_run.error_code = error_code
        failed_run.error_message = error_message
        failed_run.output_snapshot = {
            "reply_type": "fallback_text",
            "degraded": False,
            "error_code": error_code,
        }

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
                "intent_type": failed_run.intent_type,
                "workflow_name": failed_run.workflow_name,
                "degraded": False,
                "error_code": error_code,
            },
        )
        self.message_repository.create(assistant_message)
        conversation.latest_message_at = datetime.utcnow()
        self.db.commit()
        self._invalidate_conversation_cache(conversation.public_id, conversation.user_id)

        refreshed_assistant_message = self.message_repository.get_by_id(assistant_message.id)
        refreshed_failed_run = self.agent_run_repository.get_by_id(failed_run.id)
        if refreshed_assistant_message is None or refreshed_failed_run is None:
            raise AppException(500, "AGENT_FAILURE_RESULT_LOAD_FAILED", "Hard failure result could not be loaded.")

        return user_message, refreshed_assistant_message, refreshed_failed_run

    @staticmethod
    def _build_input_snapshot(context: AgentTurnContext) -> dict[str, Any]:
        """Build a debug-friendly input snapshot for agent_run."""

        return {
            "conversation_public_id": context.conversation_public_id,
            "user_public_id": context.user_public_id,
            "trigger_message_public_id": context.trigger_message_public_id,
            "user_message_text": context.user_message_text,
            "attachment_public_ids": context.attachment_public_ids,
            "knowledge_base_public_ids": context.knowledge_base_public_ids,
            "request_options": context.request_options,
            "conversation_summary": context.conversation_summary,
            "user_memories": [
                {
                    "public_id": memory.public_id,
                    "memory_type": memory.memory_type,
                    "content": memory.content,
                    "confidence": memory.confidence,
                }
                for memory in context.user_memories
            ],
            "attachment_context_count": len(context.attachment_context),
            "recent_messages": [
                {"role": message.role, "content": message.content}
                for message in context.recent_messages
            ],
        }

    @staticmethod
    def _build_output_snapshot(result: AgentTurnResult) -> dict[str, Any]:
        """Normalize the result into the output_snapshot structure."""

        output_snapshot = dict(result.output_snapshot or {})
        output_snapshot.setdefault("reply_type", "agent_text")
        output_snapshot["reply_text"] = result.reply_text
        output_snapshot["intent_type"] = result.intent_type
        output_snapshot["workflow_name"] = result.workflow_name
        return output_snapshot

    @staticmethod
    def _build_assistant_metadata(result: AgentTurnResult) -> dict[str, Any]:
        """Keep assistant message metadata aligned with agent_run output."""

        output_snapshot = dict(result.output_snapshot or {})
        return {
            "reply_type": output_snapshot.get("reply_type", "agent_text"),
            "intent_type": result.intent_type,
            "workflow_name": result.workflow_name,
            "model_name": result.model_name,
            "degraded": output_snapshot.get("degraded", False),
            "provider": output_snapshot.get("provider"),
            "primary_failure_code": output_snapshot.get("primary_failure_code"),
        }

    def _invalidate_conversation_cache(self, conversation_public_id: str, user_id: int) -> None:
        self.cache.delete(
            self.cache.build_key("messages", "conversation", conversation_public_id),
            self.cache.build_key("conversations", "user", user_id),
        )

