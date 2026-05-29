"""Evaluate the project RAG pipeline with ragas.

The script reuses CookingAgent's own retrieval and answer generation code, then
converts each run into the single-turn sample shape expected by ragas.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, field, replace
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agent.contracts import AgentTurnContext, WebSearchContext
from agent.factories.model_factory import build_chat_model
from agent.rag.context_builder import RagContextBuilder
from agent.runner import LangChainAgentRunner
from agent.web.context_builder import WebSearchContextBuilder
from src.core.config import AgentModelCandidate, get_settings
from src.core.device import resolve_compute_device


DEFAULT_METRICS = [
    "faithfulness",
    "context_precision",
    "context_recall",
    "response_relevancy",
    "answer_correctness",
]


@dataclass(frozen=True)
class RagasEvalCase:
    """One manually curated RAG evaluation case."""

    question: str
    reference: str
    knowledge_base_ids: list[str]
    expected_source_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RagasRunSample:
    """One project pipeline run converted to ragas-compatible fields."""

    user_input: str
    retrieved_contexts: list[str]
    response: str
    reference: str
    rag_status: str
    model_name: str | None
    chunk_count: int
    chunk_metadata: list[dict[str, Any]]
    elapsed_seconds: float
    expected_source_paths: list[str] = field(default_factory=list)
    retrieval_metrics: dict[str, float] = field(default_factory=dict)

    def to_ragas_row(self) -> dict[str, Any]:
        return {
            "user_input": self.user_input,
            "retrieved_contexts": self.retrieved_contexts,
            "response": self.response,
            "reference": self.reference,
        }


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases_path, args.default_knowledge_base_id)
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No evaluation cases were loaded.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    samples = run_project_pipeline(
        cases,
        include_web_search=args.include_web_search,
        disable_model_fallback=args.disable_model_fallback,
    )
    samples_path = save_run_samples(samples, args.output_dir)
    print(f"Saved project RAG samples: {samples_path}")
    retrieval_report_path = save_retrieval_report(samples, args.output_dir)
    if retrieval_report_path is not None:
        print(f"Saved retrieval metrics: {retrieval_report_path}")

    if args.skip_evaluate:
        print("Skipped ragas scoring because --skip-evaluate was provided.")
        return

    metrics = parse_metric_names(args.metrics)
    scores_path = evaluate_with_ragas(
        samples,
        metrics,
        args.output_dir,
        ragas_temperature=args.ragas_temperature,
        ragas_model_provider=args.ragas_model_provider,
        ragas_model_name=args.ragas_model_name,
        ragas_max_workers=args.ragas_max_workers,
        ragas_max_retries=args.ragas_max_retries,
        ragas_max_wait=args.ragas_max_wait,
        ragas_batch_size=args.ragas_batch_size,
    )
    print(f"Saved ragas scores: {scores_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CookingAgent RAG cases and score them with ragas.",
    )
    parser.add_argument(
        "--cases-path",
        type=Path,
        default=BACKEND_ROOT / "eval" / "ragas_cases.jsonl",
        help="JSONL file containing question/reference evaluation cases.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BACKEND_ROOT / "eval" / "ragas_results",
        help="Directory for generated samples and ragas score files.",
    )
    parser.add_argument(
        "--default-knowledge-base-id",
        default="cookbook",
        help="Knowledge base id used when a case does not specify one.",
    )
    parser.add_argument(
        "--metrics",
        default=",".join(DEFAULT_METRICS),
        help=f"Comma-separated ragas metric names. Defaults to: {', '.join(DEFAULT_METRICS)}.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases.")
    parser.add_argument(
        "--include-web-search",
        action="store_true",
        help="Also build web-search fallback context. Disabled by default to isolate RAG quality.",
    )
    parser.add_argument(
        "--skip-evaluate",
        action="store_true",
        help="Only generate ragas-compatible samples; do not call ragas.evaluate().",
    )
    parser.add_argument(
        "--ragas-temperature",
        type=float,
        default=read_float_env("RAGAS_TEMPERATURE", 0.6),
        help="Temperature used by the ragas judge LLM. Some providers only allow 0.6.",
    )
    parser.add_argument(
        "--ragas-model-provider",
        default=os.getenv("RAGAS_MODEL_PROVIDER", "").strip(),
        help="Optional judge model provider. Defaults to the primary agent model provider.",
    )
    parser.add_argument(
        "--ragas-model-name",
        default=os.getenv("RAGAS_MODEL_NAME", "").strip(),
        help="Optional judge model name. Defaults to the selected provider model.",
    )
    parser.add_argument(
        "--disable-model-fallback",
        action=argparse.BooleanOptionalAction,
        default=read_bool_env("RAGAS_DISABLE_MODEL_FALLBACK", True),
        help="Use only the primary agent model while generating evaluation answers.",
    )
    parser.add_argument(
        "--ragas-max-workers",
        type=int,
        default=read_int_env("RAGAS_MAX_WORKERS", 1),
        help="Maximum concurrent ragas jobs. Keep this low for RPM-limited model providers.",
    )
    parser.add_argument(
        "--ragas-max-retries",
        type=int,
        default=read_int_env("RAGAS_MAX_RETRIES", 10),
        help="Maximum retries for transient ragas job failures such as 429 rate limits.",
    )
    parser.add_argument(
        "--ragas-max-wait",
        type=int,
        default=read_int_env("RAGAS_MAX_WAIT", 60),
        help="Maximum retry wait seconds used by ragas RunConfig.",
    )
    parser.add_argument(
        "--ragas-batch-size",
        type=int,
        default=read_int_env("RAGAS_BATCH_SIZE", 1),
        help="Batch size passed to ragas.evaluate(). Use 1 for strict RPM limits.",
    )
    return parser.parse_args()


def read_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        return default


def read_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def read_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()
    if not normalized_value:
        return default

    return normalized_value in {"1", "true", "yes", "on"}


def load_cases(path: Path, default_knowledge_base_id: str) -> list[RagasEvalCase]:
    if not path.exists():
        raise SystemExit(f"Evaluation case file does not exist: {path}")

    cases: list[RagasEvalCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue

        raw_case = json.loads(line)
        question = str(raw_case.get("question", "")).strip()
        reference = str(raw_case.get("reference", "")).strip()
        knowledge_base_ids = raw_case.get("knowledge_base_ids") or [default_knowledge_base_id]
        expected_source_paths = raw_case.get("expected_source_paths")
        if expected_source_paths is None:
            source_path = str(raw_case.get("source_path", "")).strip()
            expected_source_paths = [source_path] if source_path else []
        if not question or not reference:
            raise SystemExit(f"Case line {line_number} must include question and reference.")
        if not isinstance(knowledge_base_ids, list):
            raise SystemExit(f"Case line {line_number} knowledge_base_ids must be a list.")
        if not isinstance(expected_source_paths, list):
            raise SystemExit(f"Case line {line_number} expected_source_paths must be a list.")

        cases.append(
            RagasEvalCase(
                question=question,
                reference=reference,
                knowledge_base_ids=[str(item).strip() for item in knowledge_base_ids if str(item).strip()],
                expected_source_paths=[
                    str(item).strip() for item in expected_source_paths if str(item).strip()
                ],
            )
        )

    return cases


def run_project_pipeline(
    cases: list[RagasEvalCase],
    *,
    include_web_search: bool,
    disable_model_fallback: bool,
) -> list[RagasRunSample]:
    base_settings = get_settings()
    primary_candidate = resolve_primary_model_candidate(base_settings)
    settings = replace(
        base_settings,
        agent_model_candidates=(
            [primary_candidate]
            if disable_model_fallback and primary_candidate is not None
            else base_settings.agent_model_candidates
        ),
    )
    rag_context_builder = RagContextBuilder(settings)
    web_context_builder = WebSearchContextBuilder(settings)
    runner = LangChainAgentRunner(settings)

    samples: list[RagasRunSample] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] Running case: {case.question}")
        started_at = time.perf_counter()
        context = build_turn_context(case)
        rag_context = rag_context_builder.build(context)

        # 默认关闭联网回退，使 ragas 的 retrieved_contexts 与模型回答保持同一来源。
        web_context = (
            web_context_builder.build(context, rag_context)
            if include_web_search
            else WebSearchContext(enabled=False, status="disabled", query=case.question)
        )

        result = runner.run(
            replace(
                context,
                rag_context=rag_context,
                web_search_context=web_context,
            )
        )
        chunk_metadata = [chunk.metadata for chunk in rag_context.chunks]
        samples.append(
            RagasRunSample(
                user_input=case.question,
                retrieved_contexts=[chunk.content for chunk in rag_context.chunks],
                response=result.reply_text,
                reference=case.reference,
                rag_status=rag_context.status,
                model_name=result.model_name,
                chunk_count=len(rag_context.chunks),
                chunk_metadata=chunk_metadata,
                elapsed_seconds=time.perf_counter() - started_at,
                expected_source_paths=case.expected_source_paths,
                retrieval_metrics=compute_retrieval_metrics(
                    case.expected_source_paths,
                    chunk_metadata,
                ),
            )
        )

    return samples


def build_turn_context(case: RagasEvalCase) -> AgentTurnContext:
    return AgentTurnContext(
        conversation_public_id=f"eval_conv_{uuid4().hex}",
        user_public_id="eval_user",
        trigger_message_public_id=f"eval_msg_{uuid4().hex}",
        user_message_text=case.question,
        knowledge_base_public_ids=case.knowledge_base_ids,
    )


def save_run_samples(samples: list[RagasRunSample], output_dir: Path) -> Path:
    path = output_dir / f"samples_{build_run_id()}.jsonl"
    with path.open("w", encoding="utf-8") as file:
        for sample in samples:
            file.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")
    return path


def compute_retrieval_metrics(
    expected_source_paths: list[str],
    chunk_metadata: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute per-case source-document retrieval metrics at the returned K."""

    expected_paths = {
        normalized_path
        for path in expected_source_paths
        if (normalized_path := _normalize_source_path(path))
    }
    if not expected_paths:
        return {}

    retrieved_paths = [
        normalized_path
        for metadata in chunk_metadata
        if (normalized_path := _normalize_source_path(str(metadata.get("source_path", ""))))
    ]
    matched_paths = expected_paths.intersection(retrieved_paths)
    first_match_rank = next(
        (rank for rank, source_path in enumerate(retrieved_paths, start=1) if source_path in expected_paths),
        None,
    )
    return {
        "hit_at_k": 1.0 if matched_paths else 0.0,
        "recall_at_k": len(matched_paths) / len(expected_paths),
        "reciprocal_rank": 1.0 / first_match_rank if first_match_rank is not None else 0.0,
    }


