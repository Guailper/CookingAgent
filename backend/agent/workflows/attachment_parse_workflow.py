"""Attachment parsing workflow placeholder."""

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from sqlalchemy.orm import Session


class AttachmentParseWorkflow:
    """Report current attachment parsing state.

    The project has attachment records and parse-result models, but no complete
    parser service wired into chat yet. This workflow keeps the orchestrator
    explicit without pretending parsing has already happened.
    """

    name = "attachment_parse_workflow"

    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        _ = self.db
        attachment_count = len(context.attachment_public_ids)
        reply_text = (
            f"已收到 {attachment_count} 个附件，但当前对话链路还没有接入完整的附件解析服务。"
            "请先完成附件解析服务接入后，再基于解析文本进行总结或问答。"
        )
        return AgentTurnResult(
            reply_text=reply_text,
            intent_type=intent.intent_type,
            workflow_name=self.name,
            output_snapshot={
                "reply_type": "workflow_notice",
                "workflow_name": self.name,
                "attachment_public_ids": context.attachment_public_ids,
                "intent": {
                    "type": intent.intent_type,
                    "confidence": intent.confidence,
                    "source": intent.source,
                    "reason": intent.reason,
                },
            },
        )
