"""Use a separately configured small model to gate attachment ingestion."""

from dataclasses import asdict, dataclass
from typing import Any, Literal

from agent.factories.model_factory import build_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.config import AgentModelCandidate, Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

CONTENT_VALIDATION_STATUS_COMPLETED = "completed"
CONTENT_VALIDATION_STATUS_FAILED = "failed"


class ContentValidationModelResult(BaseModel):
    """Structured semantic classification returned by the validation model."""

    accepted: bool = Field(
        description="True only when the document is primarily reusable cooking knowledge."
    )
    category: Literal["cooking_related", "irrelevant", "uncertain"] = Field(
        description="Semantic domain classification for the document."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the classification.")
    reason: str = Field(description="Brief Chinese explanation for the classification.")


@dataclass(frozen=True)
class AttachmentContentValidation:
    """One auditable small-model decision before knowledge-base ingestion."""

    accepted: bool
    category: str
    confidence: float
    reason: str
    status: str
    model_provider: str
    model_name: str
    error_message: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


class AttachmentContentValidationService:
    """Classify attachment content with the dedicated validation model."""

    MAX_DOCUMENT_CHARS = 12000
    MIN_ACCEPT_CONFIDENCE = 0.7

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(self, *, title: str, text: str) -> AttachmentContentValidation:
        """Return a fail-closed semantic classification for an attachment."""

        model_config = self._resolve_model_config()
        try:
            model = build_chat_model(self.settings, model_config, temperature=0.0)
            structured_model = model.with_structured_output(ContentValidationModelResult)
            response = structured_model.invoke(
                [
                    SystemMessage(content=_content_validation_system_prompt()),
                    HumanMessage(content=self._build_document_prompt(title=title, text=text)),
                ]
            )
            classification = _normalize_classification(response)
        except Exception as exc:
            logger.warning("Attachment content validation model failed.", exc_info=exc)
            return AttachmentContentValidation(
                accepted=False,
                category="uncertain",
                confidence=0.0,
                reason="主题校验模型暂时无法完成判定，附件未写入知识库。",
                status=CONTENT_VALIDATION_STATUS_FAILED,
                model_provider=model_config.provider,
                model_name=model_config.model_name,
                error_message=str(exc),
            )

        category = classification.category
        reason = classification.reason.strip()
        if category == "cooking_related" and classification.confidence < self.MIN_ACCEPT_CONFIDENCE:
            category = "uncertain"
            reason = (
                f"模型判断可能相关但置信度不足（{classification.confidence:.2f}）。"
                f"{reason}"
            )

        return AttachmentContentValidation(
            accepted=classification.accepted
            and category == "cooking_related",
            category=category,
            confidence=classification.confidence,
            reason=reason,
            status=CONTENT_VALIDATION_STATUS_COMPLETED,
            model_provider=model_config.provider,
            model_name=model_config.model_name,
        )

    def _resolve_model_config(self) -> AgentModelCandidate:
        """Build an independent model candidate without falling back to the agent model."""

        return AgentModelCandidate(
            provider=(
                str(getattr(self.settings, "content_validation_model_provider", "disabled"))
                .strip()
                .lower()
                or "disabled"
            ),
            base_url=str(
                getattr(self.settings, "content_validation_model_base_url", "")
            ).strip(),
            api_key=str(
                getattr(self.settings, "content_validation_model_api_key", "")
            ).strip(),
            model_name=str(
                getattr(self.settings, "content_validation_model_name", "")
            ).strip(),
        )

    def _build_document_prompt(self, *, title: str, text: str) -> str:
        normalized_title = " ".join((title or "").strip().split())
        normalized_text = (text or "").strip()
        if len(normalized_text) > self.MAX_DOCUMENT_CHARS:
            head_chars = self.MAX_DOCUMENT_CHARS * 2 // 3
            tail_chars = self.MAX_DOCUMENT_CHARS - head_chars
            normalized_text = (
                f"{normalized_text[:head_chars]}\n...[正文截断]...\n"
                f"{normalized_text[-tail_chars:]}"
            )

        return f"文档标题：{normalized_title}\n\n文档正文摘录：\n{normalized_text}"


def _content_validation_system_prompt() -> str:
    return "\n".join(
        [
            "你是 CookingAgent 知识库的附件主题分类器。",
            "请依据文档整体语义判断它是否适合进入做饭知识库，不要按固定关键词机械判定。",
            "cooking_related：以菜谱、烹饪方法、备菜加工、厨房技巧、食材营养或餐食规划为核心的可复用资料。",
            "irrelevant：主题属于财务、办公、编程、文学或其他与烹饪知识无关的资料。",
            "uncertain：文本过短、混杂主题或证据不足，无法可靠确认是否属于做饭知识。",
            "只有 category 为 cooking_related 且你有充分把握时，accepted 才能为 true。",
            "reason 使用简短中文说明理由。",
        ]
    )


def _normalize_classification(response: Any) -> ContentValidationModelResult:
    if isinstance(response, ContentValidationModelResult):
        return response
    return ContentValidationModelResult.model_validate(response)
