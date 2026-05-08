"""Convert project messages into LangChain chat messages."""

from typing import Any

from agent.contracts import AgentContextMessage, AgentTurnContext


def build_langchain_messages(context: AgentTurnContext, max_history_messages: int) -> list[Any]:
    """Build LangChain messages without duplicating the triggering user message."""

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except ImportError as exc:
        from src.core.exceptions import AppException

        raise AppException(
            500,
            "AGENT_LANGCHAIN_NOT_INSTALLED",
            "缺少 langchain-core 依赖，请先安装 backend/requirements.txt。",
        ) from exc

    messages: list[Any] = []
    trigger_text = normalize_user_text(context.user_message_text)

    for message in _trim_history(context.recent_messages, max_history_messages):
        content = (message.content or "").strip()
        if not content:
            continue

        normalized_role = (message.role or "").strip().lower()
        if normalized_role == "assistant":
            messages.append(AIMessage(content=content))
        elif normalized_role == "system":
            messages.append(SystemMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))

    if not messages or not _same_last_user_message(messages[-1], trigger_text):
        messages.append(HumanMessage(content=trigger_text))

    return messages


def normalize_user_text(user_message_text: str) -> str:
    """Return a non-empty user-facing message for the model."""

    normalized_text = (user_message_text or "").strip()
    if normalized_text:
        return normalized_text

    return "我刚发送了一条没有正文的消息，请提醒我补充具体需求或文字说明。"


def _trim_history(
    recent_messages: list[AgentContextMessage],
    max_history_messages: int,
) -> list[AgentContextMessage]:
    history_limit = max(1, max_history_messages)
    return recent_messages[-history_limit:]


def _same_last_user_message(message: Any, trigger_text: str) -> bool:
    message_type = getattr(message, "type", "")
    content = getattr(message, "content", "")
    return message_type == "human" and content == trigger_text
