"""Normalize LangChain agent responses into project results."""

from typing import Any

from agent.contracts import AgentTurnResult
from src.core.exceptions import AppException


def build_agent_result(
    *,
    response: Any,
    model_name: str | None,
    provider: str,
) -> AgentTurnResult:
    """Build the service-facing result from a LangChain agent response."""

    messages = _extract_messages(response)
    reply_text = _extract_final_text(messages)
    if not reply_text:
        raise AppException(
            502,
            "AGENT_EMPTY_RESPONSE",
            "LangChain Agent 执行完成，但没有生成有效文本。",
        )

    return AgentTurnResult(
        reply_text=reply_text,
        intent_type="langchain_agent",
        workflow_name="langchain_tool_calling_agent",
        model_name=model_name,
        output_snapshot={
            "reply_type": "agent_text",
            "provider": provider,
            "message_count": len(messages),
            "tool_call_count": _count_tool_calls(messages),
            "usage": _extract_usage(messages),
            "degraded": False,
        },
    )


def _extract_messages(response: Any) -> list[Any]:
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list):
            return messages

    messages = getattr(response, "messages", None)
    if isinstance(messages, list):
        return messages

    return []


def _extract_final_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        message_type = str(getattr(message, "type", "")).lower()
        if message_type not in {"ai", "assistant"}:
            continue

        text = _normalize_content(getattr(message, "content", ""))
        if text:
            return text

    return ""


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                text_parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
        return "\n".join(text_parts).strip()

    return ""


def _count_tool_calls(messages: list[Any]) -> int:
    count = 0
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            count += len(tool_calls)
    return count


def _extract_usage(messages: list[Any]) -> dict[str, Any] | None:
    for message in reversed(messages):
        usage_metadata = getattr(message, "usage_metadata", None)
        if isinstance(usage_metadata, dict):
            return usage_metadata

        response_metadata = getattr(message, "response_metadata", None)
        if isinstance(response_metadata, dict):
            token_usage = response_metadata.get("token_usage")
            if isinstance(token_usage, dict):
                return token_usage

    return None
