"""Tests for the ragas evaluation helper script."""

from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.evaluate_rag_with_ragas import (
    FixedTemperatureLangchainLLMWrapper,
    RagasRunSample,
    bind_metric_runtime,
    build_ragas_embeddings,
    load_cases,
    parse_metric_names,
    parse_args,
    resolve_ragas_model_candidate,
)
from src.core.config import AgentModelCandidate
from src.core.config import get_settings


class RagasEvalScriptTests(unittest.TestCase):
    def test_load_cases_uses_default_knowledge_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cases.jsonl"
            path.write_text(
                '{"question":"番茄炒蛋怎么做？","reference":"先炒蛋再炒番茄。"}\n',
                encoding="utf-8",
            )

            cases = load_cases(path, "cookbook")

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].knowledge_base_ids, ["cookbook"])

    def test_run_sample_exports_only_ragas_columns(self) -> None:
        sample = RagasRunSample(
            user_input="蛋炒饭怎么做？",
            retrieved_contexts=["隔夜饭更容易炒散。"],
            response="建议使用隔夜饭。",
            reference="隔夜饭水分少，更适合炒饭。",
            rag_status="hit",
            model_name="test-model",
            chunk_count=1,
            chunk_metadata=[{"chunk_public_id": "chunk_1"}],
            elapsed_seconds=0.1,
        )

        row = sample.to_ragas_row()

        self.assertEqual(
            set(row),
            {"user_input", "retrieved_contexts", "response", "reference"},
        )
        self.assertEqual(row["retrieved_contexts"], ["隔夜饭更容易炒散。"])

    def test_parse_metric_names_trims_empty_values(self) -> None:
        self.assertEqual(
            parse_metric_names("faithfulness, context_recall,"),
            ["faithfulness", "context_recall"],
        )

    def test_parse_args_defaults_ragas_temperature_to_provider_safe_value(self) -> None:
        with unittest.mock.patch("sys.argv", ["evaluate_rag_with_ragas.py"]), unittest.mock.patch.dict(
            "os.environ",
            {
                "RAGAS_TEMPERATURE": "",
                "RAGAS_MAX_WORKERS": "",
                "RAGAS_BATCH_SIZE": "",
                "RAGAS_DISABLE_MODEL_FALLBACK": "",
            },
            clear=False,
        ):
            args = parse_args()

        self.assertEqual(args.ragas_temperature, 0.6)
        self.assertEqual(args.ragas_max_workers, 1)
        self.assertEqual(args.ragas_batch_size, 1)
        self.assertTrue(args.disable_model_fallback)

    def test_build_ragas_embeddings_uses_local_provider_branch(self) -> None:
        settings = unittest.mock.Mock()
        settings.rag_embedding_provider = "local_huggingface"

        with unittest.mock.patch(
            "scripts.evaluate_rag_with_ragas.get_settings",
            return_value=settings,
        ), unittest.mock.patch(
            "scripts.evaluate_rag_with_ragas.build_local_ragas_embeddings",
            return_value="local-embeddings",
        ) as build_local:
            embeddings = build_ragas_embeddings()

        self.assertEqual(embeddings, "local-embeddings")
        build_local.assert_called_once_with(settings)

    def test_settings_default_query_rewrite_temperature_matches_safe_judge_value(self) -> None:
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            get_settings.cache_clear()

        self.assertEqual(settings.rag_query_rewrite_temperature, 0.6)

    def test_bind_metric_runtime_overrides_metric_llm_and_embeddings(self) -> None:
        metric = unittest.mock.Mock()
        metric.llm = "old-llm"
        metric.embeddings = "old-embeddings"

        bind_metric_runtime(metric, judge_llm="judge-llm", embeddings="local-embeddings")

        self.assertEqual(metric.llm, "judge-llm")
        self.assertEqual(metric.embeddings, "local-embeddings")

    def test_resolve_ragas_model_candidate_selects_requested_provider(self) -> None:
        settings = unittest.mock.Mock()
        settings.agent_model_provider = "kimi"
        settings.agent_model_base_url = "https://api.moonshot.cn/v1"
        settings.agent_model_api_key = "kimi-key"
        settings.agent_model_name = "kimi-k2.5"
        settings.agent_model_candidates = [
            AgentModelCandidate("kimi", "https://api.moonshot.cn/v1", "kimi-key", "kimi-k2.5"),
            AgentModelCandidate("aihubmix", "https://aihubmix.com/v1", "mix-key", "glm-4.7-flash-free"),
        ]

        candidate = resolve_ragas_model_candidate(
            settings,
            provider_override="aihubmix",
            model_name_override="gpt-4o-mini",
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.provider, "aihubmix")
        self.assertEqual(candidate.model_name, "gpt-4o-mini")

    def test_fixed_temperature_wrapper_overrides_ragas_temperature(self) -> None:
        class _InnerWrapper:
            def __init__(self, langchain_llm, bypass_temperature=False):
                self.langchain_llm = langchain_llm
                self.bypass_temperature = bypass_temperature
                self.seen_temperature = None

            def generate_text(self, *args, **kwargs):
                self.seen_temperature = kwargs["temperature"]
                return "ok"

            async def agenerate_text(self, *args, **kwargs):
                self.seen_temperature = kwargs["temperature"]
                return "ok"

            async def generate(self, *args, **kwargs):
                self.seen_temperature = kwargs["temperature"]
                return "ok"

            def set_run_config(self, run_config):
                self.run_config = run_config

            def is_finished(self, response):
                return True

        with unittest.mock.patch(
            "ragas.llms.LangchainLLMWrapper",
            _InnerWrapper,
        ):
            wrapper = FixedTemperatureLangchainLLMWrapper(
                langchain_llm=unittest.mock.Mock(),
                fixed_temperature=0.6,
            )
            result = wrapper.generate_text(temperature=0.01)

        self.assertEqual(result, "ok")
        self.assertEqual(wrapper.inner.seen_temperature, 0.6)
        self.assertTrue(wrapper.inner.bypass_temperature)


if __name__ == "__main__":
    unittest.main()
