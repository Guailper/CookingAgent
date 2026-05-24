"""High-level RAG retrieval workflow."""

from dataclasses import asdict
import hashlib
import json

from agent.contracts import RetrievedChunk
from src.cache.cache_service import CacheService
from src.core.config import Settings, get_settings
from src.rag.embedding_client import EmbeddingClient
from src.rag.milvus_repository import MilvusChunkRecord, MilvusRagRepository
from src.rag.rerank_client import RerankClient


class RagRetriever:
    """Coordinate embedding, vector recall, optional rerank, and output mapping."""

    def __init__(
        self,
        settings: Settings | None = None,
        embedding_client: EmbeddingClient | None = None,
        repository: MilvusRagRepository | None = None,
        rerank_client: RerankClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = CacheService(self.settings)
        self.embedding_client = embedding_client or EmbeddingClient(self.settings)
        self.repository = repository or MilvusRagRepository(self.settings)
        self.rerank_client = rerank_client or RerankClient(self.settings)

    def retrieve(
        self,
        query: str,
        knowledge_base_public_ids: list[str],
        final_top_k: int | None = None,
        vector_top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve the most useful chunks for a user question."""

        normalized_query = self._normalize_query(query)
        if not normalized_query or not knowledge_base_public_ids:
            return []

        normalized_knowledge_base_ids = self._dedupe_ids(knowledge_base_public_ids)
        resolved_final_top_k = max(1, final_top_k or self.settings.rag_final_top_k)
        resolved_vector_top_k = max(resolved_final_top_k, vector_top_k or self.settings.rag_vector_top_k)
        cache_key = self._retrieve_cache_key(
            query=normalized_query,
            knowledge_base_public_ids=normalized_knowledge_base_ids,
            final_top_k=resolved_final_top_k,
            vector_top_k=resolved_vector_top_k,
        )
        cached_chunks = self.cache.get_json(cache_key)
        if isinstance(cached_chunks, list):
            return [RetrievedChunk(**chunk) for chunk in cached_chunks if isinstance(chunk, dict)]

        query_embedding = self.embedding_client.embed_query(normalized_query)
        candidates = self.repository.search(
            query_embedding=query_embedding,
            knowledge_base_public_ids=normalized_knowledge_base_ids,
            top_k=resolved_vector_top_k,
            min_score=self.settings.rag_min_score,
        )
        candidates = self._dedupe_candidates(candidates)
        if not candidates:
            return []

        ranked_candidates = self._rerank_or_keep_vector_order(normalized_query, candidates)
        chunks = [self._to_retrieved_chunk(record) for record in ranked_candidates[:resolved_final_top_k]]
        self.cache.set_json(
            cache_key,
            [asdict(chunk) for chunk in chunks],
            self.settings.rag_cache_ttl_seconds,
        )
        return chunks

    def _dedupe_candidates(self, candidates: list[MilvusChunkRecord]) -> list[MilvusChunkRecord]:
        """Remove repeated chunks before rerank while keeping the best vector hit."""

        selected_by_key: dict[str, MilvusChunkRecord] = {}
        ordered_keys: list[str] = []
        for candidate in candidates:
            if not candidate.content.strip():
                continue

            key = self._candidate_identity(candidate)
            existing = selected_by_key.get(key)
            if existing is None:
                selected_by_key[key] = candidate
                ordered_keys.append(key)
                continue

            if self._score_value(candidate.score) > self._score_value(existing.score):
                selected_by_key[key] = candidate

        return [selected_by_key[key] for key in ordered_keys]

    def _candidate_identity(self, candidate: MilvusChunkRecord) -> str:
        if candidate.chunk_public_id:
            return f"chunk:{candidate.chunk_public_id}"
        if candidate.document_public_id and candidate.chunk_index is not None:
            return f"document_chunk:{candidate.document_public_id}:{candidate.chunk_index}"

        digest = hashlib.sha256(candidate.content.strip().encode("utf-8")).hexdigest()
        return f"content:{digest}"

    def _score_value(self, score: float | None) -> float:
        return float(score) if score is not None else float("-inf")

    def _rerank_or_keep_vector_order(
        self,
        query: str,
        candidates: list[MilvusChunkRecord],
    ) -> list[MilvusChunkRecord]:
        """Use rerank when configured; otherwise keep Milvus score order."""

        rerank_results = self.rerank_client.rerank(
            query=query,
            documents=[candidate.content for candidate in candidates],
        )
        if not rerank_results:
            return candidates

        by_index = {index: candidate for index, candidate in enumerate(candidates)}
        ranked_records: list[MilvusChunkRecord] = []
        used_indexes: set[int] = set()

        for result in rerank_results:
            candidate = by_index.get(result.index)
            if candidate is None:
                continue

            ranked_records.append(
                MilvusChunkRecord(
                    chunk_public_id=candidate.chunk_public_id,
                    knowledge_base_public_id=candidate.knowledge_base_public_id,
                    document_public_id=candidate.document_public_id,
                    document_title=candidate.document_title,
                    chunk_index=candidate.chunk_index,
                    page_no=candidate.page_no,
                    content=candidate.content,
                    score=result.score,
                    metadata={
                        **candidate.metadata,
                        "vector_score": candidate.score,
                        "rerank_score": result.score,
                    },
                )
            )
            used_indexes.add(result.index)

        # reranker 可能只返回部分候选，未返回的结果继续按向量顺序补齐。
        ranked_records.extend(
            candidate
            for index, candidate in enumerate(candidates)
            if index not in used_indexes
        )
        return ranked_records

    def _to_retrieved_chunk(self, record: MilvusChunkRecord) -> RetrievedChunk:
        metadata = {
            **record.metadata,
            "chunk_public_id": record.chunk_public_id,
            "knowledge_base_public_id": record.knowledge_base_public_id,
            "document_public_id": record.document_public_id,
        }
        return RetrievedChunk(
            content=record.content,
            document_title=record.document_title,
            chunk_index=record.chunk_index,
            page_no=record.page_no,
            score=record.score,
            metadata=metadata,
        )

    def _normalize_query(self, query: str) -> str:
        return " ".join((query or "").split())

    def _dedupe_ids(self, public_ids: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for public_id in public_ids:
            normalized = public_id.strip()
            if normalized and normalized not in seen:
                deduped.append(normalized)
                seen.add(normalized)
        return deduped

    def _retrieve_cache_key(
        self,
        *,
        query: str,
        knowledge_base_public_ids: list[str],
        final_top_k: int,
        vector_top_k: int,
    ) -> str:
        payload = {
            "query": query,
            "knowledge_base_public_ids": knowledge_base_public_ids,
            "final_top_k": final_top_k,
            "vector_top_k": vector_top_k,
            "min_score": self.settings.rag_min_score,
            "collection": self.settings.milvus_collection,
            "embedding_provider": getattr(self.settings, "rag_embedding_provider", ""),
            "embedding_model": getattr(self.settings, "rag_embedding_model", ""),
            "embedding_model_path": getattr(self.settings, "rag_embedding_model_path", ""),
            "rerank_provider": getattr(self.settings, "rag_rerank_provider", ""),
            "rerank_model": getattr(self.settings, "rag_rerank_model", ""),
            "rerank_model_path": getattr(self.settings, "rag_rerank_model_path", ""),
        }
        payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        return self.cache.build_key("rag", "retrieve", digest)
