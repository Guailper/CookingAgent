"""基于规则的高层动作意图识别。"""

from agent.contracts import ActionIntent, AgentTurnContext

INTENT_ANSWER = "answer"
INTENT_ATTACHMENT_PARSE = "attachment_parse"
INTENT_DOCUMENT_INGEST = "document_ingest"
INTENT_MEMORY_UPDATE = "memory_update"
INTENT_UNSUPPORTED = "unsupported"


class ActionIntentResolver:
    """只识别“做什么动作”，不把普通回答和 RAG 回答拆开。

    这里刻意保持规则透明：有副作用的动作必须来自明确表达，不能靠模型猜测。
    RAG 是否执行由 AnswerWorkflow 内部的 RetrievalPolicy 决定，不属于这里的动作意图。
    """

    def resolve(self, context: AgentTurnContext) -> ActionIntent:
        text = _normalize_text(context.user_message_text)

        if context.attachment_public_ids and _contains_any(text, DOCUMENT_INGEST_KEYWORDS):
            return ActionIntent(
                intent_type=INTENT_DOCUMENT_INGEST,
                confidence=1.0,
                source="rule",
                reason="用户明确要求把附件内容写入知识库。",
            )

        if context.attachment_public_ids and _contains_any(text, ATTACHMENT_PARSE_KEYWORDS):
            return ActionIntent(
                intent_type=INTENT_ATTACHMENT_PARSE,
                confidence=0.95,
                source="rule",
                reason="用户明确要求解析、读取或提取附件内容。",
            )

        if _contains_any(text, MEMORY_UPDATE_KEYWORDS):
            return ActionIntent(
                intent_type=INTENT_MEMORY_UPDATE,
                confidence=0.9,
                source="rule",
                reason="用户明确表达了需要记住的长期偏好。",
            )

        return ActionIntent(
            intent_type=INTENT_ANSWER,
            confidence=1.0,
            source="default",
            reason="默认进入统一回答工作流。",
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
