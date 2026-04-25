"""A minimal rule-based agent that guarantees an assistant reply."""

from agent.base_agent import AgentContext, AgentResult, BaseAgent
from agent.prompts import DEFAULT_REPLY, GREETING_REPLY, GUIDANCE_REPLY

GREETING_KEYWORDS = ("你好", "您好", "hi", "hello", "在吗", "嗨")
GUIDANCE_KEYWORDS = ("做菜", "推荐", "怎么办", "吃什么", "帮我", "菜谱")


class SimpleChatAgent(BaseAgent):
    """Generate a stable text reply without calling any external model."""

    name = "simple_chat_agent"
    intent_type = "simple_chat"
    workflow_name = "simple_chat_workflow"

    def run(self, context: AgentContext) -> AgentResult:
        """Reply with a small set of deterministic rules."""

        normalized_text = context.user_message_text.strip()
        lower_text = normalized_text.lower()

        if any(keyword in normalized_text or keyword in lower_text for keyword in GREETING_KEYWORDS):
            matched_rule = "greeting"
            reply_text = GREETING_REPLY
        elif len(normalized_text) <= 12 and any(
            keyword in normalized_text for keyword in GUIDANCE_KEYWORDS
        ):
            matched_rule = "guidance"
            reply_text = GUIDANCE_REPLY
        else:
            matched_rule = "default"
            reply_text = DEFAULT_REPLY

        return AgentResult(
            reply_text=reply_text,
            intent_type=self.intent_type,
            workflow_name=self.workflow_name,
            model_name=None,
            output_snapshot={
                "reply_type": "text",
                "matched_rule": matched_rule,
                "context_message_count": len(context.recent_messages),
            },
        )
