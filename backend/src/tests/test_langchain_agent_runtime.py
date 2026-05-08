"""Tests for the LangChain-backed agent runtime."""

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent.contracts import (
    AgentContextMessage,
    AgentTurnContext,
    RagContext,
    RetrievedChunk,
)
from agent.factories.model_factory import _resolve_temperature, _should_disable_reasoning
from agent.fallback import build_fallback_result
from agent.output.normalizer import build_agent_result
from agent.prompts.system_prompts import build_system_prompt
from agent.rag.context_builder import RagContextBuilder, rag_context_to_snapshot
from agent.runner import LangChainAgentRunner
from agent.tools.rag_search import build_rag_search_tool
from agent.workflows.answer_workflow import AnswerWorkflow
from src.core.config import get_settings
from src.core.exceptions import AppException


class LangChainAgentRuntimeTests(unittest.TestCase):
    """Validate the LangChain agent boundary without network calls."""

    def _settings(self, **overrides):
        defaults = {
            "agent_model_provider": "openai_compatible",
            "agent_model_base_url": "https://example.com/v1",
            "agent_model_api_key": "test-key",
            "agent_model_name": "glm-4.7-flash-free",
            "agent_request_timeout_seconds": 30,
            "agent_max_context_messages": 6,
            "agent_temperature": 0.4,
            "agent_max_output_tokens": 512,
            "agent_disable_reasoning": True,
            "rag_default_knowledge_base_ids": ["cookbook"],
            "rag_final_top_k": 3,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def _context(
        self,
        text: str = "请用鸡蛋和米饭做一份蛋炒饭",
        knowledge_base_public_ids: list[str] | None = None,
    ) -> AgentTurnContext:
        return AgentTurnContext(
            conversation_public_id="conv_test",
            user_public_id="user_test",
            trigger_message_public_id="msg_test",
            user_message_text=text,
            recent_messages=[
                AgentContextMessage(role="assistant", content="上次我们聊到了家常菜。"),
                AgentContextMessage(role="user", content=text),
            ],
            knowledge_base_public_ids=(
                ["kb_test"] if knowledge_base_public_ids is None else knowledge_base_public_ids
            ),
            request_options={"top_k": 3},
        )

    def test_system_prompt_uses_preloaded_rag_context(self) -> None:
        context = self._context()
        context = AgentTurnContext(
            **{
                **context.__dict__,
                "rag_context": RagContext(
                    enabled=True,
                    status="hit",
                    query=context.user_message_text,
                    knowledge_base_public_ids=["cookbook"],
                    chunks=[
                        RetrievedChunk(
                            content="蛋炒饭适合使用隔夜米饭。",
                            document_title="家常炒饭",
                            chunk_index=1,
                            score=0.9,
                        )
                    ],
                ),
            }
        )

        prompt = build_system_prompt(context)

        self.assertIn("CookingAgent", prompt)
        self.assertIn("后端已经默认检索知识库", prompt)
        self.assertIn("蛋炒饭适合使用隔夜米饭", prompt)
        self.assertNotIn("必须先调用 rag_search", prompt)

    def test_rag_search_tool_returns_retrieved_chunks(self) -> None:
        with patch("agent.tools.rag_search.RagRetriever") as retriever_cls:
            retriever_cls.return_value.retrieve.return_value = [
                SimpleNamespace(
                    content="鸡蛋炒饭需要先打散鸡蛋，再用隔夜米饭快速翻炒。",
                    document_title="家常炒饭",
                    chunk_index=2,
                    page_no=None,
                    score=0.91,
                    metadata={},
                )
            ]
            tool = build_rag_search_tool(self._context())

            result = tool("蛋炒饭资料")

        self.assertIn("鸡蛋炒饭", result)
        self.assertIn("家常炒饭", result)
        retriever_cls.return_value.retrieve.assert_called_once()

    def test_rag_search_tool_uses_default_cookbook_when_context_has_no_kb(self) -> None:
        with patch("agent.tools.rag_search.RagRetriever") as retriever_cls:
            retriever_cls.return_value.retrieve.return_value = []
            tool = build_rag_search_tool(self._context(knowledge_base_public_ids=[]))

            tool("蛋炒饭资料")

        call_kwargs = retriever_cls.return_value.retrieve.call_args.kwargs
        self.assertIn("cookbook", call_kwargs["knowledge_base_public_ids"])

    def test_rag_context_builder_marks_miss_when_default_retrieval_has_no_chunks(self) -> None:
        with patch("agent.rag.context_builder.RagRetriever") as retriever_cls:
            retriever_cls.return_value.retrieve.return_value = []

            rag_context = RagContextBuilder(self._settings()).build(
                self._context(knowledge_base_public_ids=[])
            )

        self.assertTrue(rag_context.enabled)
        self.assertEqual(rag_context.status, "miss")
        self.assertIn("cookbook", rag_context.knowledge_base_public_ids)

    def test_rag_context_snapshot_keeps_chunk_citations(self) -> None:
        snapshot = rag_context_to_snapshot(
            RagContext(
                enabled=True,
                status="hit",
                query="蛋炒饭",
                knowledge_base_public_ids=["cookbook"],
                chunks=[
                    RetrievedChunk(
                        content="content",
                        document_title="家常炒饭",
                        chunk_index=2,
                        score=0.91,
                        metadata={
                            "document_public_id": "doc_1",
                            "chunk_public_id": "chunk_1",
                        },
                    )
                ],
            )
        )

        self.assertEqual(snapshot["status"], "hit")
        self.assertEqual(snapshot["chunk_count"], 1)
        self.assertEqual(snapshot["chunks"][0]["document_public_id"], "doc_1")

    def test_answer_workflow_adds_intent_and_rag_metadata(self) -> None:
        fake_runner = SimpleNamespace(
            settings=self._settings(),
            run=lambda context: build_agent_result(
                response={
                    "messages": [
                        SimpleNamespace(type="ai", content="可以做蛋炒饭。"),
                    ]
                },
                model_name="glm-4.7-flash-free",
                provider="openai_compatible",
            ),
        )
        fake_rag_builder = SimpleNamespace(
            build=lambda context: RagContext(
                enabled=True,
                status="miss",
                query=context.user_message_text,
                knowledge_base_public_ids=["cookbook"],
            )
        )

        result = AnswerWorkflow(
            runner=fake_runner,
            settings=self._settings(),
            rag_context_builder=fake_rag_builder,
        ).run(
            self._context(),
            SimpleNamespace(
                intent_type="answer",
                confidence=1.0,
                source="default",
                reason="default",
            ),
        )

        self.assertEqual(result.intent_type, "answer")
        self.assertEqual(result.workflow_name, "answer_workflow")
        self.assertEqual(result.output_snapshot["rag"]["status"], "miss")

    def test_output_normalizer_extracts_final_ai_message_and_metadata(self) -> None:
        messages = [
            SimpleNamespace(type="human", content="你好"),
            SimpleNamespace(
                type="ai",
                content="可以，先把鸡蛋打散，再炒米饭。",
                tool_calls=[{"name": "rag_search"}],
                usage_metadata={"total_tokens": 42},
            ),
        ]

        result = build_agent_result(
            response={"messages": messages},
            model_name="glm-4.7-flash-free",
            provider="openai_compatible",
        )

        self.assertIn("鸡蛋", result.reply_text)
        self.assertEqual(result.intent_type, "langchain_agent")
        self.assertEqual(result.workflow_name, "langchain_tool_calling_agent")
        self.assertEqual(result.output_snapshot["tool_call_count"], 1)
        self.assertEqual(result.output_snapshot["usage"]["total_tokens"], 42)

    def test_output_normalizer_rejects_empty_agent_reply(self) -> None:
        messages = [SimpleNamespace(type="ai", content="")]

        with self.assertRaises(AppException) as raised:
            build_agent_result(
                response={"messages": messages},
                model_name="glm-4.7-flash-free",
                provider="openai_compatible",
            )

        self.assertEqual(raised.exception.code, "AGENT_EMPTY_RESPONSE")

    def test_fallback_result_is_persistable_and_marks_degraded(self) -> None:
        result = build_fallback_result(
            self._context(),
            model_name="glm-4.7-flash-free",
            failure_code="AGENT_UPSTREAM_FAILED",
            failure_message="timeout",
        )

        self.assertIn("主模型当前不可用", result.reply_text)
        self.assertEqual(result.intent_type, "answer")
        self.assertEqual(result.workflow_name, "local_fallback")
        self.assertTrue(result.output_snapshot["degraded"])
        self.assertEqual(result.output_snapshot["primary_failure_code"], "AGENT_UPSTREAM_FAILED")

    def test_runner_invokes_langchain_create_agent(self) -> None:
        fake_agents_module = types.ModuleType("langchain.agents")
        fake_langchain_module = types.ModuleType("langchain")

        class _FakeCompiledAgent:
            def __init__(self) -> None:
                self.invoked_payload = None

            def invoke(self, payload):
                self.invoked_payload = payload
                return {
                    "messages": [
                        SimpleNamespace(type="human", content="hi"),
                        SimpleNamespace(type="ai", content="可以做蛋炒饭。"),
                    ]
                }

        compiled_agent = _FakeCompiledAgent()

        def create_agent(*, model, tools, system_prompt):
            self.assertEqual(model, "fake-model")
            self.assertEqual(tools, ["fake-tool"])
            self.assertIn("CookingAgent", system_prompt)
            return compiled_agent

        fake_agents_module.create_agent = create_agent
        fake_langchain_module.agents = fake_agents_module

        with patch.dict(
            sys.modules,
            {
                "langchain": fake_langchain_module,
                "langchain.agents": fake_agents_module,
            },
        ), patch(
            "agent.runner.build_chat_model",
            return_value="fake-model",
        ), patch(
            "agent.runner.build_tools",
            return_value=["fake-tool"],
        ), patch(
            "agent.runner.build_langchain_messages",
            return_value=["fake-message"],
        ):
            result = LangChainAgentRunner(settings=self._settings()).run(self._context())

        self.assertEqual(result.reply_text, "可以做蛋炒饭。")
        self.assertEqual(compiled_agent.invoked_payload["messages"], ["fake-message"])

    def test_kimi_provider_does_not_send_glm_thinking_parameter(self) -> None:
        settings = self._settings(
            agent_model_provider="kimi",
            agent_model_name="kimi-k2.6",
            agent_disable_reasoning=True,
        )

        self.assertFalse(_should_disable_reasoning(settings, "kimi"))

    def test_kimi_provider_forces_supported_temperature(self) -> None:
        settings = self._settings(
            agent_model_provider="kimi",
            agent_model_name="kimi-k2.6",
            agent_temperature=0.4,
        )

        self.assertEqual(_resolve_temperature(settings, "kimi"), 1.0)

    def test_settings_prefers_kimi_specific_model_config(self) -> None:
        env = {
            "AGENT_MODEL_PROVIDER": "kimi",
            "AGENT_MODEL_BASE_URL": "https://generic.example/v1",
            "AGENT_MODEL_API_KEY": "generic-key",
            "AGENT_MODEL_NAME": "generic-model",
            "KIMI_BASE_URL": "https://api.moonshot.cn/v1",
            "KIMI_API_KEY": "kimi-key",
            "KIMI_MODEL_ID": "kimi-k2.6",
        }

        with patch.dict("os.environ", env, clear=False):
            get_settings.cache_clear()
            settings = get_settings()
            get_settings.cache_clear()

        self.assertEqual(settings.agent_model_provider, "kimi")
        self.assertEqual(settings.agent_model_base_url, "https://api.moonshot.cn/v1")
        self.assertEqual(settings.agent_model_api_key, "kimi-key")
        self.assertEqual(settings.agent_model_name, "kimi-k2.6")


if __name__ == "__main__":
    unittest.main()
