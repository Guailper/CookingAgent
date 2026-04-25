"""Helpers for assembling the minimal agent runtime context."""

from agent.base_agent import AgentContext, AgentContextMessage


def build_agent_context(
    *,
    conversation_public_id: str,
    user_public_id: str,
    trigger_message_public_id: str,
    user_message_text: str,
    recent_messages: list[object],
) -> AgentContext:
    """Convert ORM messages into a small, agent-friendly context object."""

    return AgentContext(
        conversation_public_id=conversation_public_id,
        user_public_id=user_public_id,
        trigger_message_public_id=trigger_message_public_id,
        user_message_text=user_message_text,
        recent_messages=[
            AgentContextMessage(
                role=getattr(message, "role", "user"),
                content=getattr(message, "content", ""),
            )
            for message in recent_messages
        ],
    )
