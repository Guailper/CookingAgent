"""Evidence guard and citation attachment for RAG answers."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.contracts import RagContext, RetrievedChunk, WebSearchContext

EXPLICIT_EVIDENCE_TERMS = (
    "根据知识库",
    "依据知识库",
    "知识库里",
    "根据资料",
    "依据资料",
    "参考资料",
    "根据文档",
    "依据文档",
    "文档中",
)


@dataclass(frozen=True)
class CitationValidationResult:
    """Final answer and audit data produced by citation validation."""

    reply_text: str
    status: str
    citations: list[dict[str, str]] = field(default_factory=list)
    refused: bool = False
    appended_text: str = ""

    def to_snapshot(self) -> dict:
        return {
            "status": self.status,
            "refused": self.refused,
            "citations": self.citations,
        }


class CitationValidator:
    """Enforce explicit-evidence requests and attach verified RAG sources."""

    def refuse_without_evidence(
        self,
        query: str,
        rag_context: RagContext,
        web_context: WebSearchContext,
    ) -> CitationValidationResult | None:
        if not self._requires_explicit_evidence(query):
            return None
        if self._has_available_evidence(rag_context, web_context):
            return None

        reply_text = (
            "当前知识库和可用资料中没有检索到足够证据，无法根据资料确认这个问题。"
            "请补充资料、换一个更具体的问法，或允许基于通用烹饪知识回答。"
        )
        return CitationValidationResult(
            reply_text=reply_text,
            status="refused_no_evidence",
            refused=True,
        )

    def validate(
        self,
        reply_text: str,
        rag_context: RagContext,
        web_context: WebSearchContext,
    ) -> CitationValidationResult:
        if rag_context.status == "hit" and rag_context.chunks:
            citations = self._build_knowledge_citations(rag_context.chunks)
            appended_text = self._render_citations(citations)
            return CitationValidationResult(
                reply_text=f"{reply_text.rstrip()}{appended_text}",
                status="verified_knowledge_citations_attached",
                citations=citations,
                appended_text=appended_text,
            )

        if self._claims_knowledge_source(reply_text) and rag_context.status != "hit":
            appended_text = (
                "\n\n引用校验：本轮没有检索到可引用的知识库片段，"
                "以上回答不得视为来自知识库。"
            )
            return CitationValidationResult(
                reply_text=f"{reply_text.rstrip()}{appended_text}",
                status="unsupported_knowledge_citation_corrected",
                appended_text=appended_text,
            )

        return CitationValidationResult(reply_text=reply_text, status="not_required")

    def _requires_explicit_evidence(self, query: str) -> bool:
        normalized_query = " ".join((query or "").split())
        return any(term in normalized_query for term in EXPLICIT_EVIDENCE_TERMS)

    def _has_available_evidence(
        self,
        rag_context: RagContext,
        web_context: WebSearchContext,
    ) -> bool:
        return (rag_context.status == "hit" and bool(rag_context.chunks)) or (
            web_context.status == "hit" and bool(web_context.results)
        )

    def _claims_knowledge_source(self, reply_text: str) -> bool:
        normalized_text = (reply_text or "").replace(" ", "")
        return "来源：知识库" in normalized_text or "来源:知识库" in normalized_text

    def _build_knowledge_citations(self, chunks: list[RetrievedChunk]) -> list[dict[str, str]]:
        citations: list[dict[str, str]] = []
        seen_keys: set[tuple[str, str]] = set()
        for chunk in chunks:
            source_path = str(chunk.metadata.get("source_path") or "").strip()
            title = chunk.document_title or "未知文档"
            section = str(
                chunk.metadata.get("heading_path") or chunk.metadata.get("section_title") or ""
            ).strip()
            citation_key = (source_path or title, section)
            if citation_key in seen_keys:
                continue

            seen_keys.add(citation_key)
            citations.append(
                {
                    "title": title,
                    "source_path": source_path,
                    "section": section,
                }
            )

        return citations

    def _render_citations(self, citations: list[dict[str, str]]) -> str:
        lines = ["", "", "已核验来源："]
        for index, citation in enumerate(citations, start=1):
            location = citation["source_path"] or citation["title"]
            section = f" | 章节：{citation['section']}" if citation["section"] else ""
            lines.append(f"[{index}] {citation['title']} | {location}{section}")
        return "\n".join(lines)
