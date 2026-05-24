"""Tests for the Milvus RAG module without external network calls."""

import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.contracts import RetrievedChunk
from agent.prompts.rag_prompts import render_retrieved_chunks
from src.core.config import get_settings
from src.core.device import resolve_compute_device
from src.core.exceptions import AppException
from src.rag.chunker import TextChunker
from src.rag.document_loader import iter_supported_files, load_rag_documents_from_path
from src.rag.embedding_client import EmbeddingClient
from src.rag.milvus_repository import MilvusChunkRecord, MilvusRagRepository
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


class _DisabledRerankClient:
    def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        return []


class _DuplicateRepository:
    def __init__(self) -> None:
        self.seen_top_k = None

    def search(self, query_embedding, knowledge_base_public_ids, top_k, min_score):
        self.seen_top_k = top_k
        return [
            MilvusChunkRecord(
                chunk_public_id="chunk_dup",
                knowledge_base_public_id="kb_1",
                document_public_id="doc_1",
                document_title="重复低分",
                chunk_index=0,
                content="同一片段内容",
                score=0.4,
            ),
            MilvusChunkRecord(
                chunk_public_id="chunk_dup",
                knowledge_base_public_id="kb_1",
                document_public_id="doc_1",
                document_title="重复高分",
                chunk_index=0,
                content="同一片段内容",
                score=0.8,
            ),
            MilvusChunkRecord(
                chunk_public_id="chunk_unique",
                knowledge_base_public_id="kb_1",
                document_public_id="doc_1",
                document_title="唯一片段",
                chunk_index=1,
                content="另一个片段",
                score=0.7,
            ),
        ]


