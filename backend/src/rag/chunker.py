"""Text chunking utilities used before embedding documents."""

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(frozen=True)
class TextChunk:
    """A document chunk ready for embedding and Milvus insertion."""

    content: str
    chunk_index: int
    page_no: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _ParagraphBlock:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _MergedChunk:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TextChunker:
    """Split long Chinese-first documents with semantic boundaries when possible."""

    def __init__(
        self,
        target_size: int = 700,
        max_size: int = 1000,
        overlap_size: int = 100,
    ) -> None:
        self.target_size = max(1, target_size)
        self.max_size = max(self.target_size, max_size)
        self.overlap_size = max(0, min(overlap_size, self.target_size // 2))

    def split(self, text: str, metadata: dict[str, Any] | None = None) -> list[TextChunk]:
        """Return ordered chunks while preserving headings, lists, and recipes."""

        cleaned_text = self._clean_text(text)
        if not cleaned_text:
            return []

        base_metadata = dict(metadata or {})
        paragraph_blocks = self._split_paragraph_blocks(cleaned_text)
        chunks = self._merge_blocks(paragraph_blocks)

        return [
            TextChunk(
                content=chunk.content,
                chunk_index=index,
                page_no=self._coerce_page_no(base_metadata.get("page_no")),
                metadata={**base_metadata, **chunk.metadata},
            )
            for index, chunk in enumerate(chunks)
        ]

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace without destroying paragraph boundaries."""

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _split_paragraph_blocks(self, text: str) -> list[_ParagraphBlock]:
        """Prefer natural paragraph boundaries while tracking Markdown sections."""

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        refined: list[_ParagraphBlock] = []
        heading_stack: list[str] = []

        for paragraph in paragraphs:
            heading = self._extract_markdown_heading(paragraph)
            if heading is not None:
                level, title = heading
                heading_stack = heading_stack[: max(0, level - 1)]
                heading_stack.append(title)

            metadata = self._build_heading_metadata(heading_stack)
            pieces = [paragraph] if len(paragraph) <= self.max_size else self._split_long_paragraph(paragraph)
            refined.extend(_ParagraphBlock(content=piece, metadata=metadata) for piece in pieces)

        return refined

    def _extract_markdown_heading(self, paragraph: str) -> tuple[int, str] | None:
        first_line = paragraph.splitlines()[0].strip()
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", first_line)
        if not match:
            return None

        return len(match.group(1)), match.group(2).strip()

    def _build_heading_metadata(self, heading_stack: list[str]) -> dict[str, Any]:
        if not heading_stack:
            return {}

        return {
            "section_title": heading_stack[-1],
            "heading_path": " > ".join(heading_stack),
        }

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        """Split oversized paragraphs by sentence punctuation with a hard fallback."""

        sentences = [part for part in re.split(r"(?<=[。！？!?；;])", paragraph) if part.strip()]
        pieces: list[str] = []
        current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(sentence) > self.max_size:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(self._hard_split(sentence))
                continue

            candidate = f"{current}{sentence}" if current else sentence
            if len(candidate) <= self.max_size:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                current = sentence

        if current:
            pieces.append(current)

        return pieces or self._hard_split(paragraph)

    def _hard_split(self, text: str) -> list[str]:
        """Guarantee that no chunk exceeds the configured maximum length."""

        return [
            text[start : start + self.max_size].strip()
            for start in range(0, len(text), self.max_size)
            if text[start : start + self.max_size].strip()
        ]

    def _merge_blocks(self, blocks: list[_ParagraphBlock]) -> list[_MergedChunk]:
        """Merge paragraph blocks into target-sized chunks with small overlaps."""

        chunks: list[_MergedChunk] = []
        current_blocks: list[_ParagraphBlock] = []
        current_length = 0

        for block in blocks:
            separator_length = 2 if current_blocks else 0
            candidate_length = current_length + separator_length + len(block.content)

            if current_blocks and candidate_length > self.target_size:
                current_chunk = self._build_merged_chunk(current_blocks)
                chunks.append(current_chunk)
                current_blocks = self._build_overlap_blocks(current_chunk)
                current_length = self._blocks_length(current_blocks)

            current_blocks.append(block)
            current_length += (2 if current_length else 0) + len(block.content)

            if current_length >= self.max_size:
                current_chunk = self._build_merged_chunk(current_blocks)
                chunks.append(current_chunk)
                current_blocks = self._build_overlap_blocks(current_chunk)
                current_length = self._blocks_length(current_blocks)

        if current_blocks:
            chunks.append(self._build_merged_chunk(current_blocks))

        return [chunk for chunk in chunks if chunk.content]

    def _build_merged_chunk(self, blocks: list[_ParagraphBlock]) -> _MergedChunk:
        content = "\n\n".join(block.content for block in blocks).strip()
        return _MergedChunk(content=content, metadata=self._merge_block_metadata(blocks))

    def _merge_block_metadata(self, blocks: list[_ParagraphBlock]) -> dict[str, Any]:
        heading_paths: list[str] = []
        section_titles: list[str] = []
        for block in blocks:
            heading_path = block.metadata.get("heading_path")
            section_title = block.metadata.get("section_title")
            if heading_path and heading_path not in heading_paths:
                heading_paths.append(str(heading_path))
            if section_title:
                section_titles.append(str(section_title))

        metadata: dict[str, Any] = {}
        if section_titles:
            metadata["section_title"] = section_titles[-1]
        if heading_paths:
            metadata["heading_path"] = heading_paths[-1]
            metadata["heading_paths"] = heading_paths
        return metadata

    def _build_overlap_blocks(self, previous_chunk: _MergedChunk) -> list[_ParagraphBlock]:
        """Carry a short suffix forward to improve recall near chunk borders."""

        if self.overlap_size <= 0:
            return []

        overlap = previous_chunk.content[-self.overlap_size :].strip()
        return [_ParagraphBlock(overlap, previous_chunk.metadata)] if overlap else []

    def _blocks_length(self, blocks: list[_ParagraphBlock]) -> int:
        return sum(len(block.content) for block in blocks) + max(0, len(blocks) - 1) * 2

    def _coerce_page_no(self, value: Any) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
