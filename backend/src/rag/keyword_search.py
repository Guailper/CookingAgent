"""Lightweight BM25 keyword scoring for hybrid RAG retrieval."""

from __future__ import annotations

from collections import Counter
import math
import re


class Bm25KeywordScorer:
    """Rank text chunks by lexical overlap with Chinese-friendly tokens."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    def rank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        query_tokens = list(dict.fromkeys(tokenize_keyword_text(query)))
        if not query_tokens or not documents:
            return []

        document_tokens = [tokenize_keyword_text(document) for document in documents]
        average_length = sum(len(tokens) for tokens in document_tokens) / len(document_tokens) or 1.0
        document_frequency = {
            token: sum(1 for tokens in document_tokens if token in tokens)
            for token in query_tokens
        }

        scored_documents: list[tuple[int, float]] = []
        for index, tokens in enumerate(document_tokens):
            score = self._score_document(
                query_tokens=query_tokens,
                document_tokens=tokens,
                document_frequency=document_frequency,
                document_count=len(documents),
                average_length=average_length,
            )
            if score > 0:
                scored_documents.append((index, score))

        return sorted(scored_documents, key=lambda item: (-item[1], item[0]))[: max(1, top_k)]

    def _score_document(
        self,
        *,
        query_tokens: list[str],
        document_tokens: list[str],
        document_frequency: dict[str, int],
        document_count: int,
        average_length: float,
    ) -> float:
        term_frequency = Counter(document_tokens)
        document_length = len(document_tokens)
        score = 0.0
        for token in query_tokens:
            frequency = term_frequency.get(token, 0)
            if not frequency:
                continue

            frequency_in_corpus = document_frequency[token]
            inverse_frequency = math.log(
                1 + (document_count - frequency_in_corpus + 0.5) / (frequency_in_corpus + 0.5)
            )
            normalization = frequency + self.k1 * (
                1 - self.b + self.b * document_length / average_length
            )
            score += inverse_frequency * frequency * (self.k1 + 1) / normalization

        return score


def tokenize_keyword_text(text: str) -> list[str]:
    """Generate English tokens and Chinese n-grams without external analyzers."""

    tokens: list[str] = []
    for match in re.finditer(r"[a-zA-Z0-9]+(?:[-_.][a-zA-Z0-9]+)*|[\u4e00-\u9fff]+", text.lower()):
        value = match.group(0)
        if not _is_chinese_sequence(value):
            tokens.append(value)
            continue

        # 菜名和食材通常很短；同时保留完整词、单字和二元组可覆盖用户简写。
        tokens.append(value)
        tokens.extend(value)
        tokens.extend(value[index : index + 2] for index in range(len(value) - 1))

    return tokens


def _is_chinese_sequence(text: str) -> bool:
    return bool(text) and all("\u4e00" <= character <= "\u9fff" for character in text)
