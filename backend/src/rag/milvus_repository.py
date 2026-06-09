"""Milvus persistence adapter for RAG chunks."""

from dataclasses import dataclass, field
import json
from typing import Any

from src.core.config import Settings
from src.core.exceptions import AppException
from src.rag.keyword_search import Bm25KeywordScorer


@dataclass(frozen=True)
class MilvusChunkRecord:
    """A chunk row stored in or retrieved from Milvus."""

    chunk_public_id: str
    knowledge_base_public_id: str
    document_public_id: str
    document_title: str | None
    chunk_index: int
    content: str
    embedding: list[float] = field(default_factory=list)
    page_no: int | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MilvusRagRepository:
    """Small wrapper around MilvusClient so the rest of RAG stays testable."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def ensure_collection(self, vector_dim: int) -> None:
        """Create the chunk collection when it does not already exist."""

        client = self._get_client()
        collection_name = self.settings.milvus_collection
        if client.has_collection(collection_name):
            return

        from pymilvus import DataType

        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("chunk_public_id", DataType.VARCHAR, max_length=128)
        schema.add_field("knowledge_base_public_id", DataType.VARCHAR, max_length=128)
        schema.add_field("document_public_id", DataType.VARCHAR, max_length=128)
        schema.add_field("document_title", DataType.VARCHAR, max_length=512)
        schema.add_field("chunk_index", DataType.INT64)
        schema.add_field("page_no", DataType.INT64)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("metadata_json", DataType.VARCHAR, max_length=65535)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=vector_dim)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )

        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
            consistency_level="Strong",
        )

    def drop_collection_if_exists(self) -> bool:
        """Drop the configured collection when rebuilding local RAG data."""

        client = self._get_client()
        collection_name = self.settings.milvus_collection
        if not client.has_collection(collection_name):
            return False

        client.drop_collection(collection_name)
        return True

    def upsert_chunks(self, records: list[MilvusChunkRecord]) -> None:
        """Replace one document's chunks so retries do not create duplicates."""

        if not records:
            return

        vector_dim = len(records[0].embedding)
        if vector_dim <= 0:
            raise AppException(400, "RAG_EMPTY_EMBEDDING", "写入 Milvus 的向量不能为空。")

        self.ensure_collection(vector_dim)
        self._get_client().delete(
            collection_name=self.settings.milvus_collection,
            filter=self._build_document_filter(
                records[0].knowledge_base_public_id,
                records[0].document_public_id,
            ),
        )
        rows = [self._record_to_row(record) for record in records]
        self._get_client().insert(
            collection_name=self.settings.milvus_collection,
            data=rows,
        )

    def delete_document(
        self,
        knowledge_base_public_id: str,
        document_public_id: str,
    ) -> bool:
        """Delete all chunks for one document when it is no longer eligible."""

        client = self._get_client()
        collection_name = self.settings.milvus_collection
        if not client.has_collection(collection_name):
            return False

        client.delete(
            collection_name=collection_name,
            filter=self._build_document_filter(
                knowledge_base_public_id,
                document_public_id,
            ),
        )
        return True

    def search(
        self,
        query_embedding: list[float],
        knowledge_base_public_ids: list[str],
        top_k: int,
        min_score: float,
    ) -> list[MilvusChunkRecord]:
        """Search selected knowledge bases and return normalized records."""

        if not knowledge_base_public_ids:
            return []

        if not query_embedding:
            raise AppException(400, "RAG_EMPTY_QUERY_EMBEDDING", "检索向量不能为空。")

        client = self._get_client()
        collection_name = self.settings.milvus_collection
        if not client.has_collection(collection_name):
            return []

        results = client.search(
            collection_name=collection_name,
            data=[query_embedding],
            anns_field="embedding",
            limit=max(1, top_k),
            filter=self._build_filter(knowledge_base_public_ids),
            output_fields=[
                "chunk_public_id",
                "knowledge_base_public_id",
                "document_public_id",
                "document_title",
                "chunk_index",
                "page_no",
                "content",
                "metadata_json",
            ],
            search_params={"metric_type": "COSINE"},
        )

        records: list[MilvusChunkRecord] = []
        for item in results[0] if results else []:
            score = self._extract_score(item)
            if score is not None and score < min_score:
                continue

            entity = item.get("entity", item)
            records.append(self._row_to_record(entity, score))

        return records

    def search_keywords(
        self,
        query: str,
        knowledge_base_public_ids: list[str],
        top_k: int,
        scan_limit: int,
    ) -> list[MilvusChunkRecord]:
        """Recall keyword-matching chunks for hybrid retrieval without a schema migration."""

        normalized_query = " ".join((query or "").split())
        if not normalized_query or not knowledge_base_public_ids:
            return []

        client = self._get_client()
        collection_name = self.settings.milvus_collection
        if not client.has_collection(collection_name):
            return []

        rows = client.query(
            collection_name=collection_name,
            filter=self._build_filter(knowledge_base_public_ids),
            output_fields=[
                "chunk_public_id",
                "knowledge_base_public_id",
                "document_public_id",
                "document_title",
                "chunk_index",
                "page_no",
                "content",
                "metadata_json",
            ],
            limit=max(top_k, scan_limit),
        )
        ranked_matches = Bm25KeywordScorer().rank(
            normalized_query,
            [str(row.get("content") or "") for row in rows],
            top_k=top_k,
        )
        return [self._row_to_record(rows[index], score) for index, score in ranked_matches]

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise AppException(
                500,
                "RAG_MILVUS_DEPENDENCY_MISSING",
                "缺少 pymilvus 依赖，无法连接 Milvus。",
            ) from exc

        try:
            self._client = MilvusClient(
                uri=self.settings.milvus_uri,
                token=self.settings.milvus_token or None,
                db_name=self.settings.milvus_database or "default",
                timeout=getattr(self.settings, "rag_request_timeout_seconds", 30),
            )
        except Exception as exc:
            raise AppException(
                503,
                "RAG_MILVUS_UNAVAILABLE",
                f"Milvus 服务不可用，请检查 MILVUS_URI={self.settings.milvus_uri} 并确认服务已启动。",
            ) from exc
        return self._client

    def _record_to_row(self, record: MilvusChunkRecord) -> dict[str, Any]:
        row = {
            "chunk_public_id": record.chunk_public_id,
            "knowledge_base_public_id": record.knowledge_base_public_id,
            "document_public_id": record.document_public_id,
            "document_title": record.document_title or "",
            "chunk_index": record.chunk_index,
            "page_no": record.page_no or 0,
            "content": record.content,
            "metadata_json": json.dumps(record.metadata, ensure_ascii=False),
            "embedding": record.embedding,
        }
        return row

    def _row_to_record(self, row: dict[str, Any], score: float | None) -> MilvusChunkRecord:
        metadata_json = row.get("metadata_json") or "{}"
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}

        page_no = row.get("page_no")
        return MilvusChunkRecord(
            chunk_public_id=str(row.get("chunk_public_id", "")),
            knowledge_base_public_id=str(row.get("knowledge_base_public_id", "")),
            document_public_id=str(row.get("document_public_id", "")),
            document_title=str(row.get("document_title") or "") or None,
            chunk_index=int(row.get("chunk_index") or 0),
            page_no=int(page_no) if page_no else None,
            content=str(row.get("content") or ""),
            score=score,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _build_filter(self, knowledge_base_public_ids: list[str]) -> str:
        values = json.dumps(knowledge_base_public_ids, ensure_ascii=False)
        return f"knowledge_base_public_id in {values}"

    def _build_document_filter(
        self,
        knowledge_base_public_id: str,
        document_public_id: str,
    ) -> str:
        knowledge_base_value = json.dumps(knowledge_base_public_id, ensure_ascii=False)
        document_value = json.dumps(document_public_id, ensure_ascii=False)
        return (
            f"knowledge_base_public_id == {knowledge_base_value} "
            f"and document_public_id == {document_value}"
        )

    def _extract_score(self, item: dict[str, Any]) -> float | None:
        raw_score = item.get("distance", item.get("score"))
        if raw_score is None:
            return None

        try:
            return float(raw_score)
        except (TypeError, ValueError):
            return None
