"""Build structured web search context when local RAG has no relevant hit."""

from agent.contracts import AgentTurnContext, RagContext, WebSearchContext, WebSearchResult
from agent.tools.web_search import search_web
from src.core.config import Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class WebSearchContextBuilder:
    """Run a bounded web search only after knowledge-base retrieval misses."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build(self, context: AgentTurnContext, rag_context: RagContext) -> WebSearchContext:
        query = (context.user_message_text or "").strip()
        if rag_context.status != "miss":
            return WebSearchContext(
                enabled=False,
                status="skipped",
                query=query,
            )

        if not self.settings.serpapi_api_key:
            return WebSearchContext(
                enabled=False,
                status="disabled",
                query=query,
                error_code="WEB_SEARCH_NOT_CONFIGURED",
                error_message="SERPAPI_API_KEY is not configured.",
            )

        try:
            return search_web(
                settings=self.settings,
                query=query,
                num_results=3,
            )
        except Exception as exc:
            logger.exception("Unexpected default web search failure.", exc_info=exc)
            return WebSearchContext(
                enabled=True,
                status="error",
                query=query,
                error_code="WEB_SEARCH_FAILED",
                error_message=str(exc),
            )


def web_search_context_to_snapshot(web_context: WebSearchContext | None) -> dict:
    if web_context is None:
        return {"enabled": False, "status": "disabled", "result_count": 0}

    return {
        "enabled": web_context.enabled,
        "status": web_context.status,
        "query": web_context.query,
        "result_count": len(web_context.results),
        "results": [_result_to_snapshot(result) for result in web_context.results],
        "error_code": web_context.error_code,
        "error_message": web_context.error_message,
    }


def _result_to_snapshot(result: WebSearchResult) -> dict:
    return {
        "title": result.title,
        "link": result.link,
        "snippet": result.snippet,
    }
