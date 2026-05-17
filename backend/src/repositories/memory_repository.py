"""用户长期记忆数据访问。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.memory_item import MemoryItem


class MemoryRepository:
    """封装 memory_items 的读写逻辑。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_duplicate(
        self,
        *,
        user_public_id: str,
        memory_type: str,
        content: str,
    ) -> MemoryItem | None:
        stmt = select(MemoryItem).where(
            MemoryItem.user_public_id == user_public_id,
            MemoryItem.memory_type == memory_type,
            MemoryItem.content == content,
        )
        return self.db.scalar(stmt)

    def create(self, memory_item: MemoryItem) -> MemoryItem:
        self.db.add(memory_item)
        self.db.flush()
        return memory_item

    def list_by_user_public_id(
        self,
        user_public_id: str,
        *,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """Return the latest long-term memories for one user."""

        stmt = (
            select(MemoryItem)
            .where(MemoryItem.user_public_id == user_public_id)
            .order_by(MemoryItem.created_at.desc())
            .limit(max(1, limit))
        )
        return list(self.db.scalars(stmt).all())

    def list_relevant_by_user(
        self,
        *,
        user_public_id: str,
        query: str,
        limit: int = 8,
    ) -> list[MemoryItem]:
        """Return relevant memories using a small deterministic ranking.

        这里先保持数据库实现轻量可控：长期记忆数量通常不大，先按用户取最近记忆，
        再用关键词重叠做本地排序。后续如果记忆规模变大，可以把这个方法替换为
        LangChain retriever + 向量库，而不影响 agent 层调用。
        """

        memories = self.list_by_user_public_id(
            user_public_id,
            limit=max(limit * 4, 20),
        )
        normalized_query = _normalize_text(query)
        if not normalized_query:
            return memories[:limit]

        scored_memories = [
            (_score_memory(memory, normalized_query), index, memory)
            for index, memory in enumerate(memories)
        ]
        scored_memories.sort(key=lambda item: (-item[0], item[1]))
        return [memory for score, _, memory in scored_memories if score > 0][:limit] or memories[:limit]


def _score_memory(memory: MemoryItem, normalized_query: str) -> int:
    content = _normalize_text(memory.content)
    if not content:
        return 0

    score = 0
    if content in normalized_query or normalized_query in content:
        score += 4

    query_tokens = set(normalized_query.split())
    content_tokens = set(content.split())
    score += len(query_tokens & content_tokens)
    return score


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())
