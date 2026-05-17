"""Build LangChain tools for one agent turn."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agent.contracts import AgentTurnContext
from agent.tools.attachment_context import build_attachment_context_tool
from agent.tools.rag_search import build_rag_search_tool
from agent.tools.recipe_formatter import format_recipe_plan
from agent.tools.user_memory import build_user_memory_search_tool
from agent.tools.weather import build_weather_tool
from agent.tools.web_search import build_web_search_tool
from src.core.config import Settings, get_settings
from src.core.exceptions import AppException
from src.core.logging import get_logger

logger = get_logger(__name__)

MCP_ONLY_TOOL_NAMES = {
    "rag",
    "rag_search",
    "web_search",
    "search_web",
    "weather",
    "weather_search",
    "get_weather",
}


def build_tools(
    context: AgentTurnContext,
    settings: Settings | None = None,
) -> list[Any]:
    """Return the tools available to the LangChain agent for this turn."""

    resolved_settings = settings or get_settings()
    local_tools = [
        build_attachment_context_tool(context),
        build_user_memory_search_tool(context),
        build_rag_search_tool(context),
        build_web_search_tool(resolved_settings),
        build_weather_tool(resolved_settings),
        format_recipe_plan,
    ]
    if not resolved_settings.agent_mcp_servers:
        logger.info("No MCP servers configured for agent tools.")
        return local_tools

    mcp_tools = _run_async(_load_mcp_tools(resolved_settings.agent_mcp_servers))
    return [*local_tools, *_filter_mcp_only_tools(mcp_tools)]


async def _load_mcp_tools(server_config: dict[str, dict[str, Any]]) -> list[Any]:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:
        raise AppException(
            500,
            "AGENT_MCP_ADAPTER_NOT_INSTALLED",
            "Missing langchain-mcp-adapters dependency. Install backend/requirements.txt first.",
        ) from exc

    client = MultiServerMCPClient(server_config)
    return await client.get_tools()


def _filter_mcp_only_tools(tools: list[Any]) -> list[Any]:
    """Keep only tools that should be provided through MCP.

    RAG、联网搜索和天气查询统一由 MCP 提供；其余 MCP 工具不进入 Agent，
    避免覆盖项目里已经存在的本地工具逻辑。
    """

    filtered_tools = []
    for tool in tools:
        if _normalize_tool_name(getattr(tool, "name", None)) in MCP_ONLY_TOOL_NAMES:
            filtered_tools.append(tool)

    return filtered_tools


def _normalize_tool_name(name: Any) -> str:
    return str(name or "").strip().lower().replace("-", "_")


def _run_async(awaitable):
    """Run one adapter coroutine from the current synchronous agent path."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    # If this code is ever called from an active event loop, isolate the adapter call
    # in a short-lived worker thread instead of nesting event loops.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, awaitable)
        return future.result()
