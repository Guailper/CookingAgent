"""Rule-based high-level action intent resolver."""

from agent.contracts import ActionIntent, AgentTurnContext

INTENT_ANSWER = "answer"
INTENT_ATTACHMENT_PARSE = "attachment_parse"
INTENT_DOCUMENT_INGEST = "document_ingest"
INTENT_UNSUPPORTED = "unsupported"


class ActionIntentResolver:
    """Resolve only coarse actions, not answer subtypes.

    RAG is deliberately not an intent here. It is a default backend context
    enhancement inside AnswerWorkflow.
    """

    def resolve(self, context: AgentTurnContext) -> ActionIntent:
        text = (context.user_message_text or "").strip().lower()

        if context.attachment_public_ids and _contains_any(text, DOCUMENT_INGEST_KEYWORDS):
            return ActionIntent(
                intent_type=INTENT_DOCUMENT_INGEST,
                confidence=1.0,
                source="rule",
                reason="User explicitly asked to store an attachment in the knowledge base.",
            )

        if context.attachment_public_ids and _contains_any(text, ATTACHMENT_PARSE_KEYWORDS):
            return ActionIntent(
                intent_type=INTENT_ATTACHMENT_PARSE,
                confidence=0.9,
                source="rule",
                reason="User asked to parse or extract content from the attachment.",
            )

        return ActionIntent(
            intent_type=INTENT_ANSWER,
            confidence=1.0,
            source="default",
            reason="Default user turn is handled by the unified answer workflow.",
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
    "这份文件内容",
    "extract",
    "parse",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)
