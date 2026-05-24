"""RAG context rendering helpers."""

from agent.contracts import RetrievedChunk


def render_retrieved_chunks(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into prompt-friendly plain text."""

    if not chunks:
        return "没有检索到可用的知识库片段。"

    rendered_chunks: list[str] = []
    for chunk in chunks:
        title = chunk.document_title or "未知文档"
        chunk_label = chunk.chunk_index if chunk.chunk_index is not None else "未知"
        page_label = f"][页码: {chunk.page_no}" if chunk.page_no is not None else ""
        score_label = f"][分数: {chunk.score:.4f}" if chunk.score is not None else ""
        source_label = _format_source_label(chunk)
        rendered_chunks.append(
            f"[文档: {title}][块: {chunk_label}{page_label}{score_label}{source_label}]\n"
            f"{chunk.content.strip()}"
        )

    return "\n\n".join(rendered_chunks)


def _format_source_label(chunk: RetrievedChunk) -> str:
    metadata = chunk.metadata or {}
    labels: list[str] = []

    source_path = metadata.get("source_path")
    if source_path:
        labels.append(f"来源: {source_path}")

    section = metadata.get("heading_path") or metadata.get("section_title")
    if section:
        labels.append(f"章节: {section}")

    document_format = metadata.get("document_format")
    if document_format:
        labels.append(f"格式: {document_format}")

    return "".join(f"][{label}" for label in labels)