def summarize_retrieval_metrics(samples: list[RagasRunSample]) -> dict[str, float | int]:
    """Average retrieval metrics over cases that declare expected sources."""

    scored_metrics = [sample.retrieval_metrics for sample in samples if sample.retrieval_metrics]
    if not scored_metrics:
        return {"case_count": 0, "hit_at_k": 0.0, "recall_at_k": 0.0, "mrr": 0.0}

    case_count = len(scored_metrics)
    return {
        "case_count": case_count,
        "hit_at_k": sum(metrics["hit_at_k"] for metrics in scored_metrics) / case_count,
        "recall_at_k": sum(metrics["recall_at_k"] for metrics in scored_metrics) / case_count,
        "mrr": sum(metrics["reciprocal_rank"] for metrics in scored_metrics) / case_count,
    }


def save_retrieval_report(samples: list[RagasRunSample], output_dir: Path) -> Path | None:
    """Save deterministic retrieval metrics alongside the LLM-based RAGAS report."""

    summary = summarize_retrieval_metrics(samples)
    if summary["case_count"] == 0:
        return None

    path = output_dir / f"retrieval_metrics_{build_run_id()}.json"
    payload = {
        "summary": summary,
        "cases": [
            {
                "user_input": sample.user_input,
                "expected_source_paths": sample.expected_source_paths,
                "retrieval_metrics": sample.retrieval_metrics,
            }
            for sample in samples
            if sample.retrieval_metrics
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _normalize_source_path(path: str) -> str:
    normalized_path = path.replace("\\", "/").strip().lstrip("./")
    if normalized_path.startswith("data/"):
        normalized_path = normalized_path[len("data/") :]
    return normalized_path


def evaluate_with_ragas(
    samples: list[RagasRunSample],
    metric_names: list[str],
    output_dir: Path,
    *,
    ragas_temperature: float,
    ragas_model_provider: str,
    ragas_model_name: str,
    ragas_max_workers: int,
    ragas_max_retries: int,
    ragas_max_wait: int,
    ragas_batch_size: int,
) -> Path:
    try:
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.run_config import RunConfig
    except ImportError as exc:
        raise SystemExit(
            "ragas is not installed. Install backend/requirements.txt or rerun with --skip-evaluate."
        ) from exc

    ragas_samples = [
        SingleTurnSample(**sample.to_ragas_row())
        for sample in samples
    ]
    dataset = EvaluationDataset(samples=ragas_samples)
    judge_llm = build_ragas_llm(
        ragas_temperature,
        provider_override=ragas_model_provider,
        model_name_override=ragas_model_name,
    )
    embeddings = build_ragas_embeddings()
    metrics = resolve_metrics(metric_names, judge_llm=judge_llm, embeddings=embeddings)
    run_config = RunConfig(
        max_workers=max(1, ragas_max_workers),
        max_retries=max(0, ragas_max_retries),
        max_wait=max(1, ragas_max_wait),
    )
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=embeddings,
        run_config=run_config,
        batch_size=max(1, ragas_batch_size),
        raise_exceptions=False,
    )

    dataframe = result.to_pandas()
    path = output_dir / f"scores_{build_run_id()}.csv"
    dataframe.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    return path


def resolve_metrics(
    metric_names: list[str],
    *,
    judge_llm: Any | None = None,
    embeddings: Any | None = None,
) -> list[Any]:
    from ragas import metrics as ragas_metrics

    resolved_metrics: list[Any] = []
    for name in metric_names:
        metric = resolve_metric(ragas_metrics, name)
        bind_metric_runtime(metric, judge_llm=judge_llm, embeddings=embeddings)
        resolved_metrics.append(metric)
    return resolved_metrics


def bind_metric_runtime(
    metric: Any,
    *,
    judge_llm: Any | None,
    embeddings: Any | None,
) -> None:
    """Force every ragas metric to use the same project-selected runtime.

    Some ragas versions expose metrics as module-level objects. Passing llm and
    embeddings to evaluate() is normally enough, but explicitly binding them
    here avoids version-specific defaults leaking model parameters such as
    temperature.
    """

    if judge_llm is not None and hasattr(metric, "llm"):
        metric.llm = judge_llm
    if embeddings is not None and hasattr(metric, "embeddings"):
        metric.embeddings = embeddings


def resolve_metric(ragas_metrics: Any, name: str) -> Any:
    metric_factories = {
        "faithfulness": ("Faithfulness", "faithfulness"),
        "context_precision": ("LLMContextPrecisionWithReference", "context_precision"),
        "context_recall": ("LLMContextRecall", "context_recall"),
        "response_relevancy": ("ResponseRelevancy", "answer_relevancy"),
        "answer_relevancy": ("ResponseRelevancy", "answer_relevancy"),
        "answer_correctness": ("AnswerCorrectness", "answer_correctness"),
    }
    candidates = metric_factories.get(name)
    if candidates is None:
        raise SystemExit(f"Unsupported metric: {name}")

    for candidate in candidates:
        metric_or_factory = getattr(ragas_metrics, candidate, None)
        if metric_or_factory is None:
            continue
        return metric_or_factory() if isinstance(metric_or_factory, type) else metric_or_factory

    raise SystemExit(f"Metric {name} is not available in the installed ragas version.")


def build_ragas_llm(
    temperature: float,
    *,
    provider_override: str = "",
    model_name_override: str = "",
) -> Any | None:
    try:
        from ragas.llms import LangchainLLMWrapper
    except ImportError:
        return None

    settings = get_settings()
    candidate = resolve_ragas_model_candidate(
        settings,
        provider_override=provider_override,
        model_name_override=model_name_override,
    )
    if candidate is None:
        return None

    model = build_ragas_chat_model(settings, candidate, temperature)
    return FixedTemperatureLangchainLLMWrapper(model, fixed_temperature=temperature)


class FixedTemperatureLangchainLLMWrapper:
    """Keep ragas requests within provider-specific generation constraints."""

    def __init__(
        self,
        langchain_llm: Any,
        fixed_temperature: float,
        wrapper_factory: Any | None = None,
    ) -> None:
        if wrapper_factory is None:
            from ragas.llms import LangchainLLMWrapper

            wrapper_factory = LangchainLLMWrapper
        self.fixed_temperature = fixed_temperature
        self.inner = wrapper_factory(
            langchain_llm,
            bypass_temperature=True,
            bypass_n=True,
        )
        self.langchain_llm = langchain_llm

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def generate_text(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["temperature"] = self.fixed_temperature
        return self.inner.generate_text(*args, **kwargs)

    async def agenerate_text(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["temperature"] = self.fixed_temperature
        return await self.inner.agenerate_text(*args, **kwargs)

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["temperature"] = self.fixed_temperature
        return await self.inner.generate(*args, **kwargs)

    def set_run_config(self, run_config: Any) -> None:
        self.inner.set_run_config(run_config)

    def is_finished(self, response: Any) -> bool:
        return self.inner.is_finished(response)


def resolve_primary_model_candidate(settings: Any) -> AgentModelCandidate | None:
    if settings.agent_model_candidates:
        return settings.agent_model_candidates[0]

    if not settings.agent_model_base_url or not settings.agent_model_name:
        return None

    return AgentModelCandidate(
        provider=settings.agent_model_provider,
        base_url=settings.agent_model_base_url,
        api_key=settings.agent_model_api_key,
        model_name=settings.agent_model_name,
    )


def resolve_ragas_model_candidate(
    settings: Any,
    *,
    provider_override: str,
    model_name_override: str,
) -> AgentModelCandidate | None:
    provider = (provider_override or settings.agent_model_provider).strip().lower()
    candidates = [
        *(settings.agent_model_candidates or []),
        AgentModelCandidate(
            provider=settings.agent_model_provider,
            base_url=settings.agent_model_base_url,
            api_key=settings.agent_model_api_key,
            model_name=settings.agent_model_name,
        ),
    ]

    for candidate in candidates:
        if candidate.provider.strip().lower() != provider:
            continue
        return replace(
            candidate,
            model_name=(model_name_override or candidate.model_name).strip(),
        )

    return None


def build_ragas_chat_model(settings: Any, model_config: Any, temperature: float) -> Any:
    # Keep provider handling (for example Kimi's thinking/temperature pair), but
    # do not truncate judge rationales with the answer model's short output cap.
    judge_settings = replace(settings, agent_max_output_tokens=0)
    return build_chat_model(judge_settings, model_config, temperature=temperature)


def build_ragas_embeddings() -> Any | None:
    settings = get_settings()
    if settings.rag_embedding_provider == "local_huggingface":
        return build_local_ragas_embeddings(settings)

    if not settings.rag_embedding_base_url or not settings.rag_embedding_api_key:
        return None

    modern_embeddings = build_modern_ragas_embeddings(settings)
    if modern_embeddings is not None:
        return modern_embeddings

    return build_legacy_langchain_embeddings(settings)


def build_local_ragas_embeddings(settings: Any) -> Any | None:
    # The installed RAGAS relevance metrics still call the LangChain-style
    # embed_query API, while its modern HuggingFace adapter exposes embed_text.
    compatible_embeddings = build_legacy_local_langchain_embeddings(settings)
    if compatible_embeddings is not None:
        return compatible_embeddings

    device = resolve_compute_device()
    return build_modern_local_ragas_embeddings(settings, device)


def build_modern_local_ragas_embeddings(settings: Any, device: str) -> Any | None:
    try:
        from ragas import embeddings as ragas_embeddings
    except ImportError:
        return None

    # ragas 0.3+ 提供 HuggingFaceEmbeddings；部分 0.2/0.3 版本还保留
    # HuggingfaceEmbeddings。这里兼容两种命名和构造参数，优先走非 LangChain wrapper。
    constructors = [
        (
            getattr(ragas_embeddings, "HuggingFaceEmbeddings", None),
            {
                "model": settings.rag_embedding_model_path,
                "device": device,
                "normalize_embeddings": settings.rag_embedding_normalize,
            },
        ),
        (
            getattr(ragas_embeddings, "HuggingfaceEmbeddings", None),
            {
                "model_name": settings.rag_embedding_model_path,
                "model_kwargs": {"device": device},
                "encode_kwargs": {
                    "normalize_embeddings": settings.rag_embedding_normalize,
                },
            },
        ),
    ]
    for constructor, kwargs in constructors:
        if constructor is None:
            continue
        try:
            return constructor(**kwargs)
        except TypeError:
            continue

    return None


def build_legacy_local_langchain_embeddings(settings: Any) -> Any | None:
    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError:
        return None

    from src.rag.embedding_client import EmbeddingClient

    return LangchainEmbeddingsWrapper(ProjectLocalEmbeddings(EmbeddingClient(settings)))


class ProjectLocalEmbeddings:
    """LangChain-compatible adapter over the project's local embedding client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def embed_query(self, text: str) -> list[float]:
        return self.client.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)


def build_modern_ragas_embeddings(settings: Any) -> Any | None:
    try:
        from openai import OpenAI
        from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
    except ImportError:
        return None

    client = OpenAI(
        api_key=settings.rag_embedding_api_key,
        base_url=settings.rag_embedding_base_url.rstrip("/"),
        timeout=settings.rag_request_timeout_seconds,
    )
    for kwargs in (
        {"client": client, "model": settings.rag_embedding_model},
        {"client": client, "model_name": settings.rag_embedding_model},
        {"openai_client": client, "model": settings.rag_embedding_model},
    ):
        try:
            return RagasOpenAIEmbeddings(**kwargs)
        except TypeError:
            continue

    return None


def build_legacy_langchain_embeddings(settings: Any) -> Any | None:
    try:
        from langchain_openai import OpenAIEmbeddings
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError:
        return None

    embeddings = OpenAIEmbeddings(
        model=settings.rag_embedding_model,
        api_key=settings.rag_embedding_api_key,
        base_url=settings.rag_embedding_base_url.rstrip("/"),
        timeout=settings.rag_request_timeout_seconds,
    )
    return LangchainEmbeddingsWrapper(embeddings)


def parse_metric_names(raw_metrics: str) -> list[str]:
    metric_names = [item.strip() for item in raw_metrics.split(",") if item.strip()]
    return metric_names or DEFAULT_METRICS


def build_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    main()
