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
    RetrievalDecision,
    RetrievedChunk,
    WebSearchContext,
    WebSearchResult,
)
from agent.factories.model_factory import (
    _resolve_temperature,
    _should_disable_reasoning,
    build_chat_model,
)
from agent.fallback import build_fallback_result
from agent.output.normalizer import build_agent_result
from agent.prompts.system_prompts import build_system_prompt
from agent.rag.context_builder import RagContextBuilder, rag_context_to_snapshot
from agent.runner import LangChainAgentRunner
from agent.tools.rag_search import build_rag_search_tool
from agent.tools.weather import build_weather_tool
from agent.tools.web_search import build_web_search_tool
from agent.workflows.answer_workflow import AnswerWorkflow
from src.core.config import AgentModelCandidate, get_settings
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
            "agent_model_candidates": [],
            "rag_default_knowledge_base_ids": ["cookbook"],
            "rag_final_top_k": 3,
            "weather_api_key": "",
            "weather_api_base_url": "https://devapi.qweather.com",
            "weather_geo_base_url": "https://geoapi.qweather.com",
            "weather_request_timeout_seconds": 10,
            "serpapi_api_key": "",
            "serpapi_search_url": "https://serpapi.com/search.json",
            "web_search_request_timeout_seconds": 15,
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

    def test_system_prompt_includes_conversation_summary(self) -> None:
        context = self._context()
        context = AgentTurnContext(
            **{
                **context.__dict__,
                "conversation_summary": "当前目标：做一份快手晚餐。\n已确认约束：不吃香菜。",
            }
        )

        prompt = build_system_prompt(context)

        self.assertIn("历史会话摘要", prompt)
        self.assertIn("不吃香菜", prompt)
        self.assertIn("本轮用户输入为准", prompt)

    def test_system_prompt_explains_skipped_rag_context(self) -> None:
        context = self._context(text="谢谢")
        context = AgentTurnContext(
            **{
                **context.__dict__,
                "rag_context": RagContext(
                    enabled=True,
                    status="skipped",
                    query=context.user_message_text,
                    knowledge_base_public_ids=["cookbook"],
                    decision=RetrievalDecision(
                        should_retrieve=False,
                        source="rule",
                        reason="skip control turn",
                    ),
                ),
            }
        )

        prompt = build_system_prompt(context)

        self.assertIn("规则判断不需要检索", prompt)
        self.assertIn("不要声称已经检索过知识库", prompt)

    def test_system_prompt_includes_web_sources_after_rag_miss(self) -> None:
        context = self._context(text="空气炸锅烤红薯温度")
        context = AgentTurnContext(
            **{
                **context.__dict__,
                "rag_context": RagContext(
                    enabled=True,
                    status="miss",
                    query=context.user_message_text,
                    knowledge_base_public_ids=["cookbook"],
                ),
                "web_search_context": WebSearchContext(
                    enabled=True,
                    status="hit",
                    query=context.user_message_text,
                    results=[
                        WebSearchResult(
                            title="空气炸锅烤红薯做法",
                            link="https://example.com/sweet-potato",
                            snippet="建议 180 到 200 度烘烤。",
                        )
                    ],
                ),
            }
        )

        prompt = build_system_prompt(context)

        self.assertIn("知识库未检索到相关信息", prompt)
        self.assertIn("联网搜索结果", prompt)
        self.assertIn("空气炸锅烤红薯做法", prompt)
        self.assertIn("https://example.com/sweet-potato", prompt)
        self.assertIn("不要编造来源或链接", prompt)

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

    def test_weather_tool_reports_missing_api_key(self) -> None:
        tool = build_weather_tool(self._settings(weather_api_key=""))

        result = tool("北京", "now")

        self.assertIn("WEATHER_API_KEY", result)

    def test_weather_tool_returns_current_weather(self) -> None:
        requested_urls = []

        class _FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class _FakeClient:
            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def get(self, url, params):
                requested_urls.append(url)
                if "city/lookup" in url:
                    return _FakeResponse(
                        {"code": "200", "location": [{"id": "101010100", "name": "北京"}]}
                    )
                return _FakeResponse(
                    {
                        "code": "200",
                        "now": {
                            "text": "晴",
                            "temp": "26",
                            "feelsLike": "27",
                            "humidity": "35",
                            "windDir": "东北风",
                        },
                    }
                )

        with patch("agent.tools.weather.httpx.Client", _FakeClient):
            tool = build_weather_tool(self._settings(weather_api_key="weather-key"))
            result = tool("北京", "now")

        self.assertIn("北京当前天气：晴", result)
        self.assertIn("气温 26°C", result)
        self.assertEqual("https://geoapi.qweather.com/geo/v2/city/lookup", requested_urls[0])
        self.assertEqual("https://devapi.qweather.com/v7/weather/now", requested_urls[1])

    def test_weather_tool_normalizes_legacy_geo_endpoint(self) -> None:
        requested_urls = []

        class _FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class _FakeClient:
            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def get(self, url, params):
                requested_urls.append(url)
                if "city/lookup" in url:
                    return _FakeResponse(
                        {"code": "200", "location": [{"id": "101010100", "name": "北京"}]}
                    )
                return _FakeResponse({"code": "200", "now": {"text": "晴", "temp": "26"}})

        settings = self._settings(
            weather_api_key="weather-key",
            weather_api_base_url="https://k76x87f4f5.re.qweatherapi.com/v7/weather/",
            weather_geo_base_url="https://k76x87f4f5.re.qweatherapi.com/v2/city/lookup",
        )

        with patch("agent.tools.weather.httpx.Client", _FakeClient):
            tool = build_weather_tool(settings)
            result = tool("北京", "now")

        self.assertIn("北京当前天气：晴", result)
        self.assertEqual(
            "https://k76x87f4f5.re.qweatherapi.com/geo/v2/city/lookup",
            requested_urls[0],
        )
        self.assertEqual(
            "https://k76x87f4f5.re.qweatherapi.com/v7/weather/now",
            requested_urls[1],
        )

    def test_web_search_tool_reports_missing_api_key(self) -> None:
        tool = build_web_search_tool(self._settings(serpapi_api_key=""))

        result = tool("红烧肉 做法")

        self.assertIn("SERPAPI_API_KEY", result)

    def test_web_search_tool_returns_organic_results(self) -> None:
        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "organic_results": [
                        {
                            "title": "红烧肉做法",
                            "link": "https://example.com/recipe",
                            "snippet": "家常红烧肉步骤。",
                        }
                    ]
                }

        class _FakeClient:
            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def get(self, url, params):
                return _FakeResponse()

        with patch("agent.tools.web_search.httpx.Client", _FakeClient):
            tool = build_web_search_tool(self._settings(serpapi_api_key="serp-key"))
            result = tool("红烧肉 做法", 3)

        self.assertIn("红烧肉做法", result)
        self.assertIn("https://example.com/recipe", result)

    def test_rag_context_builder_marks_miss_when_default_retrieval_has_no_chunks(self) -> None:
        with patch("agent.rag.context_builder.RagRetriever") as retriever_cls:
            retriever_cls.return_value.retrieve.return_value = []

            rag_context = RagContextBuilder(self._settings()).build(
                self._context(knowledge_base_public_ids=[])
            )

        self.assertTrue(rag_context.enabled)
        self.assertEqual(rag_context.status, "miss")
        self.assertIn("cookbook", rag_context.knowledge_base_public_ids)
        self.assertTrue(rag_context.decision.should_retrieve)

    def test_rag_context_builder_skips_short_control_turns(self) -> None:
        with patch("agent.rag.context_builder.RagRetriever") as retriever_cls:
            rag_context = RagContextBuilder(self._settings()).build(
                self._context(text="谢谢", knowledge_base_public_ids=[])
            )

        self.assertTrue(rag_context.enabled)
        self.assertEqual(rag_context.status, "skipped")
        self.assertFalse(rag_context.decision.should_retrieve)
        retriever_cls.return_value.retrieve.assert_not_called()

    def test_rag_context_builder_retrieves_for_domain_questions(self) -> None:
        with patch("agent.rag.context_builder.RagRetriever") as retriever_cls:
            retriever_cls.return_value.retrieve.return_value = []

            rag_context = RagContextBuilder(self._settings()).build(
                self._context(text="鸡蛋和米饭怎么做", knowledge_base_public_ids=[])
            )

        self.assertEqual(rag_context.status, "miss")
        self.assertTrue(rag_context.decision.should_retrieve)
        retriever_cls.return_value.retrieve.assert_called_once()

    def test_rag_context_snapshot_keeps_chunk_citations_and_decision(self) -> None:
        snapshot = rag_context_to_snapshot(
            RagContext(
                enabled=True,
                status="hit",
                query="蛋炒饭",
                knowledge_base_public_ids=["cookbook"],
                decision=RetrievalDecision(
                    should_retrieve=True,
                    source="rule",
                    reason="domain question",
                ),
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
        self.assertTrue(snapshot["decision"]["should_retrieve"])

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
                status="skipped",
                query=context.user_message_text,
                knowledge_base_public_ids=["cookbook"],
                decision=RetrievalDecision(
                    should_retrieve=False,
                    source="rule",
                    reason="control turn",
                ),
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
        self.assertEqual(result.output_snapshot["rag"]["status"], "skipped")
        self.assertEqual(result.output_snapshot["web_search"]["status"], "skipped")
        self.assertFalse(result.output_snapshot["rag"]["decision"]["should_retrieve"])

    def test_answer_workflow_adds_web_search_context_when_rag_misses(self) -> None:
        class _FakeRunner:
            def __init__(self, settings) -> None:
                self.settings = settings
                self.context = None

            def run(self, context):
                self.context = context
                return build_agent_result(
                    response={
                        "messages": [
                            SimpleNamespace(type="ai", content="可以参考网页结果回答。"),
                        ]
                    },
                    model_name="glm-4.7-flash-free",
                    provider="openai_compatible",
                )

        fake_runner = _FakeRunner(self._settings())
        fake_rag_builder = SimpleNamespace(
            build=lambda context: RagContext(
                enabled=True,
                status="miss",
                query=context.user_message_text,
                knowledge_base_public_ids=["cookbook"],
                decision=RetrievalDecision(
                    should_retrieve=True,
                    source="rule",
                    reason="domain question",
                ),
            )
        )
        fake_web_builder = SimpleNamespace(
            build=lambda context, rag_context: WebSearchContext(
                enabled=True,
                status="hit",
                query=context.user_message_text,
                results=[
                    WebSearchResult(
                        title="空气炸锅烤红薯做法",
                        link="https://example.com/sweet-potato",
                        snippet="180 到 200 度烘烤。",
                    )
                ],
            )
        )

        result = AnswerWorkflow(
            runner=fake_runner,
            settings=self._settings(),
            rag_context_builder=fake_rag_builder,
            web_search_context_builder=fake_web_builder,
        ).run(
            self._context(text="空气炸锅烤红薯温度"),
            SimpleNamespace(
                intent_type="answer",
                confidence=1.0,
                source="default",
                reason="default",
            ),
        )

        self.assertEqual(fake_runner.context.web_search_context.status, "hit")
        self.assertEqual(result.output_snapshot["rag"]["status"], "miss")
        self.assertEqual(result.output_snapshot["web_search"]["status"], "hit")
        self.assertEqual(
            result.output_snapshot["web_search"]["results"][0]["link"],
            "https://example.com/sweet-potato",
        )

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

    def test_runner_tries_next_model_candidate_after_failure(self) -> None:
        fake_agents_module = types.ModuleType("langchain.agents")
        fake_langchain_module = types.ModuleType("langchain")

        class _FakeCompiledAgent:
            def __init__(self, model):
                self.model = model

            def invoke(self, payload):
                _ = payload
                if self.model == "primary-model":
                    raise RuntimeError("primary unavailable")
                return {
                    "messages": [
                        SimpleNamespace(type="human", content="hi"),
                        SimpleNamespace(type="ai", content="备用模型回答。"),
                    ]
                }

        def create_agent(*, model, tools, system_prompt):
            _ = tools
            _ = system_prompt
            return _FakeCompiledAgent(model)

        fake_agents_module.create_agent = create_agent
        fake_langchain_module.agents = fake_agents_module
        settings = self._settings(
            agent_model_candidates=[
                AgentModelCandidate(
                    provider="kimi",
                    base_url="https://primary.example/v1",
                    api_key="primary-key",
                    model_name="kimi-k2.6",
                ),
                AgentModelCandidate(
                    provider="aihubmix",
                    base_url="https://backup.example/v1",
                    api_key="backup-key",
                    model_name="glm-4.7-flash-free",
                ),
            ]
        )

        with patch.dict(
            sys.modules,
            {
                "langchain": fake_langchain_module,
                "langchain.agents": fake_agents_module,
            },
        ), patch(
            "agent.runner.build_chat_model",
            side_effect=["primary-model", "backup-model"],
        ), patch(
            "agent.runner.build_tools",
            return_value=["fake-tool"],
        ), patch(
            "agent.runner.build_langchain_messages",
            return_value=["fake-message"],
        ):
            result = LangChainAgentRunner(settings=settings).run(self._context())

        self.assertEqual(result.reply_text, "备用模型回答。")
        self.assertEqual(result.model_name, "glm-4.7-flash-free")
        self.assertEqual(result.output_snapshot["provider"], "aihubmix")
        self.assertTrue(result.output_snapshot["model_fallback"]["used_fallback"])
        self.assertEqual(result.output_snapshot["model_fallback"]["used_priority"], 2)
        self.assertEqual(
            result.output_snapshot["model_fallback"]["attempts"][0]["status"],
            "failed",
        )
        self.assertEqual(
            result.output_snapshot["model_fallback"]["attempts"][1]["status"],
            "succeeded",
        )

    def test_runner_tries_next_model_candidate_after_empty_response(self) -> None:
        fake_agents_module = types.ModuleType("langchain.agents")
        fake_langchain_module = types.ModuleType("langchain")

        class _FakeCompiledAgent:
            def __init__(self, model):
                self.model = model

            def invoke(self, payload):
                _ = payload
                if self.model == "primary-model":
                    return {"messages": [SimpleNamespace(type="ai", content="")]}
                return {
                    "messages": [
                        SimpleNamespace(type="ai", content="备用模型回答。"),
                    ]
                }

        def create_agent(*, model, tools, system_prompt):
            _ = tools
            _ = system_prompt
            return _FakeCompiledAgent(model)

        fake_agents_module.create_agent = create_agent
        fake_langchain_module.agents = fake_agents_module
        settings = self._settings(
            agent_model_candidates=[
                AgentModelCandidate(
                    provider="kimi",
                    base_url="https://primary.example/v1",
                    api_key="primary-key",
                    model_name="kimi-k2.6",
                ),
                AgentModelCandidate(
                    provider="aihubmix",
                    base_url="https://backup.example/v1",
                    api_key="backup-key",
                    model_name="glm-4.7-flash-free",
                ),
            ]
        )

        with patch.dict(
            sys.modules,
            {
                "langchain": fake_langchain_module,
                "langchain.agents": fake_agents_module,
            },
        ), patch(
            "agent.runner.build_chat_model",
            side_effect=["primary-model", "backup-model"],
        ), patch(
            "agent.runner.build_tools",
            return_value=["fake-tool"],
        ), patch(
            "agent.runner.build_langchain_messages",
            return_value=["fake-message"],
        ):
            result = LangChainAgentRunner(settings=settings).run(self._context())

        self.assertEqual(result.reply_text, "备用模型回答。")
        self.assertEqual(result.model_name, "glm-4.7-flash-free")
        self.assertTrue(result.output_snapshot["model_fallback"]["used_fallback"])
        self.assertEqual(
            result.output_snapshot["model_fallback"]["attempts"][0]["error_code"],
            "AGENT_EMPTY_RESPONSE",
        )

    def test_kimi_provider_disables_thinking_for_tool_call_compatibility(self) -> None:
        settings = self._settings(
            agent_model_provider="kimi",
            agent_model_name="kimi-k2.6",
            agent_disable_reasoning=True,
        )

        self.assertTrue(_should_disable_reasoning(settings, "kimi"))

    def test_kimi_provider_forces_supported_temperature_when_thinking_enabled(self) -> None:
        settings = self._settings(
            agent_model_provider="kimi",
            agent_model_name="kimi-k2.5",
            agent_temperature=0.4,
            agent_disable_reasoning=False,
        )

        self.assertEqual(_resolve_temperature(settings, "kimi"), 1.0)

    def test_kimi_provider_forces_supported_temperature_when_thinking_disabled(self) -> None:
        settings = self._settings(
            agent_model_provider="kimi",
            agent_model_name="kimi-k2.5",
            agent_temperature=1.0,
            agent_disable_reasoning=True,
        )

        self.assertEqual(_resolve_temperature(settings, "kimi"), 0.6)

    def test_kimi_chat_model_sends_thinking_in_extra_body(self) -> None:
        captured_kwargs = {}

        class _FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        fake_langchain_openai = types.SimpleNamespace(ChatOpenAI=_FakeChatOpenAI)
        settings = self._settings(
            agent_model_provider="kimi",
            agent_model_base_url="https://api.moonshot.cn/v1",
            agent_model_api_key="kimi-key",
            agent_model_name="kimi-k2.5",
            agent_temperature=1.0,
            agent_disable_reasoning=True,
        )

        with patch.dict(sys.modules, {"langchain_openai": fake_langchain_openai}):
            build_chat_model(settings)

        self.assertEqual(captured_kwargs["model"], "kimi-k2.5")
        self.assertEqual(captured_kwargs["temperature"], 0.6)
        self.assertEqual(captured_kwargs["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertNotIn("model_kwargs", captured_kwargs)

    def test_settings_prefers_kimi_specific_model_config(self) -> None:
        env = {
            "AGENT_MODEL_PROVIDER": "kimi",
            "AGENT_MODEL_BASE_URL": "https://generic.example/v1",
            "AGENT_MODEL_API_KEY": "generic-key",
            "AGENT_MODEL_NAME": "generic-model",
            "KIMI_BASE_URL": "https://api.moonshot.cn/v1",
            "KIMI_API_KEY": "kimi-key",
            "KIMI_MODEL_ID": "kimi-k2.5",
        }

        with patch.dict("os.environ", env, clear=False):
            get_settings.cache_clear()
            settings = get_settings()
            get_settings.cache_clear()

        self.assertEqual(settings.agent_model_provider, "kimi")
        self.assertEqual(settings.agent_model_base_url, "https://api.moonshot.cn/v1")
        self.assertEqual(settings.agent_model_api_key, "kimi-key")
        self.assertEqual(settings.agent_model_name, "kimi-k2.5")

    def test_settings_builds_agent_model_fallback_candidates_in_configured_order(self) -> None:
        env = {
            "AGENT_MODEL_PROVIDER": "kimi",
            "AGENT_MODEL_FALLBACK_ORDER": "kimi,xiaomi,aihubmix,local",
            "KIMI_BASE_URL": "https://api.moonshot.cn/v1",
            "KIMI_API_KEY": "kimi-key",
            "KIMI_MODEL_ID": "kimi-k2.6",
            "XIAOMI_BASE_URL": "https://api.xiaomi.example/v1",
            "XIAOMI_API_KEY": "xiaomi-key",
            "XIAOMI_MODEL_ID": "mimo-v2.5-pro",
            "AIHUBMIX_BASE_URL": "https://aihubmix.example/v1",
            "AIHUBMIX_API_KEY": "aihubmix-key",
            "AIHUBMIX_MODEL_ID": "glm-4.7-flash-free",
            "LOCAL_MODEL_BASE_URL": "http://127.0.0.1:11434/v1",
            "LOCAL_MODEL_ID": "qwen2.5:7b",
        }

        with patch.dict("os.environ", env, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            get_settings.cache_clear()

        self.assertEqual(
            [candidate.provider for candidate in settings.agent_model_candidates],
            ["kimi", "xiaomi", "aihubmix", "local"],
        )
        self.assertEqual(settings.agent_model_candidates[-1].api_key, "not-needed")


if __name__ == "__main__":
    unittest.main()
