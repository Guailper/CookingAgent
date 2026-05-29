"""融合规则和本地模型的高层动作意图识别。"""

from dataclasses import dataclass
from typing import Any, Literal

from agent.contracts import ActionIntent, AgentTurnContext
from agent.factories.model_factory import build_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from src.core.config import AgentModelCandidate, Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

INTENT_ANSWER = "answer"
INTENT_ATTACHMENT_PARSE = "attachment_parse"
INTENT_DOCUMENT_INGEST = "document_ingest"
INTENT_MEMORY_UPDATE = "memory_update"
INTENT_UNSUPPORTED = "unsupported"
SUPPORTED_INTENTS = (
    INTENT_ANSWER,
    INTENT_ATTACHMENT_PARSE,
    INTENT_DOCUMENT_INGEST,
    INTENT_MEMORY_UPDATE,
)
SIDE_EFFECT_ATTACHMENT_INTENTS = {
    INTENT_ATTACHMENT_PARSE,
    INTENT_DOCUMENT_INGEST,
}


class ModelIntentResult(BaseModel):
    """本地模型返回的结构化意图识别结果。"""

    intent_type: Literal[
        "answer",
        "attachment_parse",
        "document_ingest",
        "memory_update",
    ] = Field(description="One of the supported high-level action intents.")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(description="Brief Chinese explanation for the decision.")


@dataclass(frozen=True)
class IntentPrediction:
    """一次意图识别来源给出的候选结果。"""

    intent_type: str
    confidence: float
    source: str
    reason: str
    available: bool = True
    error_message: str | None = None


