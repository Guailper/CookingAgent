"""Minimal agent orchestrator for routing one request to one agent."""

from agent.base_agent import AgentContext, AgentResult
from agent.simple_chat_agent import SimpleChatAgent


class AgentOrchestrator:
    """Route the current request to the MVP simple chat agent."""

    def __init__(self) -> None:
        self.simple_chat_agent = SimpleChatAgent()

    def run(self, context: AgentContext) -> AgentResult:
        """Execute the only workflow currently supported."""

        return self.simple_chat_agent.run(context)
