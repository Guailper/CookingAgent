"""Tests for the Milvus RAG module without external network calls."""

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.core.config import get_settings
from src.core.device import resolve_compute_device
from src.rag.chunker import TextChunker
from src.rag.embedding_client import EmbeddingClient
from src.rag.milvus_repository import MilvusChunkRecord
from src.rag.retriever import RagRetriever
from src.rag.rerank_client import RerankClient, RerankResult


class _FakeEmbeddingClient:
    def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeRepository:
    def search(self, query_embedding, knowledge_base_public_ids, top_k, min_score):
        return [
            MilvusChunkRecord(
                chunk_public_id="chunk_1",
                knowledge_base_public_id="kb_1",
                document_public_id="doc_1",
                document_title="米饭处理",
                chunk_index=0,
                content="隔夜米饭更适合炒饭。",
                score=0.62,
            ),
            MilvusChunkRecord(
                chunk_public_id="chunk_2",
                knowledge_base_public_id="kb_1",
                document_public_id="doc_1",
                document_title="鸡蛋处理",
                chunk_index=1,
                content="鸡蛋先打散再下锅。",
                score=0.58,
            ),
        ]


class _FakeRerankClient:
    def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        return [RerankResult(index=1, score=0.95), RerankResult(index=0, score=0.72)]


class RagModuleTests(unittest.TestCase):
    def test_text_chunker_keeps_chunks_under_max_size(self) -> None:
        chunker = TextChunker(target_size=40, max_size=60, overlap_size=10)
        text = "第一段介绍食材。\n\n" + "鸡蛋炒饭需要快速翻炒。" * 8

        chunks = chunker.split(text)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk.content) <= 70 for chunk in chunks))
        self.assertEqual(chunks[0].chunk_index, 0)

    def test_retriever_applies_rerank_order(self) -> None:
        settings = SimpleNamespace(
            rag_vector_top_k=20,
            rag_final_top_k=2,
            rag_min_score=0.25,
        )
        retriever = RagRetriever(
            settings=settings,
            embedding_client=_FakeEmbeddingClient(),
            repository=_FakeRepository(),
            rerank_client=_FakeRerankClient(),
        )

        chunks = retriever.retrieve("鸡蛋炒饭", ["kb_1"])

        self.assertEqual([chunk.document_title for chunk in chunks], ["鸡蛋处理", "米饭处理"])
        self.assertEqual(chunks[0].score, 0.95)
        self.assertEqual(chunks[0].metadata["vector_score"], 0.58)

    def test_settings_resolves_local_model_paths_from_project_root(self) -> None:
        env = {
            "RAG_EMBEDDING_PROVIDER": "local_huggingface",
            "RAG_EMBEDDING_MODEL_PATH": "models/test-embedding",
            "RAG_RERANK_PROVIDER": "local_huggingface",
            "RAG_RERANK_MODEL_PATH": "models/test-reranker",
        }

        with patch.dict("os.environ", env, clear=False):
            get_settings.cache_clear()
            settings = get_settings()
            get_settings.cache_clear()

        self.assertTrue(settings.rag_embedding_model_path.endswith("models\\test-embedding"))
        self.assertTrue(settings.rag_rerank_model_path.endswith("models\\test-reranker"))

    def test_resolve_compute_device_returns_cuda_when_torch_reports_cuda(self) -> None:
        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: True)
        )

        with patch.dict(sys.modules, {"torch": fake_torch}):
            self.assertEqual(resolve_compute_device(), "cuda")

    def test_local_embedding_client_uses_sentence_transformer(self) -> None:
        calls = {}

        class _FakeSentenceTransformer:
            def __init__(self, model_path, device):
                calls["model_path"] = model_path
                calls["device"] = device

            def encode(self, texts, normalize_embeddings):
                calls["normalize"] = normalize_embeddings
                if isinstance(texts, str):
                    return [1, 2, 3]
                return [[1, 2, 3] for _ in texts]

        fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
        settings = SimpleNamespace(
            rag_embedding_provider="local_huggingface",
            rag_embedding_model_path="models/local-embedding",
            rag_embedding_normalize=True,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}), patch(
            "src.rag.embedding_client.resolve_compute_device",
            return_value="cpu",
        ):
            client = EmbeddingClient(settings)
            vector = client.embed_query("query")

        self.assertEqual(vector, [1.0, 2.0, 3.0])
        self.assertEqual(calls["model_path"], "models/local-embedding")
        self.assertEqual(calls["device"], "cpu")
        self.assertTrue(calls["normalize"])

    def test_local_rerank_client_uses_flag_embedding_and_disables_fp16_on_cpu(self) -> None:
        calls = {}

        class _FakeFlagReranker:
            def __init__(self, model_path, use_fp16, devices=None, device=None):
                calls["model_path"] = model_path
                calls["use_fp16"] = use_fp16
                calls["devices"] = devices
                calls["device"] = device

            def compute_score(self, pairs):
                return [0.2, 0.8]

        fake_module = types.SimpleNamespace(FlagReranker=_FakeFlagReranker)
        settings = SimpleNamespace(
            rag_rerank_provider="local_huggingface",
            rag_rerank_model_path="models/local-reranker",
            rag_rerank_use_fp16=True,
        )

        with patch.dict(sys.modules, {"FlagEmbedding": fake_module}), patch(
            "src.rag.rerank_client.resolve_compute_device",
            return_value="cpu",
        ), patch(
            "src.rag.rerank_client.Path.exists",
            return_value=True,
        ):
            results = RerankClient(settings).rerank("query", ["doc1", "doc2"])

        self.assertEqual([result.index for result in results], [1, 0])
        self.assertFalse(calls["use_fp16"])
        self.assertEqual(calls["devices"], ["cpu"])


if __name__ == "__main__":
    unittest.main()
