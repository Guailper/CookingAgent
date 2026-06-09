"""文档向量化入库工作流。"""

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.core.config import Settings, get_settings
from src.core.constants import (
    EMBEDDING_STATUS_COMPLETED,
    EMBEDDING_STATUS_FAILED,
    EMBEDDING_STATUS_PENDING,
    EMBEDDING_STATUS_REJECTED,
    PARSE_STATUS_COMPLETED,
)
from src.db.models.attachment import Attachment
from src.rag.indexing_service import RagDocument, RagIndexingService
from src.services.attachment_content_validation_service import (
    CONTENT_VALIDATION_STATUS_COMPLETED,
    AttachmentContentValidation,
    AttachmentContentValidationService,
)
from src.services.attachment_parse_service import AttachmentParseService


class DocumentIngestWorkflow:
    """把已解析附件写入后端默认知识库。"""

    name = "document_ingest_workflow"

    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        indexing_service: RagIndexingService | None = None,
        content_validation_service: AttachmentContentValidationService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.indexing_service = indexing_service or RagIndexingService(self.settings)
        self.parse_service = AttachmentParseService(db)
        self.content_validation_service = (
            content_validation_service or AttachmentContentValidationService(self.settings)
        )

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

            validation = self.content_validation_service.validate(
                title=attachment.original_name,
                text=raw_text,
            )
            self._persist_content_validation(attachment, validation)
            if not validation.accepted:
                validation_failed = (
                    validation.status != CONTENT_VALIDATION_STATUS_COMPLETED
                )
                if not validation_failed:
                    delete_document = getattr(
                        self.indexing_service,
                        "delete_document",
                        None,
                    )
                    if callable(delete_document):
                        delete_document(knowledge_base_id, attachment.public_id)
                if attachment.parse_result is not None:
                    attachment.parse_result.embedding_status = (
                        EMBEDDING_STATUS_FAILED
                        if validation_failed
                        else EMBEDDING_STATUS_REJECTED
                    )
                skipped_documents.append(
                    {
                        "attachment_public_id": attachment.public_id,
                        "title": attachment.original_name,
                        "reason": (
                            "validation_failed"
                            if validation_failed
                            else "irrelevant_content"
                        ),
                        "error_message": validation.error_message or validation.reason,
                        "content_validation": validation.to_metadata(),
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

        parse_result = attachment.parse_result
        if (
            parse_result
            and parse_result.raw_text
            and parse_result.parser_name == self.parse_service.PARSER_NAME
        ):
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

    @staticmethod
    def _persist_content_validation(
        attachment: Attachment,
        validation: AttachmentContentValidation,
    ) -> None:
        """把入库判定保存在解析元数据中，便于排查拒绝原因。"""

        if attachment.parse_result is None:
            return

        structured_result = attachment.parse_result.structured_result
        normalized_result = dict(structured_result) if isinstance(structured_result, dict) else {}
        normalized_result["content_validation"] = validation.to_metadata()
        attachment.parse_result.structured_result = normalized_result

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

        if skipped_documents and all(
            item["reason"] == "irrelevant_content" for item in skipped_documents
        ):
            if len(skipped_documents) == 1:
                reason = skipped_documents[0].get("error_message") or "内容与烹饪知识无关。"
                return (
                    f"附件内容检测未通过：{reason}"
                    " 未执行入库。请重新上传符合主题的菜谱、菜单、食材清单或做菜相关资料。"
                )
            return (
                f"{len(skipped_documents)} 个附件内容检测未通过，未执行入库。"
                "请重新上传符合主题的菜谱、菜单、食材清单或做菜相关资料。"
            )

        if skipped_documents and all(
            item["reason"] == "validation_failed" for item in skipped_documents
        ):
            return "附件主题校验暂时不可用，未写入知识库。请稍后重试入库。"

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
                "embedding_status_failed": EMBEDDING_STATUS_FAILED,
                "embedding_status_rejected": EMBEDDING_STATUS_REJECTED,
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
