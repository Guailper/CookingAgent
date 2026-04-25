"""Unit tests for the MVP rule-based simple chat agent."""

import unittest

from agent.base_agent import AgentContext, AgentContextMessage
from agent.simple_chat_agent import SimpleChatAgent


class SimpleChatAgentTests(unittest.TestCase):
    """Keep the first agent implementation predictable and easy to evolve."""

    def setUp(self) -> None:
        self.agent = SimpleChatAgent()

    def _build_context(self, text: str) -> AgentContext:
        return AgentContext(
            conversation_public_id="conv_test",
            user_public_id="user_test",
            trigger_message_public_id="msg_test",
            user_message_text=text,
            recent_messages=[AgentContextMessage(role="user", content=text)],
        )

    def test_greeting_rule(self) -> None:
        result = self.agent.run(self._build_context("你好，在吗"))

        self.assertEqual(result.intent_type, "simple_chat")
        self.assertEqual(result.workflow_name, "simple_chat_workflow")
        self.assertEqual(result.output_snapshot["matched_rule"], "greeting")
        self.assertIn("在线", result.reply_text)

    def test_guidance_rule(self) -> None:
        result = self.agent.run(self._build_context("帮我做菜"))

        self.assertEqual(result.output_snapshot["matched_rule"], "guidance")
        self.assertIn("食材", result.reply_text)

    def test_default_rule(self) -> None:
        result = self.agent.run(self._build_context("我今晚想做一道适合两个人吃的晚餐"))

        self.assertEqual(result.output_snapshot["matched_rule"], "default")
        self.assertIn("已经收到", result.reply_text)


if __name__ == "__main__":
    unittest.main()
