"""Document ingestion workflow for parsed attachment text."""

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from src.core.config import Settings, get_settings
from src.db.models.attachment import Attachment
from src.rag.indexing_service import RagDocument, RagIndexingService
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload


class DocumentIngestWorkflow:
    """Index already parsed attachment text into the backend default knowledge base."""

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

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        knowledge_base_id = self._resolve_target_knowledge_base_id(context)
        attachments = self._load_attachments(context)
        indexed_documents: list[dict] = []
        skipped_documents: list[dict] = []

        if not knowledge_base_id:
            return self._build_notice_result(
                context=context,
                intent=intent,
                reply_text="当前后端没有配置默认知识库 ID，无法执行文档向量化入库。",
                indexed_documents=indexed_documents,
                skipped_documents=skipped_documents,
            )

        for attachment in attachments:
            raw_text = (attachment.parse_result.raw_text if attachment.parse_result else "") or ""
            raw_text = raw_text.strip()
            if not raw_text:
                skipped_documents.append(
                    {
                        "attachment_public_id": attachment.public_id,
                        "reason": "missing_parsed_text",
                    }
                )
                continue

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
            indexed_documents.append(
                {
                    "attachment_public_id": attachment.public_id,
                    "title": attachment.original_name,
                    "chunk_count": chunk_count,
                }
            )

        if indexed_documents:
            reply_text = (
                f"已将 {len(indexed_documents)} 个文档写入默认知识库，"
                f"共生成 {sum(item['chunk_count'] for item in indexed_documents)} 个向量片段。"
            )
            if skipped_documents:
                reply_text += f"另有 {len(skipped_documents)} 个附件缺少解析文本，已跳过。"
        else:
            reply_text = "没有可入库的解析文本。请先完成附件解析，再执行知识库入库。"

        return self._build_notice_result(
            context=context,
            intent=intent,
            reply_text=reply_text,
            indexed_documents=indexed_documents,
            skipped_documents=skipped_documents,
            knowledge_base_id=knowledge_base_id,
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
        return list(self.db.scalars(stmt).all())

    def _build_notice_result(
        self,
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
            workflow_name=self.name,
            output_snapshot={
                "reply_type": "workflow_notice",
                "workflow_name": self.name,
                "knowledge_base_id": knowledge_base_id,
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
