"""Document indexing workflow for RAG knowledge bases."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from src.core.config import Settings, get_settings
from src.rag.chunker import TextChunker
from src.rag.embedding_client import EmbeddingClient
from src.rag.milvus_repository import MilvusChunkRecord, MilvusRagRepository


@dataclass(frozen=True)
class RagDocument:
    """Plain-text document input for RAG indexing."""

    knowledge_base_public_id: str
    document_public_id: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RagIndexingService:
    """Chunk, embed, and store documents in Milvus."""

    def __init__(
        self,
        settings: Settings | None = None,
        chunker: TextChunker | None = None,
        embedding_client: EmbeddingClient | None = None,
        repository: MilvusRagRepository | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.chunker = chunker or TextChunker(
            target_size=self.settings.rag_chunk_target_size,
            max_size=self.settings.rag_chunk_max_size,
            overlap_size=self.settings.rag_chunk_overlap_size,
        )
        self.embedding_client = embedding_client or EmbeddingClient(self.settings)
        self.repository = repository or MilvusRagRepository(self.settings)

    def index_document(self, document: RagDocument) -> int:
        """Index one document and return the number of stored chunks."""

        chunks = self.chunker.split(document.text, metadata=document.metadata)
        if not chunks:
            return 0

        embeddings = self.embedding_client.embed_documents([chunk.content for chunk in chunks])
        records = [
            MilvusChunkRecord(
                chunk_public_id=self._new_chunk_public_id(),
                knowledge_base_public_id=document.knowledge_base_public_id,
                document_public_id=document.document_public_id,
                document_title=document.title,
                chunk_index=chunk.chunk_index,
                page_no=chunk.page_no,
                content=chunk.content,
                embedding=embedding,
                metadata=chunk.metadata,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        self.repository.upsert_chunks(records)
        return len(records)

    def delete_document(
        self,
        knowledge_base_public_id: str,
        document_public_id: str,
    ) -> bool:
        """Remove a document that no longer passes ingestion validation."""

        return self.repository.delete_document(
            knowledge_base_public_id,
            document_public_id,
        )

    def _new_chunk_public_id(self) -> str:
        return f"rag_chunk_{uuid4().hex}"
