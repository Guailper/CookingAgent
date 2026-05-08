"""RAG search tool adapter."""

from agent.contracts import AgentTurnContext
from agent.prompts.rag_prompts import render_retrieved_chunks
from src.core.config import Settings, get_settings
from src.core.exceptions import AppException
from src.core.logging import get_logger
from src.rag.retriever import RagRetriever

logger = get_logger(__name__)


def build_rag_search_tool(context: AgentTurnContext):
    """Create a per-turn RAG search tool."""

    def rag_search(query: str) -> str:
        """Search selected user knowledge bases for context snippets."""

        settings = get_settings()
        knowledge_base_ids = _resolve_knowledge_base_ids(context, settings)
        if not knowledge_base_ids:
            return "本轮没有启用知识库，因此没有执行 RAG 检索。"

        top_k = _resolve_top_k(context)
        try:
            chunks = RagRetriever(settings).retrieve(
                query=query,
                knowledge_base_public_ids=knowledge_base_ids,
                final_top_k=top_k,
            )
        except AppException as exc:
            logger.warning(
                "RAG search is unavailable.",
                extra={"code": exc.code, "message": exc.message},
            )
            return (
                "知识库检索暂不可用，无法基于已选择知识库回答。"
                f"原因：{exc.message}"
            )
        except Exception as exc:
            logger.exception("Unexpected RAG search failure.", exc_info=exc)
            return "知识库检索执行失败，当前无法使用知识库片段回答。"

        if not chunks:
            return (
                "没有检索到与问题足够相关的知识库片段。"
                "请基于这一事实回答，不要编造知识库来源。"
            )

        return render_retrieved_chunks(chunks)

    return rag_search


def _resolve_knowledge_base_ids(
    context: AgentTurnContext,
    settings: Settings,
) -> list[str]:
    merged_ids: list[str] = []
    for public_id in [
        *context.knowledge_base_public_ids,
        *settings.rag_default_knowledge_base_ids,
    ]:
        normalized_id = (public_id or "").strip()
        if normalized_id and normalized_id not in merged_ids:
            merged_ids.append(normalized_id)

    return merged_ids


def _resolve_top_k(context: AgentTurnContext) -> int | None:
    raw_top_k = context.request_options.get("top_k")
    if raw_top_k is None:
        return None

    try:
        return max(1, int(raw_top_k))
    except (TypeError, ValueError):
        return None
