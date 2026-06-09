"""用户长期记忆更新工作流。"""

from dataclasses import dataclass
from typing import Any

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from agent.factories.model_factory import build_chat_model
from agent.prompts.system_prompts import build_memory_extraction_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.security import generate_public_id
from src.core.config import Settings, get_settings
from src.core.logging import get_logger
from src.db.models.memory_item import MemoryItem
from src.repositories.memory_repository import MemoryRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExtractedMemory:
    """规则抽取出的单条记忆。"""

    memory_type: str
    content: str
    confidence: float
    source: str = "rule"


class MemoryExtractionItem(BaseModel):
    """Structured output item returned by the LangChain extraction chain."""

    memory_type: str = Field(description="diet_restriction, taste_preference, appliance, health_goal, or general_preference")
    content: str = Field(description="Normalized Chinese memory content")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class MemoryExtractionResult(BaseModel):
    """Structured output envelope for long-term memory extraction."""

    memories: list[MemoryExtractionItem] = Field(default_factory=list)


class MemoryUpdateWorkflow:
    """从用户输入中抽取明确偏好并写入 memory_items。"""

    name = "memory_update_workflow"

    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.memory_repository = MemoryRepository(db)

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        memories = self._extract_memories(context.user_message_text)
        created_items: list[dict] = []
        updated_items: list[dict] = []
        duplicate_items: list[dict] = []
        is_update_request = _looks_like_memory_update_request(context.user_message_text)

        for memory in memories:
            duplicate = self.memory_repository.find_duplicate(
                user_public_id=context.user_public_id,
                memory_type=memory.memory_type,
                content=memory.content,
            )
            if duplicate is not None:
                duplicate_items.append(self._to_snapshot(duplicate))
                continue

            if is_update_request:
                update_target = self.memory_repository.find_latest_by_type(
                    user_public_id=context.user_public_id,
                    memory_type=memory.memory_type,
                )
                if update_target is not None:
                    updated_items.append(
                        self._update_memory_item(update_target, memory, context)
                    )
                    continue

            item = MemoryItem(
                public_id=generate_public_id("mem"),
                user_public_id=context.user_public_id,
                conversation_public_id=context.conversation_public_id,
                source_message_public_id=context.trigger_message_public_id,
                memory_type=memory.memory_type,
                content=memory.content,
                confidence=f"{memory.confidence:.2f}",
                extra_metadata={"extractor": memory.source},
            )
            self.memory_repository.create(item)
            created_items.append(self._to_snapshot(item))

        self.db.commit()

        if updated_items and created_items:
            reply_text = f"已更新 {len(updated_items)} 条偏好，并新记录 {len(created_items)} 条偏好，后续推荐会优先参考。"
        elif updated_items:
            reply_text = f"已更新 {len(updated_items)} 条偏好，后续推荐会优先参考。"
        elif created_items:
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
                "updated_memories": updated_items,
                "duplicate_memories": duplicate_items,
                "intent": {
                    "type": intent.intent_type,
                    "confidence": intent.confidence,
                    "source": intent.source,
                    "reason": intent.reason,
                },
            },
        )

    def _update_memory_item(
        self,
        item: MemoryItem,
        memory: ExtractedMemory,
        context: AgentTurnContext,
    ) -> dict:
        """更新已有记忆，并在 metadata 中保留最近几次旧值，方便后续排查误更新。"""

        previous_snapshot = self._to_snapshot(item)
        previous_metadata = item.extra_metadata if isinstance(item.extra_metadata, dict) else {}
        update_history = list(previous_metadata.get("update_history", []))
        update_history.append(previous_snapshot)

        item.content = memory.content
        item.confidence = f"{memory.confidence:.2f}"
        item.conversation_public_id = context.conversation_public_id
        item.source_message_public_id = context.trigger_message_public_id
        item.extra_metadata = {
            **previous_metadata,
            "extractor": memory.source,
            "last_operation": "update",
            "update_history": update_history[-5:],
        }
        return self._to_snapshot(item)

    def _extract_memories(self, text: str) -> list[ExtractedMemory]:
        normalized_text = " ".join((text or "").strip().split())
        if not normalized_text:
            return []

        extracted_by_model = self._extract_memories_with_langchain(normalized_text)
        if extracted_by_model:
            return self._dedupe_memories(extracted_by_model)

        return self._extract_memories_by_rule(normalized_text)

    def _extract_memories_with_langchain(self, normalized_text: str) -> list[ExtractedMemory]:
        """Extract long-term memories through LangChain structured output."""

        try:
            model = build_chat_model(self.settings)
            structured_model = model.with_structured_output(MemoryExtractionResult)
            response = structured_model.invoke(
                [
                    SystemMessage(content=build_memory_extraction_system_prompt()),
                    HumanMessage(content=normalized_text),
                ]
            )
        except Exception as exc:
            logger.info("LangChain memory extraction failed; using rule fallback.", exc_info=exc)
            return []

        return _normalize_structured_memories(response)

    def _extract_memories_by_rule(self, normalized_text: str) -> list[ExtractedMemory]:
        """Rule fallback for explicit memory commands."""

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


def _normalize_structured_memories(response: Any) -> list[ExtractedMemory]:
    if isinstance(response, MemoryExtractionResult):
        items = response.memories
    elif isinstance(response, dict):
        raw_items = response.get("memories", [])
        items = [
            MemoryExtractionItem.model_validate(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
    else:
        raw_items = getattr(response, "memories", [])
        items = [
            item
            for item in raw_items
            if hasattr(item, "memory_type") and hasattr(item, "content")
        ]

    memories: list[ExtractedMemory] = []
    for item in items:
        memory_type = str(getattr(item, "memory_type", "")).strip()
        content = str(getattr(item, "content", "")).strip()
        if not memory_type or not content:
            continue
        confidence = _normalize_confidence(getattr(item, "confidence", 0.8))
        memories.append(ExtractedMemory(memory_type, content, confidence, "langchain_structured"))

    return memories


def _normalize_confidence(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.8


def _looks_like_memory_update_request(text: str) -> bool:
    normalized_text = " ".join((text or "").strip().lower().split())
    if not normalized_text:
        return False

    update_keywords = (
        "更新",
        "修改",
        "改成",
        "改为",
        "换成",
        "以后改",
        "以后按",
        "现在",
        "从现在起",
        "不再",
        "不用再",
        "update",
        "change",
    )
    memory_keywords = (
        "记忆",
        "记住",
        "偏好",
        "口味",
        "忌口",
        "不吃",
        "喜欢",
        "remember",
    )
    return any(keyword in normalized_text for keyword in update_keywords) and any(
        keyword in normalized_text for keyword in memory_keywords
    )
