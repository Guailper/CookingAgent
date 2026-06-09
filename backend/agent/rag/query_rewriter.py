"""Rewrite user questions into retrieval-friendly standalone queries."""

from typing import Any

from agent.contracts import AgentTurnContext
from agent.factories.model_factory import build_chat_model
from agent.prompts.system_prompts import _build_rewrite_prompt as build_rewrite_prompt
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from src.core.config import Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class QueryRewriter:
    """Use the configured chat model to improve RAG recall queries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def rewrite(self, context: AgentTurnContext) -> str:
        """Return a concise standalone query, falling back to the raw user input."""

        query = _normalize_text(context.user_message_text)
        if not query:
            return ""

        if not self._enabled():
            return query

        history = _render_recent_context(context)
        prompt = build_rewrite_prompt(query=query, history=history)

        try:
            model = build_chat_model(
                self.settings,
                temperature=getattr(self.settings, "rag_query_rewrite_temperature", 0.0),
            )
            rewrite_chain = _build_rewrite_chain(model)
            rewritten_query = rewrite_chain.invoke({"prompt": prompt})
        except Exception as exc:
            logger.warning("RAG query rewrite failed; using original query.", exc_info=exc)
            return query

        cleaned_query = _clean_rewritten_query(rewritten_query)
        if not cleaned_query:
            return query

        max_chars = max(20, int(getattr(self.settings, "rag_query_rewrite_max_chars", 180)))
        return cleaned_query[:max_chars].strip()

    def _enabled(self) -> bool:
        return bool(getattr(self.settings, "rag_query_rewrite_enabled", True))


def _render_recent_context(context: AgentTurnContext) -> str:
    max_messages = _resolve_history_limit(context)
    recent_messages = context.recent_messages[-max_messages:] if max_messages else []

    rendered_messages: list[str] = []
    for message in recent_messages:
        content = _normalize_text(message.content)
        if not content or content == _normalize_text(context.user_message_text):
            continue

        role = "用户" if message.role == "user" else "助手"
        rendered_messages.append(f"{role}: {content[:240]}")

    return "\n".join(rendered_messages)


def _resolve_history_limit(context: AgentTurnContext) -> int:
    raw_limit = getattr(context, "request_options", {}).get("rewrite_history_limit", 4)
    try:
        return max(0, int(raw_limit))
    except (TypeError, ValueError):
        return 4


def _build_rewrite_chain(model: Any) -> Any:
    """Build a small LangChain Runnable for query rewriting."""

    prompt_template = ChatPromptTemplate.from_messages([("human", "{prompt}")])
    return prompt_template | model | StrOutputParser()

def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response

    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return " ".join(parts)

    return ""


def _clean_rewritten_query(query: str) -> str:
    cleaned = _normalize_text(query)
    for prefix in ("改写后的检索查询：", "检索查询：", "查询：", "问题："):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()

    return cleaned.strip("「」\"'` ")


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").strip().split())