class RagModuleTests(unittest.TestCase):
    def test_text_chunker_keeps_chunks_under_max_size(self) -> None:
        chunker = TextChunker(target_size=40, max_size=60, overlap_size=10)
        text = "第一段介绍食材。\n\n" + "鸡蛋炒饭需要快速翻炒。" * 8

        chunks = chunker.split(text)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk.content) <= 70 for chunk in chunks))
        self.assertEqual(chunks[0].chunk_index, 0)

    def test_text_chunker_attaches_markdown_heading_metadata(self) -> None:
        chunker = TextChunker(target_size=36, max_size=80, overlap_size=0)
        text = "# 番茄炒蛋\n\n## 食材\n西红柿 2 个，鸡蛋 3 个。\n\n## 步骤\n先炒蛋，再炒番茄。"

        chunks = chunker.split(text, metadata={"source_path": "recipes/番茄炒蛋.md"})

        ingredient_chunk = next(chunk for chunk in chunks if "西红柿 2 个" in chunk.content)
        step_chunk = next(chunk for chunk in chunks if "先炒蛋" in chunk.content)
        self.assertEqual(ingredient_chunk.metadata["heading_path"], "番茄炒蛋 > 食材")
        self.assertEqual(step_chunk.metadata["section_title"], "步骤")
        self.assertEqual(step_chunk.metadata["source_path"], "recipes/番茄炒蛋.md")

    def test_render_retrieved_chunks_includes_source_section_and_format(self) -> None:
        rendered = render_retrieved_chunks(
            [
                RetrievedChunk(
                    content="先炒蛋，再炒番茄。",
                    document_title="番茄炒蛋",
                    chunk_index=1,
                    score=0.88,
                    metadata={
                        "source_path": "recipes/番茄炒蛋.json",
                        "heading_path": "番茄炒蛋 > 步骤",
                        "document_format": "json",
                    },
                )
            ]
        )

        self.assertIn("[来源: recipes/番茄炒蛋.json]", rendered)
        self.assertIn("[章节: 番茄炒蛋 > 步骤]", rendered)
        self.assertIn("[格式: json]", rendered)

    def test_document_loader_supports_recipe_text_json_jsonl_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "番茄炒蛋.md").write_text("# 番茄炒蛋\n\n先炒蛋再炒番茄。", encoding="utf-8")
            (data_dir / "tips.txt").write_text("米饭提前冷藏更适合炒饭。", encoding="utf-8")
            (data_dir / "recipes.json").write_text(
                """
                [
                  {
                    "name": "凉拌黄瓜",
                    "ingredients": ["黄瓜 2 根", "蒜 3 瓣"],
                    "steps": ["拍黄瓜", "加调料拌匀"]
                  }
                ]
                """,
                encoding="utf-8",
            )
            (data_dir / "soups.jsonl").write_text(
                '{"菜名":"紫菜蛋花汤","食材":"紫菜；鸡蛋","步骤":["煮汤","淋蛋液"]}\n',
                encoding="utf-8",
            )
            (data_dir / "quick.csv").write_text(
                "title,ingredients,steps\n手撕包菜,包菜；干辣椒,撕菜；大火快炒\n",
                encoding="utf-8",
            )

            loaded_files = iter_supported_files(data_dir)
            documents = [
                document
                for path in loaded_files
                for document in load_rag_documents_from_path(path, data_dir, "cookbook")
            ]

        self.assertEqual(len(loaded_files), 5)
        self.assertEqual(len(documents), 5)
        self.assertEqual(
            {document.metadata["document_format"] for document in documents},
            {"md", "txt", "json", "jsonl", "csv"},
        )
        cucumber = next(document for document in documents if document.title == "凉拌黄瓜")
        tomato_egg = next(document for document in documents if document.title == "番茄炒蛋")
        self.assertIn("## 食材", cucumber.text)
        self.assertIn("1. 拍黄瓜", cucumber.text)
        self.assertEqual(tomato_egg.metadata["document_format"], "md")

    def test_project_multi_format_recipe_data_is_loadable(self) -> None:
        project_root = Path(__file__).resolve().parents[3]
        data_dir = project_root / "data" / "recipes_multi_format"

        loaded_files = iter_supported_files(data_dir)
        documents = [
            document
            for path in loaded_files
            for document in load_rag_documents_from_path(path, data_dir, "cookbook")
        ]

        self.assertEqual(len(loaded_files), 5)
        self.assertEqual(len(documents), 7)
        self.assertEqual(
            {document.metadata["document_format"] for document in documents},
            {"md", "txt", "json", "jsonl", "csv"},
        )
        self.assertTrue(any(document.title == "紫菜蛋花汤" for document in documents))

    def test_retriever_applies_rerank_order(self) -> None:
        settings = SimpleNamespace(
            rag_vector_top_k=20,
            rag_final_top_k=2,
            rag_min_score=0.25,
            rag_cache_ttl_seconds=0,
            milvus_collection="rag_chunks",
            redis_key_prefix="test",
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
        self.assertEqual(chunks[0].metadata["rerank_score"], 0.95)

    def test_retriever_dedupes_candidates_and_keeps_vector_top_k_above_final_top_k(self) -> None:
        repository = _DuplicateRepository()
        settings = SimpleNamespace(
            rag_vector_top_k=1,
            rag_final_top_k=3,
            rag_min_score=0.25,
            rag_cache_ttl_seconds=0,
            milvus_collection="rag_chunks",
            redis_key_prefix="test",
        )
        retriever = RagRetriever(
            settings=settings,
            embedding_client=_FakeEmbeddingClient(),
            repository=repository,
            rerank_client=_DisabledRerankClient(),
        )

        chunks = retriever.retrieve("重复片段", ["kb_1"], final_top_k=3, vector_top_k=1)

        self.assertEqual(repository.seen_top_k, 3)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].document_title, "重复高分")
        self.assertEqual(chunks[0].score, 0.8)

    def test_retriever_cache_key_changes_when_rerank_model_changes(self) -> None:
        settings = SimpleNamespace(
            rag_min_score=0.25,
            milvus_collection="rag_chunks",
            redis_key_prefix="test",
            rag_embedding_provider="local_huggingface",
            rag_embedding_model="",
            rag_embedding_model_path="models/embedding-a",
            rag_rerank_provider="local_huggingface",
            rag_rerank_model="",
            rag_rerank_model_path="models/reranker-a",
        )
        retriever = RagRetriever(
            settings=settings,
            embedding_client=_FakeEmbeddingClient(),
            repository=_FakeRepository(),
            rerank_client=_DisabledRerankClient(),
        )

        first_key = retriever._retrieve_cache_key(
            query="蛋炒饭",
            knowledge_base_public_ids=["cookbook"],
            final_top_k=5,
            vector_top_k=20,
        )
        settings.rag_rerank_model_path = "models/reranker-b"
        second_key = retriever._retrieve_cache_key(
            query="蛋炒饭",
            knowledge_base_public_ids=["cookbook"],
            final_top_k=5,
            vector_top_k=20,
        )

        self.assertNotEqual(first_key, second_key)

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

    def test_milvus_connection_failure_uses_stable_app_error(self) -> None:
        class _FailingMilvusClient:
            def __init__(self, **kwargs):
                raise TimeoutError("connection timed out")

        fake_module = types.SimpleNamespace(MilvusClient=_FailingMilvusClient)
        settings = SimpleNamespace(
            milvus_uri="http://127.0.0.1:19530",
            milvus_token="",
            milvus_database="default",
            rag_request_timeout_seconds=1,
        )

        with patch.dict(sys.modules, {"pymilvus": fake_module}):
            repository = MilvusRagRepository(settings)

            with self.assertRaises(AppException) as raised:
                repository.search([0.1, 0.2], ["kb_1"], top_k=3, min_score=0.2)

        self.assertEqual(raised.exception.code, "RAG_MILVUS_UNAVAILABLE")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("127.0.0.1:19530", raised.exception.message)

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
