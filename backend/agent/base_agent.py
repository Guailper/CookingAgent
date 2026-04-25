"""Shared data structures and interfaces for backend agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from openai import OpenAI


@dataclass(frozen=True)
class AgentContextMessage:
    """A lightweight message view passed into the agent runtime."""

    role: str
    content: str


@dataclass(frozen=True)
class AgentContext:
    """Input assembled for one agent execution."""

    conversation_public_id: str
    user_public_id: str
    trigger_message_public_id: str
    user_message_text: str
    recent_messages: list[AgentContextMessage] = field(default_factory=list)


@dataclass(frozen=True)
class AgentResult:
    """Normalized result returned by an agent implementation."""

    reply_text: str
    intent_type: str
    workflow_name: str
    model_name: str | None = None
    output_snapshot: dict[str, Any] | None = None


class BaseAgent(ABC):
    """Common interface implemented by all backend agents."""
    def __init__(self):
        super().__init__()
    name: str = "base_agent"
    intent_type: str = "base"
    workflow_name: str = "base_workflow"

    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        """Generate a response for the given agent context."""
