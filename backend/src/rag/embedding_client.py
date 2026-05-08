"""Embedding client wrapper supporting local HuggingFace and API providers."""

from collections.abc import Sequence

from src.core.config import Settings
from src.core.device import resolve_compute_device
from src.core.exceptions import AppException


class EmbeddingClient:
    """Generate query and document embeddings for RAG."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""

        provider = self.settings.rag_embedding_provider
        if provider == "local_huggingface":
            vector = self._get_local_client().encode(
                query,
                normalize_embeddings=self.settings.rag_embedding_normalize,
            )
            return self._to_float_list(vector)

        return list(self._get_api_client().embed_query(query))

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed document chunks in batch."""

        if not texts:
            return []

        provider = self.settings.rag_embedding_provider
        if provider == "local_huggingface":
            vectors = self._get_local_client().encode(
                list(texts),
                normalize_embeddings=self.settings.rag_embedding_normalize,
            )
            return [self._to_float_list(vector) for vector in vectors]

        return [list(vector) for vector in self._get_api_client().embed_documents(list(texts))]

    def _get_local_client(self):
        if self._client is not None:
            return self._client

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise AppException(
                500,
                "RAG_LOCAL_EMBEDDING_DEPENDENCY_MISSING",
                "缺少 sentence-transformers 依赖，无法加载本地 embedding 模型。",
            ) from exc

        self._client = SentenceTransformer(
            self.settings.rag_embedding_model_path,
            device=resolve_compute_device(),
        )
        return self._client

    def _get_api_client(self):
        if self._client is not None:
            return self._client

        if not self.settings.rag_embedding_base_url or not self.settings.rag_embedding_api_key:
            raise AppException(
                503,
                "RAG_EMBEDDING_NOT_CONFIGURED",
                "RAG embedding 模型尚未配置，请补充 RAG_EMBEDDING_BASE_URL 和 RAG_EMBEDDING_API_KEY。",
            )

        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise AppException(
                500,
                "RAG_EMBEDDING_DEPENDENCY_MISSING",
                "缺少 langchain-openai 依赖，无法生成 RAG embedding。",
            ) from exc

        self._client = OpenAIEmbeddings(
            model=self.settings.rag_embedding_model,
            api_key=self.settings.rag_embedding_api_key,
            base_url=self.settings.rag_embedding_base_url.rstrip("/"),
            timeout=self.settings.rag_request_timeout_seconds,
        )
        return self._client

    def _to_float_list(self, vector) -> list[float]:
        """Convert numpy/torch/list vectors into plain floats for Milvus."""

        if hasattr(vector, "tolist"):
            vector = vector.tolist()

        return [float(value) for value in vector]

