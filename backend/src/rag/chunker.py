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

        base_metadata = metadata or {}
        paragraphs = self._split_paragraphs(cleaned_text)
        chunks = self._merge_paragraphs(paragraphs)

        return [
            TextChunk(
                content=chunk,
                chunk_index=index,
                page_no=self._coerce_page_no(base_metadata.get("page_no")),
                metadata=dict(base_metadata),
            )
            for index, chunk in enumerate(chunks)
        ]

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace without destroying paragraph boundaries."""

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _split_paragraphs(self, text: str) -> list[str]:
        """Prefer natural paragraph boundaries, then sentence boundaries."""

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        refined: list[str] = []

        for paragraph in paragraphs:
            if len(paragraph) <= self.max_size:
                refined.append(paragraph)
                continue

            refined.extend(self._split_long_paragraph(paragraph))

        return refined

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

    def _merge_paragraphs(self, paragraphs: list[str]) -> list[str]:
        """Merge paragraphs into target-sized chunks with small overlaps."""

        chunks: list[str] = []
        current_parts: list[str] = []
        current_length = 0

        for paragraph in paragraphs:
            separator_length = 2 if current_parts else 0
            candidate_length = current_length + separator_length + len(paragraph)

            if current_parts and candidate_length > self.target_size:
                current_chunk = "\n\n".join(current_parts).strip()
                chunks.append(current_chunk)
                current_parts = self._build_overlap_parts(current_chunk)
                current_length = sum(len(part) for part in current_parts) + max(0, len(current_parts) - 1) * 2

            current_parts.append(paragraph)
            current_length += (2 if current_length else 0) + len(paragraph)

            if current_length >= self.max_size:
                current_chunk = "\n\n".join(current_parts).strip()
                chunks.append(current_chunk)
                current_parts = self._build_overlap_parts(current_chunk)
                current_length = sum(len(part) for part in current_parts) + max(0, len(current_parts) - 1) * 2

        if current_parts:
            chunks.append("\n\n".join(current_parts).strip())

        return [chunk for chunk in chunks if chunk]

    def _build_overlap_parts(self, previous_chunk: str) -> list[str]:
        """Carry a short suffix forward to improve recall near chunk borders."""

        if self.overlap_size <= 0:
            return []

        overlap = previous_chunk[-self.overlap_size :].strip()
        return [overlap] if overlap else []

    def _coerce_page_no(self, value: Any) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
