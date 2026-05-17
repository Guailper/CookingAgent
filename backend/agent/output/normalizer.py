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


def build_streamed_agent_result(
    *,
    reply_text: str,
    model_name: str | None,
    provider: str,
    chunk_count: int,
    tool_call_count: int = 0,
) -> AgentTurnResult:
    """Build the service-facing result from streamed LangChain output."""

    normalized_reply_text = (reply_text or "").strip()
    if not normalized_reply_text:
        raise AppException(
            502,
            "AGENT_EMPTY_RESPONSE",
            "LangChain Agent streamed no valid text.",
        )

    return AgentTurnResult(
        reply_text=normalized_reply_text,
        intent_type="langchain_agent",
        workflow_name="langchain_tool_calling_agent",
        model_name=model_name,
        output_snapshot={
            "reply_type": "agent_text",
            "provider": provider,
            "streamed": True,
            "chunk_count": chunk_count,
            "tool_call_count": tool_call_count,
            "degraded": False,
        },
    )


def extract_stream_delta(chunk: Any) -> str:
    """Extract visible text from one LangChain stream chunk."""

    token = chunk[0] if isinstance(chunk, tuple) and chunk else chunk

    content_blocks = getattr(token, "content_blocks", None)
    if isinstance(content_blocks, list):
        return _normalize_content_blocks(content_blocks)

    return _normalize_stream_content(getattr(token, "content", ""))


def count_stream_tool_calls(chunk: Any) -> int:
    """Count tool-call fragments on a streamed LangChain chunk."""

    token = chunk[0] if isinstance(chunk, tuple) and chunk else chunk
    tool_calls = getattr(token, "tool_calls", None)
    if isinstance(tool_calls, list):
        return len(tool_calls)

    tool_call_chunks = getattr(token, "tool_call_chunks", None)
    if isinstance(tool_call_chunks, list):
        return len(tool_call_chunks)

    return 0


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


def _normalize_stream_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    text_parts.append(text)
        return "".join(text_parts)

    return ""


def _normalize_content_blocks(content_blocks: list[Any]) -> str:
    text_parts: list[str] = []
    for block in content_blocks:
        if isinstance(block, dict):
            block_type = block.get("type")
            text = block.get("text") or block.get("content")
            if block_type in {None, "text"} and isinstance(text, str):
                text_parts.append(text)
        else:
            text = getattr(block, "text", None) or getattr(block, "content", None)
            if isinstance(text, str):
                text_parts.append(text)

    return "".join(text_parts)


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
