"""文档向量化入库工作流。"""

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.core.config import Settings, get_settings
from src.core.constants import EMBEDDING_STATUS_PENDING, PARSE_STATUS_COMPLETED
from src.db.models.attachment import Attachment
from src.rag.indexing_service import RagDocument, RagIndexingService
from src.services.attachment_parse_service import AttachmentParseService

EMBEDDING_STATUS_COMPLETED = "completed"
EMBEDDING_STATUS_FAILED = "failed"


class DocumentIngestWorkflow:
    """把已解析附件写入后端默认知识库。"""

    name = "document_ingest_workflow"

    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        indexing_service: RagIndexingService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.indexing_service = indexing_service or RagIndexingService(self.settings)
        self.parse_service = AttachmentParseService(db)

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        knowledge_base_id = self._resolve_target_knowledge_base_id(context)
        attachments = self._load_attachments(context)
        indexed_documents: list[dict] = []
        skipped_documents: list[dict] = []

        if not knowledge_base_id:
            return self._build_result(
                context=context,
                intent=intent,
                reply_text="当前后端没有配置默认知识库 ID，无法执行文档向量化入库。",
                indexed_documents=indexed_documents,
                skipped_documents=skipped_documents,
            )

        for attachment in attachments:
            self._ensure_attachment_parsed(attachment, skipped_documents)
            raw_text = (attachment.parse_result.raw_text if attachment.parse_result else "") or ""
            raw_text = raw_text.strip()
            if not raw_text:
                if not any(item["attachment_public_id"] == attachment.public_id for item in skipped_documents):
                    skipped_documents.append(
                        {
                            "attachment_public_id": attachment.public_id,
                            "title": attachment.original_name,
                            "reason": "missing_parsed_text",
                        }
                    )
                continue

            try:
                chunk_count = self.indexing_service.index_document(
                    RagDocument(
                        knowledge_base_public_id=knowledge_base_id,
                        document_public_id=attachment.public_id,
                        title=attachment.original_name,
                        text=raw_text,
                        metadata={
                            "attachment_public_id": attachment.public_id,
                            "conversation_public_id": context.conversation_public_id,
                        },
                    )
                )
            except Exception as exc:
                if attachment.parse_result is not None:
                    attachment.parse_result.embedding_status = EMBEDDING_STATUS_FAILED
                skipped_documents.append(
                    {
                        "attachment_public_id": attachment.public_id,
                        "title": attachment.original_name,
                        "reason": "index_failed",
                        "error_message": str(exc),
                    }
                )
                continue

            if attachment.parse_result is not None:
                attachment.parse_result.embedding_status = EMBEDDING_STATUS_COMPLETED
            indexed_documents.append(
                {
                    "attachment_public_id": attachment.public_id,
                    "title": attachment.original_name,
                    "chunk_count": chunk_count,
                }
            )

        self.db.commit()

        reply_text = self._build_reply_text(indexed_documents, skipped_documents)
        return self._build_result(
            context=context,
            intent=intent,
            reply_text=reply_text,
            indexed_documents=indexed_documents,
            skipped_documents=skipped_documents,
            knowledge_base_id=knowledge_base_id,
        )

    def _ensure_attachment_parsed(
        self,
        attachment: Attachment,
        skipped_documents: list[dict],
    ) -> None:
        """入库依赖解析文本；未解析附件先尝试本地解析一次。"""

        if attachment.parse_result and attachment.parse_result.raw_text:
            return

        outcome = self.parse_service.parse_attachment(attachment)
        if outcome.status != PARSE_STATUS_COMPLETED:
            skipped_documents.append(
                {
                    "attachment_public_id": attachment.public_id,
                    "title": attachment.original_name,
                    "reason": "parse_failed",
                    "error_message": outcome.error_message,
                }
            )

    def _resolve_target_knowledge_base_id(self, context: AgentTurnContext) -> str | None:
        ids = context.knowledge_base_public_ids or self.settings.rag_default_knowledge_base_ids
        return ids[0] if ids else None

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
        return [
            attachment_by_id[public_id]
            for public_id in context.attachment_public_ids
            if public_id in attachment_by_id
        ]

    @staticmethod
    def _build_reply_text(indexed_documents: list[dict], skipped_documents: list[dict]) -> str:
        if indexed_documents:
            chunk_count = sum(item["chunk_count"] for item in indexed_documents)
            reply_text = f"已将 {len(indexed_documents)} 个文档写入默认知识库，共生成 {chunk_count} 个向量片段。"
            if skipped_documents:
                reply_text += f"另有 {len(skipped_documents)} 个附件未能入库，已记录失败原因。"
            return reply_text

        if skipped_documents:
            return "没有文档成功入库。请检查附件格式、解析结果或向量库配置。"

        return "本轮没有可入库的附件。"

    @staticmethod
    def _build_result(
        *,
        context: AgentTurnContext,
        intent: ActionIntent,
        reply_text: str,
        indexed_documents: list[dict],
        skipped_documents: list[dict],
        knowledge_base_id: str | None = None,
    ) -> AgentTurnResult:
        return AgentTurnResult(
            reply_text=reply_text,
            intent_type=intent.intent_type,
            workflow_name=DocumentIngestWorkflow.name,
            output_snapshot={
                "reply_type": "workflow_notice",
                "workflow_name": DocumentIngestWorkflow.name,
                "knowledge_base_id": knowledge_base_id,
                "embedding_status_completed": EMBEDDING_STATUS_COMPLETED,
                "embedding_status_pending": EMBEDDING_STATUS_PENDING,
                "attachment_public_ids": context.attachment_public_ids,
                "indexed_documents": indexed_documents,
                "skipped_documents": skipped_documents,
                "intent": {
                    "type": intent.intent_type,
                    "confidence": intent.confidence,
                    "source": intent.source,
                    "reason": intent.reason,
                },
            },
        )
