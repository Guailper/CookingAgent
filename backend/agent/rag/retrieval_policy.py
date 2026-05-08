"""Rule-based policy for deciding whether a turn needs RAG retrieval."""

from agent.contracts import AgentTurnContext, RetrievalDecision


class RetrievalPolicy:
    """Decide whether the current turn should query the default knowledge base."""

    def decide(self, context: AgentTurnContext) -> RetrievalDecision:
        text = _normalize_text(context.user_message_text)

        if context.attachment_public_ids:
            return RetrievalDecision(
                should_retrieve=True,
                source="rule",
                reason="本轮包含附件，保留检索机会以辅助附件相关回答。",
            )

        if not text:
            return RetrievalDecision(
                should_retrieve=False,
                source="rule",
                reason="用户输入为空，不执行知识库检索。",
            )

        if _contains_any(text, DOMAIN_KEYWORDS):
            return RetrievalDecision(
                should_retrieve=True,
                source="rule",
                reason="用户输入涉及做菜、食材、菜谱、营养或厨房流程。",
            )

        if _contains_any(text, EXPLICIT_KNOWLEDGE_KEYWORDS):
            return RetrievalDecision(
                should_retrieve=True,
                source="rule",
                reason="用户明确提到资料、文档、知识库或检索。",
            )

        if _is_short_control_turn(text) or _contains_any(text, SKIP_KEYWORDS):
            return RetrievalDecision(
                should_retrieve=False,
                source="rule",
                reason="用户输入是问候、感谢、格式调整或续写控制，不需要知识库检索。",
            )

        # 默认对不确定问题执行检索。这样不会把潜在领域问题过早排除；
        # 无相关片段时会进入 miss，由回答模型按通用知识继续处理。
        return RetrievalDecision(
            should_retrieve=True,
            source="default",
            reason="无法通过规则确认可跳过检索，默认尝试后端知识库检索。",
        )


DOMAIN_KEYWORDS = (
    "做菜",
    "菜",
    "菜谱",
    "食谱",
    "食材",
    "调味",
    "调料",
    "烹饪",
    "厨房",
    "营养",
    "减脂",
    "热量",
    "蛋白质",
    "空气炸锅",
    "炒",
    "煮",
    "蒸",
    "烤",
    "焯水",
    "腌制",
    "火候",
    "替代",
)

EXPLICIT_KNOWLEDGE_KEYWORDS = (
    "资料",
    "文档",
    "知识库",
    "检索",
    "根据已有",
    "根据资料",
    "参考资料",
)

SKIP_KEYWORDS = (
    "你好",
    "您好",
    "谢谢",
    "感谢",
    "再见",
    "拜拜",
    "你是谁",
    "继续",
    "换一种说法",
    "换个说法",
    "重新生成",
    "简短",
    "精简",
    "详细一点",
    "用表格",
    "表格展示",
    "分步骤",
    "上一条",
    "刚才",
)


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_short_control_turn(text: str) -> bool:
    return len(text) <= 8 and _contains_any(text, SKIP_KEYWORDS)
