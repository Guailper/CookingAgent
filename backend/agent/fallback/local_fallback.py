"""Deterministic fallback replies for unavailable model calls."""

from agent.contracts import AgentTurnContext, AgentTurnResult

ERROR_FALLBACK_REPLY = "智能体主模型当前不可用，请稍后重试，或先补充更具体的食材和目标。"


def build_fallback_result(
    context: AgentTurnContext,
    *,
    model_name: str | None,
    failure_code: str,
    failure_message: str,
) -> AgentTurnResult:
    """Build a local fallback result that can still be persisted as a reply."""

    _ = context
    return AgentTurnResult(
        reply_text=ERROR_FALLBACK_REPLY,
        intent_type="answer",
        workflow_name="local_fallback",
        model_name=model_name,
        output_snapshot={
            "reply_type": "fallback_text",
            "provider": "local_fallback",
            "degraded": True,
            "primary_failure_code": failure_code,
            "primary_failure_message": failure_message,
        },
    )
