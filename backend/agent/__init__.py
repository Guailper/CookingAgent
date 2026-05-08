"""LangChain-backed agent package for CookingAgent."""

from agent.contracts import AgentContextMessage, AgentTurnContext, AgentTurnResult

__all__ = [
    "AgentContextMessage",
    "AgentTurnContext",
    "AgentTurnResult",
    "LangChainAgentRunner",
]


def __getattr__(name: str):
    """Lazy-load the runner so lightweight contract imports do not pull tools."""

    if name == "LangChainAgentRunner":
        from agent.runner import LangChainAgentRunner

        return LangChainAgentRunner

    raise AttributeError(f"module 'agent' has no attribute {name!r}")
