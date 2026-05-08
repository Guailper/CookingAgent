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
