"""附件解析工作流。"""

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.db.models.attachment import Attachment
from src.services.attachment_parse_service import AttachmentParseService


class AttachmentParseWorkflow:
    """解析本轮消息绑定的附件，并把文本结果写入 parse_results。"""

    name = "attachment_parse_workflow"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.parse_service = AttachmentParseService(db)

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        attachments = self._load_attachments(context)
        outcomes: list[dict] = []

        for attachment in attachments:
            outcome = self.parse_service.parse_attachment(attachment)
            outcomes.append(
                {
                    "attachment_public_id": outcome.attachment_public_id,
                    "file_name": outcome.file_name,
                    "status": outcome.status,
                    "text_length": outcome.text_length,
                    "error_message": outcome.error_message,
                }
            )

        self.db.commit()

        completed_count = sum(1 for item in outcomes if item["status"] == "completed")
        failed_count = sum(1 for item in outcomes if item["status"] == "failed")

        if not attachments:
            reply_text = "本轮没有可解析的附件。"
        elif failed_count == 0:
            reply_text = f"已完成 {completed_count} 个附件解析，解析文本已保存，可用于后续问答或入库。"
        elif completed_count == 0:
            reply_text = "附件解析失败。当前仅支持 MinerU 可解析的 PDF、DOCX、PPTX、XLSX 和 JPG/PNG 图片。"
        else:
            reply_text = (
                f"已完成 {completed_count} 个附件解析，另有 {failed_count} 个附件解析失败。"
                "失败项可在解析明细中查看原因。"
            )

        return AgentTurnResult(
            reply_text=reply_text,
            intent_type=intent.intent_type,
            workflow_name=self.name,
            output_snapshot={
                "reply_type": "workflow_notice",
                "workflow_name": self.name,
                "attachment_public_ids": context.attachment_public_ids,
                "parse_results": outcomes,
                "intent": {
                    "type": intent.intent_type,
                    "confidence": intent.confidence,
                    "source": intent.source,
                    "reason": intent.reason,
                },
            },
        )

    def _load_attachments(self, context: AgentTurnContext) -> list[Attachment]:
        if not context.attachment_public_ids:
            return []

        stmt = (
            select(Attachment)
            .options(joinedload(Attachment.parse_result))
            .where(Attachment.public_id.in_(context.attachment_public_ids))
        )
        attachments = list(self.db.scalars(stmt).all())
        attachment_by_id = {attachment.public_id: attachment for attachment in attachments}

        # 保持用户上传顺序，便于前端展示解析明细时与原附件顺序一致。
        return [
            attachment_by_id[public_id]
            for public_id in context.attachment_public_ids
            if public_id in attachment_by_id
        ]
