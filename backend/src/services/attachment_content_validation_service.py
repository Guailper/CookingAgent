"""Use a separately configured small model to gate attachment ingestion."""

from dataclasses import asdict, dataclass
from typing import Any, Literal

from agent.factories.model_factory import build_chat_model
from agent.prompts.system_prompts import (
    build_content_validation_document_prompt,
    build_content_validation_system_prompt,
)
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.config import AgentModelCandidate, Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

CONTENT_VALIDATION_STATUS_COMPLETED = "completed"
CONTENT_VALIDATION_STATUS_FAILED = "failed"
RESUME_SECTION_MARKERS = (
    "教育背景",
    "工作经历",
    "项目经历",
    "实习经历",
    "获奖经历",
    "个人技能",
    "专业技能",
    "求职意向",
    "自我评价",
)


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
        irrelevant_reason = _detect_high_confidence_irrelevant_content(text)
        if irrelevant_reason:
            return AttachmentContentValidation(
                accepted=False,
                category="irrelevant",
                confidence=1.0,
                reason=irrelevant_reason,
                status=CONTENT_VALIDATION_STATUS_COMPLETED,
                model_provider=model_config.provider,
                model_name=model_config.model_name,
            )

        try:
            model = build_chat_model(self.settings, model_config, temperature=0.0)
            structured_model = model.with_structured_output(
                ContentValidationModelResult,
                method=(
                    "json_mode"
                    if model_config.provider == "local"
                    else "json_schema"
                ),
            )
            system_prompt = build_content_validation_system_prompt()
            if model_config.provider == "local":
                system_prompt += (
                    "\nReturn only a valid JSON object with accepted, category, "
                    "confidence, and reason."
                )
            response = structured_model.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=build_content_validation_document_prompt(
                            title=title,
                            text=text,
                            max_document_chars=self.MAX_DOCUMENT_CHARS,
                        )
                    ),
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

def _normalize_classification(response: Any) -> ContentValidationModelResult:
    if isinstance(response, ContentValidationModelResult):
        return response
    return ContentValidationModelResult.model_validate(response)


def _detect_high_confidence_irrelevant_content(text: str) -> str | None:
    """Reject document structures that are clearly unrelated before model classification."""

    normalized_text = (text or "").strip()
    matched_resume_sections = [
        marker for marker in RESUME_SECTION_MARKERS if marker in normalized_text
    ]
    if len(matched_resume_sections) >= 3:
        evidence = "、".join(matched_resume_sections[:4])
        return f"正文检测到明确的简历结构（{evidence}），不属于烹饪知识资料。"

    return None
