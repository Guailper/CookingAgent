"""Shared workflow protocol."""

from typing import Protocol

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult


class AgentWorkflow(Protocol):
    name: str

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        """Execute one workflow and return a persistable result."""
