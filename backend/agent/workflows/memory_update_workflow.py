"""用户长期记忆更新工作流。"""

from dataclasses import dataclass

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from sqlalchemy.orm import Session

from src.core.security import generate_public_id
from src.db.models.memory_item import MemoryItem
from src.repositories.memory_repository import MemoryRepository


@dataclass(frozen=True)
class ExtractedMemory:
    """规则抽取出的单条记忆。"""

    memory_type: str
    content: str
    confidence: float


class MemoryUpdateWorkflow:
    """从用户输入中抽取明确偏好并写入 memory_items。"""

    name = "memory_update_workflow"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.memory_repository = MemoryRepository(db)

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        memories = self._extract_memories(context.user_message_text)
        created_items: list[dict] = []
        duplicate_items: list[dict] = []

        for memory in memories:
            duplicate = self.memory_repository.find_duplicate(
                user_public_id=context.user_public_id,
                memory_type=memory.memory_type,
                content=memory.content,
            )
            if duplicate is not None:
                duplicate_items.append(self._to_snapshot(duplicate))
                continue

            item = MemoryItem(
                public_id=generate_public_id("mem"),
                user_public_id=context.user_public_id,
                conversation_public_id=context.conversation_public_id,
                source_message_public_id=context.trigger_message_public_id,
                memory_type=memory.memory_type,
                content=memory.content,
                confidence=f"{memory.confidence:.2f}",
                extra_metadata={"extractor": "rule"},
            )
            self.memory_repository.create(item)
            created_items.append(self._to_snapshot(item))

        self.db.commit()

        if created_items:
            reply_text = f"已记住 {len(created_items)} 条偏好，后续推荐会优先参考。"
        elif duplicate_items:
            reply_text = "这条偏好之前已经记录过了，后续会继续参考。"
        else:
            reply_text = "我没有识别到明确可长期保存的偏好，请用“记住我...”这类表达告诉我。"

        return AgentTurnResult(
            reply_text=reply_text,
            intent_type=intent.intent_type,
            workflow_name=self.name,
            output_snapshot={
                "reply_type": "workflow_notice",
                "workflow_name": self.name,
                "created_memories": created_items,
                "duplicate_memories": duplicate_items,
                "intent": {
                    "type": intent.intent_type,
                    "confidence": intent.confidence,
                    "source": intent.source,
                    "reason": intent.reason,
                },
            },
        )

    def _extract_memories(self, text: str) -> list[ExtractedMemory]:
        normalized_text = " ".join((text or "").strip().split())
        if not normalized_text:
            return []

        memories: list[ExtractedMemory] = []
        lowered = normalized_text.lower()

        # 这些规则只保存用户明确说出的长期偏好，避免把一次性需求误写入长期记忆。
        if "不吃" in normalized_text or "不能吃" in normalized_text or "忌口" in normalized_text:
            memories.append(ExtractedMemory("diet_restriction", normalized_text, 0.9))
        if "喜欢" in normalized_text or "偏好" in normalized_text or "口味" in normalized_text:
            memories.append(ExtractedMemory("taste_preference", normalized_text, 0.85))
        if "空气炸锅" in normalized_text or "烤箱" in normalized_text or "电饭煲" in normalized_text:
            memories.append(ExtractedMemory("appliance", normalized_text, 0.8))
        if "减脂" in normalized_text or "控糖" in normalized_text or "低脂" in normalized_text:
            memories.append(ExtractedMemory("health_goal", normalized_text, 0.8))
        if "remember" in lowered:
            memories.append(ExtractedMemory("general_preference", normalized_text, 0.75))

        return self._dedupe_memories(memories)

    @staticmethod
    def _dedupe_memories(memories: list[ExtractedMemory]) -> list[ExtractedMemory]:
        deduped: list[ExtractedMemory] = []
        seen: set[tuple[str, str]] = set()
        for memory in memories:
            key = (memory.memory_type, memory.content)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(memory)
        return deduped

    @staticmethod
    def _to_snapshot(item: MemoryItem) -> dict:
        return {
            "public_id": item.public_id,
            "memory_type": item.memory_type,
            "content": item.content,
            "confidence": item.confidence,
        }
