"""Optional rerank client for improving vector search order."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from src.core.config import Settings
from src.core.device import resolve_compute_device
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RerankResult:
    """Rerank score bound to the original candidate index."""

    index: int
    score: float


class RerankClient:
    """Rerank candidates with local HuggingFace models or an API endpoint."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local_client = None

    def is_enabled(self) -> bool:
        if self.settings.rag_rerank_provider == "local_huggingface":
            return bool(self.settings.rag_rerank_model_path) and Path(
                self.settings.rag_rerank_model_path
            ).exists()

        return bool(self.settings.rag_rerank_base_url and self.settings.rag_rerank_api_key)

    def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        """Return reranked indexes; failures are logged and treated as disabled."""

        if not self.is_enabled() or not documents:
            return []

        if self.settings.rag_rerank_provider == "local_huggingface":
            return self._rerank_with_local_model(query, documents)

        return self._rerank_with_api(query, documents)

    def _rerank_with_local_model(self, query: str, documents: list[str]) -> list[RerankResult]:
        pairs = [[query, document] for document in documents]

        try:
            raw_scores = self._get_local_client().compute_score(pairs)
        except Exception as exc:
            logger.warning("Local RAG rerank failed; falling back to vector scores.", exc_info=exc)
            return []

        if isinstance(raw_scores, (int, float)):
            raw_scores = [raw_scores]

        results = [
            RerankResult(index=index, score=float(score))
            for index, score in enumerate(raw_scores)
        ]
        return sorted(results, key=lambda result: result.score, reverse=True)

    def _get_local_client(self):
        if self._local_client is not None:
            return self._local_client

        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            logger.warning("FlagEmbedding is not installed; local rerank is disabled.", exc_info=exc)
            raise

        device = resolve_compute_device()
        use_fp16 = self.settings.rag_rerank_use_fp16 and device == "cuda"

        # FlagEmbedding 的构造参数在不同版本间有细微差异；优先显式传入 devices，
        # 如果当前版本不支持则回退到通用构造方式，让库自行选择可用设备。
        try:
            self._local_client = FlagReranker(
                self.settings.rag_rerank_model_path,
                use_fp16=use_fp16,
                devices=[device],
            )
        except TypeError:
            try:
                self._local_client = FlagReranker(
                    self.settings.rag_rerank_model_path,
                    use_fp16=use_fp16,
                    device=device,
                )
            except TypeError:
                self._local_client = FlagReranker(
                    self.settings.rag_rerank_model_path,
                    use_fp16=use_fp16,
                )

        return self._local_client

    def _rerank_with_api(self, query: str, documents: list[str]) -> list[RerankResult]:
        url = f"{self.settings.rag_rerank_base_url.rstrip('/')}/rerank"
        payload = {
            "model": self.settings.rag_rerank_model,
            "query": query,
            "documents": documents,
        }
        headers = {"Authorization": f"Bearer {self.settings.rag_rerank_api_key}"}

        try:
            with httpx.Client(timeout=self.settings.rag_request_timeout_seconds) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("RAG rerank failed; falling back to vector scores.", exc_info=exc)
            return []

        return self._parse_api_results(data)

    def _parse_api_results(self, data: dict[str, Any]) -> list[RerankResult]:
        raw_results = data.get("results") or data.get("data") or []
        parsed: list[RerankResult] = []

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            index = item.get("index", item.get("document_index"))
            score = item.get("relevance_score", item.get("score"))
            try:
                parsed.append(RerankResult(index=int(index), score=float(score)))
            except (TypeError, ValueError):
                continue

        return sorted(parsed, key=lambda result: result.score, reverse=True)
