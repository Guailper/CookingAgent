"""Web search tool adapter backed by SerpApi."""

from typing import Any

import httpx

from agent.contracts import WebSearchContext, WebSearchResult
from src.core.config import Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def build_web_search_tool(settings: Settings | None = None):
    """Create a web search tool backed by SerpApi."""

    tool_settings = settings or get_settings()

    def web_search(query: str, num_results: int = 5) -> str:
        """Search the web for fresh public information using SerpApi."""

        normalized_query = (query or "").strip()
        if not normalized_query:
            return "请提供要搜索的关键词。"

        context = search_web(
            settings=tool_settings,
            query=normalized_query,
            num_results=num_results,
        )
        return render_web_search_context(context)

    return web_search


def search_web(settings: Settings, query: str, num_results: int = 5) -> WebSearchContext:
    """Search SerpApi and return structured results that can be cited later."""

    normalized_query = (query or "").strip()
    if not normalized_query:
        return WebSearchContext(enabled=False, status="skipped", query="")

    if not settings.serpapi_api_key:
        return WebSearchContext(
            enabled=False,
            status="disabled",
            query=normalized_query,
            error_code="WEB_SEARCH_NOT_CONFIGURED",
            error_message="SERPAPI_API_KEY is not configured.",
        )

    limit = _normalize_result_limit(num_results)
    try:
        with httpx.Client(timeout=settings.web_search_request_timeout_seconds) as client:
            response = client.get(
                settings.serpapi_search_url,
                params={
                    "engine": "google",
                    "q": normalized_query,
                    "api_key": settings.serpapi_api_key,
                    "num": limit,
                    "hl": "zh-cn",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("SerpApi web search request failed.", exc_info=exc)
        return WebSearchContext(
            enabled=True,
            status="error",
            query=normalized_query,
            error_code="WEB_SEARCH_REQUEST_FAILED",
            error_message=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected web search tool failure.", exc_info=exc)
        return WebSearchContext(
            enabled=True,
            status="error",
            query=normalized_query,
            error_code="WEB_SEARCH_FAILED",
            error_message=str(exc),
        )

    if payload.get("error"):
        error_message = str(payload["error"])
        logger.warning("SerpApi returned an error.", extra={"error": error_message})
        return WebSearchContext(
            enabled=True,
            status="error",
            query=normalized_query,
            error_code="WEB_SEARCH_PROVIDER_ERROR",
            error_message=error_message,
        )

    results = _extract_organic_results(payload, limit)
    return WebSearchContext(
        enabled=True,
        status="hit" if results else "miss",
        query=normalized_query,
        results=results,
    )


def render_web_search_context(context: WebSearchContext) -> str:
    """Render structured web results for the LangChain tool interface."""

    if context.status == "disabled":
        return "网页搜索工具未配置 SERPAPI_API_KEY，暂时无法联网搜索。"
    if context.status == "error":
        return "网页搜索服务请求失败，暂时无法获取搜索结果。"
    if context.status == "miss":
        return f"没有搜索到与“{context.query}”相关的网页结果。"
    if not context.results:
        return "没有可用的网页搜索结果。"

    lines = [f"网页搜索结果：{context.query}"]
    for index, item in enumerate(context.results, start=1):
        lines.append(
            f"{index}. {item.title}\n"
            f"链接：{item.link}\n"
            f"摘要：{item.snippet or '无摘要'}"
        )

    return "\n\n".join(lines)


def _normalize_result_limit(num_results: int) -> int:
    try:
        return min(10, max(1, int(num_results)))
    except (TypeError, ValueError):
        return 5


def _extract_organic_results(payload: dict[str, Any], limit: int) -> list[WebSearchResult]:
    organic_results = payload.get("organic_results")
    if not isinstance(organic_results, list):
        return []

    return [
        WebSearchResult(
            title=str(item.get("title") or "无标题"),
            link=str(item.get("link") or ""),
            snippet=str(item.get("snippet") or item.get("description") or ""),
        )
        for item in organic_results[:limit]
        if isinstance(item, dict) and (item.get("title") or item.get("link"))
    ]
