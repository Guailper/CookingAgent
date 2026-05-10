"""Web search tool adapter backed by SerpApi."""

from typing import Any

import httpx

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

        if not tool_settings.serpapi_api_key:
            return "网页搜索工具未配置 SERPAPI_API_KEY，暂时无法联网搜索。"

        limit = _normalize_result_limit(num_results)
        try:
            with httpx.Client(timeout=tool_settings.web_search_request_timeout_seconds) as client:
                response = client.get(
                    tool_settings.serpapi_search_url,
                    params={
                        "engine": "google",
                        "q": normalized_query,
                        "api_key": tool_settings.serpapi_api_key,
                        "num": limit,
                        "hl": "zh-cn",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("SerpApi web search request failed.", exc_info=exc)
            return "网页搜索服务请求失败，暂时无法获取搜索结果。"
        except Exception as exc:
            logger.exception("Unexpected web search tool failure.", exc_info=exc)
            return "网页搜索失败，暂时无法获取搜索结果。"

        if payload.get("error"):
            logger.warning("SerpApi returned an error.", extra={"error": payload["error"]})
            return f"网页搜索服务返回错误：{payload['error']}"

        results = _extract_organic_results(payload, limit)
        if not results:
            return f"没有搜索到与“{normalized_query}”相关的网页结果。"

        lines = [f"网页搜索结果：{normalized_query}"]
        for index, item in enumerate(results, start=1):
            title = item.get("title") or "无标题"
            link = item.get("link") or ""
            snippet = item.get("snippet") or item.get("description") or "无摘要"
            lines.append(f"{index}. {title}\n链接：{link}\n摘要：{snippet}")

        return "\n\n".join(lines)

    return web_search


def _normalize_result_limit(num_results: int) -> int:
    try:
        return min(10, max(1, int(num_results)))
    except (TypeError, ValueError):
        return 5


def _extract_organic_results(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    organic_results = payload.get("organic_results")
    if not isinstance(organic_results, list):
        return []

    return [
        item
        for item in organic_results[:limit]
        if isinstance(item, dict) and (item.get("title") or item.get("link"))
    ]
