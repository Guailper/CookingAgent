"""Build structured RAG context before answer generation."""

from agent.contracts import AgentTurnContext, RagContext, RetrievedChunk
from src.core.config import Settings, get_settings
from src.core.exceptions import AppException
from src.core.logging import get_logger
from src.rag.retriever import RagRetriever

logger = get_logger(__name__)


class RagContextBuilder:
    """Run backend-default retrieval for every answer turn."""

    def __init__(
        self,
        settings: Settings | None = None,
        retriever: RagRetriever | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or RagRetriever(self.settings)

    def build(self, context: AgentTurnContext) -> RagContext:
        knowledge_base_ids = self._resolve_knowledge_base_ids(context)
        query = (context.user_message_text or "").strip()

        if not knowledge_base_ids:
            return RagContext(
                enabled=False,
                status="disabled",
                query=query,
                knowledge_base_public_ids=[],
            )

        try:
            chunks = self.retriever.retrieve(
                query=query,
                knowledge_base_public_ids=knowledge_base_ids,
                final_top_k=self.settings.rag_final_top_k,
            )
        except AppException as exc:
            logger.warning(
                "Default RAG retrieval failed.",
                extra={"code": exc.code, "message": exc.message},
            )
            return RagContext(
                enabled=True,
                status="error",
                query=query,
                knowledge_base_public_ids=knowledge_base_ids,
                error_code=exc.code,
                error_message=exc.message,
            )
        except Exception as exc:
            logger.exception("Unexpected default RAG retrieval failure.", exc_info=exc)
            return RagContext(
                enabled=True,
                status="error",
                query=query,
                knowledge_base_public_ids=knowledge_base_ids,
                error_code="RAG_RETRIEVAL_FAILED",
                error_message=str(exc),
            )

        return RagContext(
            enabled=True,
            status="hit" if chunks else "miss",
            query=query,
            knowledge_base_public_ids=knowledge_base_ids,
            chunks=chunks,
        )

    def _resolve_knowledge_base_ids(self, context: AgentTurnContext) -> list[str]:
        merged_ids: list[str] = []
        for public_id in [
            *context.knowledge_base_public_ids,
            *self.settings.rag_default_knowledge_base_ids,
        ]:
            normalized_id = (public_id or "").strip()
            if normalized_id and normalized_id not in merged_ids:
                merged_ids.append(normalized_id)

        return merged_ids


def rag_context_to_snapshot(rag_context: RagContext | None) -> dict:
    if rag_context is None:
        return {"enabled": False, "status": "disabled", "chunk_count": 0}

    return {
        "enabled": rag_context.enabled,
        "status": rag_context.status,
        "query": rag_context.query,
        "knowledge_base_public_ids": rag_context.knowledge_base_public_ids,
        "chunk_count": len(rag_context.chunks),
        "chunks": [_chunk_to_snapshot(chunk) for chunk in rag_context.chunks],
        "error_code": rag_context.error_code,
        "error_message": rag_context.error_message,
    }


def _chunk_to_snapshot(chunk: RetrievedChunk) -> dict:
    return {
        "document_public_id": chunk.metadata.get("document_public_id"),
        "document_title": chunk.document_title,
        "chunk_index": chunk.chunk_index,
        "page_no": chunk.page_no,
        "score": chunk.score,
        "chunk_public_id": chunk.metadata.get("chunk_public_id"),
    }
