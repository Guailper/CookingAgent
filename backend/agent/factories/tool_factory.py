"""Build LangChain tools for one agent turn."""

from typing import Any

from agent.contracts import AgentTurnContext
from agent.tools.attachment_context import build_attachment_context_tool
from agent.tools.rag_search import build_rag_search_tool
from agent.tools.recipe_formatter import format_recipe_plan
from agent.tools.weather import build_weather_tool
from agent.tools.web_search import build_web_search_tool


def build_tools(context: AgentTurnContext) -> list[Any]:
    """Return the tools available to the LangChain agent for this turn."""

    return [
        build_rag_search_tool(context),
        build_attachment_context_tool(context),
        build_weather_tool(),
        build_web_search_tool(),
        format_recipe_plan,
    ]