class ActionIntentResolver:
    """只识别“做什么动作”，不把普通回答和 RAG 回答拆开。

    规则和本地模型会分别给出候选意图，再按配置权重融合。附件解析和文档入库
    仍需要规则侧明确命中，避免模型误判触发有副作用的动作。
    RAG 是否执行由 AnswerWorkflow 内部的 RetrievalPolicy 决定，不属于这里的动作意图。
    """

    def __init__(
        self,
        settings: Settings | None = None,
        model_classifier: "LocalModelIntentClassifier | None" = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_classifier = model_classifier or LocalModelIntentClassifier(self.settings)

    def resolve(self, context: AgentTurnContext) -> ActionIntent:
        rule_prediction = self._resolve_by_rule(context)
        model_prediction = self.model_classifier.predict(context)

        if not model_prediction.available:
            return ActionIntent(
                intent_type=rule_prediction.intent_type,
                confidence=rule_prediction.confidence,
                source=rule_prediction.source,
                reason=_build_model_unavailable_reason(rule_prediction, model_prediction),
            )

        fused_scores = _build_fused_scores(
            rule_prediction=rule_prediction,
            model_prediction=model_prediction,
            rule_weight=self.settings.intent_rule_weight,
            model_weight=self.settings.intent_model_weight,
        )
        intent_type = _select_best_intent(
            fused_scores,
            context=context,
            rule_prediction=rule_prediction,
        )
        confidence = fused_scores.get(intent_type, 0.0)

        return ActionIntent(
            intent_type=intent_type,
            confidence=confidence,
            source="hybrid",
            reason=_build_hybrid_reason(
                intent_type=intent_type,
                rule_prediction=rule_prediction,
                model_prediction=model_prediction,
                fused_scores=fused_scores,
                rule_weight=self.settings.intent_rule_weight,
                model_weight=self.settings.intent_model_weight,
            ),
        )

    def _resolve_by_rule(self, context: AgentTurnContext) -> IntentPrediction:
        text = _normalize_text(context.user_message_text)

        if context.attachment_public_ids and _contains_any(text, DOCUMENT_INGEST_KEYWORDS):
            return IntentPrediction(
                intent_type=INTENT_DOCUMENT_INGEST,
                confidence=1.0,
                source="rule",
                reason="用户明确要求把附件内容写入知识库。",
            )

        if context.attachment_public_ids and _contains_any(text, ATTACHMENT_PARSE_KEYWORDS):
            return IntentPrediction(
                intent_type=INTENT_ATTACHMENT_PARSE,
                confidence=0.95,
                source="rule",
                reason="用户明确要求解析、读取或提取附件内容。",
            )

        if _contains_any(text, MEMORY_UPDATE_KEYWORDS):
            return IntentPrediction(
                intent_type=INTENT_MEMORY_UPDATE,
                confidence=0.9,
                source="rule",
                reason="用户明确表达了需要记住的长期偏好。",
            )

        return IntentPrediction(
            intent_type=INTENT_ANSWER,
            confidence=0.5,
            source="default",
            reason="默认进入统一回答工作流。",
        )


class LocalModelIntentClassifier:
    """通过独立配置的本地小模型做高层动作意图分类。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def predict(self, context: AgentTurnContext) -> IntentPrediction:
        model_config = self._resolve_model_config()
        if model_config.provider == "disabled":
            return IntentPrediction(
                intent_type=INTENT_ANSWER,
                confidence=0.0,
                source="model",
                reason="本地意图识别模型未启用。",
                available=False,
            )

        try:
            model = build_chat_model(self.settings, model_config, temperature=0.0)
            structured_model = model.with_structured_output(ModelIntentResult)
            response = structured_model.invoke(
                [
                    SystemMessage(content=_intent_model_system_prompt()),
                    HumanMessage(content=_build_intent_model_prompt(context)),
                ]
            )
            result = _normalize_model_result(response)
        except Exception as exc:
            logger.warning("Local intent classification model failed.", exc_info=exc)
            return IntentPrediction(
                intent_type=INTENT_ANSWER,
                confidence=0.0,
                source="model",
                reason="本地意图识别模型调用失败。",
                available=False,
                error_message=str(exc),
            )

        return IntentPrediction(
            intent_type=result.intent_type,
            confidence=_clamp_confidence(result.confidence),
            source="model",
            reason=result.reason.strip() or "本地模型未返回原因。",
        )

    def _resolve_model_config(self) -> AgentModelCandidate:
        """构造独立的本地意图模型配置，不复用主 Agent 大模型。"""

        provider = (
            str(getattr(self.settings, "intent_model_provider", "disabled"))
            .strip()
            .lower()
            or "disabled"
        )
        return AgentModelCandidate(
            provider=provider,
            base_url=str(getattr(self.settings, "intent_model_base_url", "")).strip(),
            api_key=str(getattr(self.settings, "intent_model_api_key", "")).strip(),
            model_name=str(getattr(self.settings, "intent_model_name", "")).strip(),
        )


DOCUMENT_INGEST_KEYWORDS = (
    "入库",
    "加入知识库",
    "保存到知识库",
    "存到知识库",
    "向量化",
    "以后可以检索",
    "以后能检索",
    "index this",
    "add to knowledge base",
)

ATTACHMENT_PARSE_KEYWORDS = (
    "解析",
    "提取",
    "识别附件",
    "读取附件",
    "读一下附件",
    "这份文件内容",
    "总结附件",
    "看看文件",
    "extract",
    "parse",
)

MEMORY_UPDATE_KEYWORDS = (
    "记住",
    "以后都",
    "我不吃",
    "我不能吃",
    "我喜欢",
    "我偏好",
    "我的口味",
    "我家里有",
    "我的厨具",
    "remember",
)


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _build_fused_scores(
    *,
    rule_prediction: IntentPrediction,
    model_prediction: IntentPrediction,
    rule_weight: float,
    model_weight: float,
) -> dict[str, float]:
    scores = {intent_type: 0.0 for intent_type in SUPPORTED_INTENTS}
    scores[rule_prediction.intent_type] += rule_weight * rule_prediction.confidence
    scores[model_prediction.intent_type] += model_weight * model_prediction.confidence
    return scores


def _select_best_intent(
    fused_scores: dict[str, float],
    *,
    context: AgentTurnContext,
    rule_prediction: IntentPrediction,
) -> str:
    ranked_intents = sorted(
        fused_scores.items(),
        key=lambda item: (item[1], _intent_priority(item[0])),
        reverse=True,
    )
    for intent_type, _score in ranked_intents:
        if _is_intent_allowed(
            intent_type,
            context=context,
            rule_prediction=rule_prediction,
        ):
            return intent_type
    return INTENT_ANSWER


def _is_intent_allowed(
    intent_type: str,
    *,
    context: AgentTurnContext,
    rule_prediction: IntentPrediction,
) -> bool:
    if intent_type not in SIDE_EFFECT_ATTACHMENT_INTENTS:
        return True

    # 附件解析和入库会改变后端状态，必须同时满足“有附件”和“规则明确命中”。
    return bool(context.attachment_public_ids) and rule_prediction.intent_type == intent_type


def _intent_priority(intent_type: str) -> int:
    priority = {
        INTENT_DOCUMENT_INGEST: 4,
        INTENT_ATTACHMENT_PARSE: 3,
        INTENT_MEMORY_UPDATE: 2,
        INTENT_ANSWER: 1,
    }
    return priority.get(intent_type, 0)


def _build_hybrid_reason(
    *,
    intent_type: str,
    rule_prediction: IntentPrediction,
    model_prediction: IntentPrediction,
    fused_scores: dict[str, float],
    rule_weight: float,
    model_weight: float,
) -> str:
    score_summary = ", ".join(
        f"{name}={score:.2f}" for name, score in sorted(fused_scores.items())
    )
    guard_note = ""
    if (
        model_prediction.intent_type in SIDE_EFFECT_ATTACHMENT_INTENTS
        and rule_prediction.intent_type != model_prediction.intent_type
        and intent_type != model_prediction.intent_type
    ):
        guard_note = "；模型给出的附件副作用意图未被规则确认，已按安全策略跳过"

    return (
        f"融合意图={intent_type}；规则({rule_weight:.2f})={rule_prediction.intent_type}"
        f"/{rule_prediction.confidence:.2f}，原因：{rule_prediction.reason}；"
        f"模型({model_weight:.2f})={model_prediction.intent_type}"
        f"/{model_prediction.confidence:.2f}，原因：{model_prediction.reason}；"
        f"融合分数：{score_summary}{guard_note}。"
    )


def _build_model_unavailable_reason(
    rule_prediction: IntentPrediction,
    model_prediction: IntentPrediction,
) -> str:
    error_detail = (
        f" 错误：{model_prediction.error_message}"
        if model_prediction.error_message
        else ""
    )
    return (
        f"{rule_prediction.reason} 本地模型意图识别不可用，已降级使用规则结果。"
        f"模型状态：{model_prediction.reason}{error_detail}"
    )


def _intent_model_system_prompt() -> str:
    return "\n".join(
        [
            "你是 CookingAgent 的本地高层动作意图分类器。",
            "只判断用户这一轮想触发哪类系统动作，不回答用户问题。",
            "可选 intent_type：",
            "answer：普通问答、菜谱咨询、闲聊、RAG 问答或不确定场景。",
            "attachment_parse：用户要求读取、解析、提取、总结本轮附件内容。",
            "document_ingest：用户要求把本轮附件写入知识库、入库、向量化或以后可检索。",
            "memory_update：用户明确表达长期偏好、忌口、厨具、健康目标或要求记住信息。",
            "不要因为问题涉及菜谱就选择 document_ingest；没有明确系统动作时选择 answer。",
            "confidence 表示你对分类的把握，范围 0 到 1；reason 用简短中文说明。",
        ]
    )


def _build_intent_model_prompt(context: AgentTurnContext) -> str:
    attachment_state = "有附件" if context.attachment_public_ids else "无附件"
    message_text = (context.user_message_text or "").strip()
    return f"附件状态：{attachment_state}\n用户输入：{message_text}"


def _normalize_model_result(response: Any) -> ModelIntentResult:
    if isinstance(response, ModelIntentResult):
        return response
    return ModelIntentResult.model_validate(response)


def _clamp_confidence(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
