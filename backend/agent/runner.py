"""LangChain agent runtime wrapper."""

from dataclasses import replace
from typing import Any

from agent.contracts import AgentTurnContext, AgentTurnResult
from agent.factories.model_factory import build_chat_model
from agent.factories.tool_factory import build_tools
from agent.memory.message_history import build_langchain_messages
from agent.output.normalizer import (
    build_agent_result,
    build_streamed_agent_result,
    count_stream_tool_calls,
    extract_stream_delta,
)
from agent.prompts.system_prompts import build_system_prompt
from src.core.config import AgentModelCandidate, Settings, get_settings
from src.core.exceptions import AppException
from src.core.logging import get_logger

logger = get_logger(__name__)


class LangChainAgentRunner:
    """Run one CookingAgent turn through LangChain's agent runtime."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def resolve_model_name(self) -> str | None:
        """Return the configured model name for agent_run tracing."""

        return self.settings.agent_model_name or None

    def run(self, context: AgentTurnContext) -> AgentTurnResult:
        """Invoke the LangChain agent and normalize its response."""

        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise AppException(
                500,
                "AGENT_LANGCHAIN_NOT_INSTALLED",
                "Missing langchain dependency. Install backend/requirements.txt first.",
            ) from exc

        tools = build_tools(context, self.settings)
        messages = build_langchain_messages(
            context,
            max_history_messages=self.settings.agent_max_context_messages,
        )
        system_prompt = build_system_prompt(context)
        model_candidates = self._resolve_model_candidates()
        if not model_candidates:
            raise AppException(
                503,
                "AGENT_MODEL_NOT_CONFIGURED",
                "No configured agent model candidate is available.",
            )

        failed_attempts: list[dict[str, Any]] = []
        for priority, candidate in enumerate(model_candidates, start=1):
            logger.info(
                "Starting LangChain agent turn.",
                extra={
                    "conversation_public_id": context.conversation_public_id,
                    "trigger_message_public_id": context.trigger_message_public_id,
                    "provider": candidate.provider,
                    "model_name": candidate.model_name,
                    "model_priority": priority,
                    "tool_count": len(tools),
                    "rag_status": (
                        context.rag_context.status if context.rag_context else "none"
                    ),
                },
            )

            try:
                model = build_chat_model(self.settings, candidate)
                agent = create_agent(
                    model=model,
                    tools=tools,
                    system_prompt=system_prompt,
                )
                response = agent.invoke({"messages": messages})
                result = build_agent_result(
                    response=response,
                    model_name=candidate.model_name,
                    provider=candidate.provider,
                )
            except AppException as exc:
                failed_attempts.append(self._build_failed_attempt(priority, candidate, exc))
                logger.warning(
                    "LangChain agent model candidate failed.",
                    extra={
                        "provider": candidate.provider,
                        "model_name": candidate.model_name,
                        "error_code": exc.code,
                        "error_message": exc.message,
                    },
                )
                continue
            except Exception as exc:
                failed_attempts.append(self._build_failed_attempt(priority, candidate, exc))
                logger.warning(
                    "LangChain agent model candidate failed.",
                    extra={
                        "provider": candidate.provider,
                        "model_name": candidate.model_name,
                        "error_code": "AGENT_UPSTREAM_FAILED",
                        "error_message": str(exc),
                    },
                )
                continue

            return self._with_model_fallback_metadata(
                result=result,
                candidate=candidate,
                priority=priority,
                failed_attempts=failed_attempts,
            )

        raise AppException(
            502,
            "AGENT_ALL_MODELS_FAILED",
            "All configured agent model candidates failed.",
            detail={"model_fallback_attempts": failed_attempts},
        )

    def stream(self, context: AgentTurnContext):
        """Stream one LangChain agent turn and return the final normalized result."""

        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise AppException(
                500,
                "AGENT_LANGCHAIN_NOT_INSTALLED",
                "Missing langchain dependency. Install backend/requirements.txt first.",
            ) from exc

        tools = build_tools(context, self.settings)
        messages = build_langchain_messages(
            context,
            max_history_messages=self.settings.agent_max_context_messages,
        )
        system_prompt = build_system_prompt(context)
        model_candidates = self._resolve_model_candidates()
        if not model_candidates:
            raise AppException(
                503,
                "AGENT_MODEL_NOT_CONFIGURED",
                "No configured agent model candidate is available.",
            )

        failed_attempts: list[dict[str, Any]] = []
        for priority, candidate in enumerate(model_candidates, start=1):
            chunk_count = 0
            tool_call_count = 0
            reply_parts: list[str] = []
            has_emitted_text = False

            logger.info(
                "Starting streamed LangChain agent turn.",
                extra={
                    "conversation_public_id": context.conversation_public_id,
                    "trigger_message_public_id": context.trigger_message_public_id,
                    "provider": candidate.provider,
                    "model_name": candidate.model_name,
                    "model_priority": priority,
                    "tool_count": len(tools),
                },
            )

            try:
                model = build_chat_model(self.settings, candidate)
                agent = create_agent(
                    model=model,
                    tools=tools,
                    system_prompt=system_prompt,
                )

                for chunk in agent.stream({"messages": messages}, stream_mode="messages"):
                    delta = extract_stream_delta(chunk)
                    tool_call_count += count_stream_tool_calls(chunk)
                    if not delta:
                        continue

                    has_emitted_text = True
                    chunk_count += 1
                    reply_parts.append(delta)
                    yield {"event": "delta", "data": {"content": delta}}

                result = build_streamed_agent_result(
                    reply_text="".join(reply_parts),
                    model_name=candidate.model_name,
                    provider=candidate.provider,
                    chunk_count=chunk_count,
                    tool_call_count=tool_call_count,
                )
            except AppException as exc:
                if has_emitted_text:
                    raise
                failed_attempts.append(self._build_failed_attempt(priority, candidate, exc))
                logger.warning(
                    "Streamed LangChain agent model candidate failed.",
                    extra={
                        "provider": candidate.provider,
                        "model_name": candidate.model_name,
                        "error_code": exc.code,
                        "error_message": exc.message,
                    },
                )
                continue
            except Exception as exc:
                if has_emitted_text:
                    raise
                failed_attempts.append(self._build_failed_attempt(priority, candidate, exc))
                logger.warning(
                    "Streamed LangChain agent model candidate failed.",
                    extra={
                        "provider": candidate.provider,
                        "model_name": candidate.model_name,
                        "error_code": "AGENT_UPSTREAM_FAILED",
                        "error_message": str(exc),
                    },
                )
                continue

            yield {
                "event": "final",
                "data": self._with_model_fallback_metadata(
                    result=result,
                    candidate=candidate,
                    priority=priority,
                    failed_attempts=failed_attempts,
                ),
            }
            return

        raise AppException(
            502,
            "AGENT_ALL_MODELS_FAILED",
            "All configured agent model candidates failed.",
            detail={"model_fallback_attempts": failed_attempts},
        )

    def _resolve_model_candidates(self) -> list[AgentModelCandidate]:
        candidates = getattr(self.settings, "agent_model_candidates", None)
        if candidates:
            return list(candidates)

        return [
            AgentModelCandidate(
                provider=self.settings.agent_model_provider,
                base_url=self.settings.agent_model_base_url,
                api_key=self.settings.agent_model_api_key,
                model_name=self.settings.agent_model_name,
            )
        ]

    @staticmethod
    def _build_failed_attempt(
        priority: int,
        candidate: AgentModelCandidate,
        exc: Exception,
    ) -> dict[str, Any]:
        if isinstance(exc, AppException):
            error_code = exc.code
            error_message = exc.message
        else:
            error_code = "AGENT_UPSTREAM_FAILED"
            error_message = str(exc)

        return {
            "priority": priority,
            "provider": candidate.provider,
            "model_name": candidate.model_name,
            "status": "failed",
            "error_code": error_code,
            "error_message": error_message,
        }

    @staticmethod
    def _with_model_fallback_metadata(
        *,
        result: AgentTurnResult,
        candidate: AgentModelCandidate,
        priority: int,
        failed_attempts: list[dict[str, Any]],
    ) -> AgentTurnResult:
        output_snapshot = dict(result.output_snapshot or {})
        output_snapshot["model_fallback"] = {
            "used_fallback": bool(failed_attempts),
            "used_priority": priority,
            "used_provider": candidate.provider,
            "used_model_name": candidate.model_name,
            "attempts": [
                *failed_attempts,
                {
                    "priority": priority,
                    "provider": candidate.provider,
                    "model_name": candidate.model_name,
                    "status": "succeeded",
                },
            ],
        }

        return replace(result, output_snapshot=output_snapshot)
