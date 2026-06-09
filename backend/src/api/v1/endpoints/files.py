"""Attachment upload and cleanup endpoints for the chat workspace."""

from agent.contracts import ActionIntent, AgentTurnContext
from agent.workflows.document_ingest_workflow import DocumentIngestWorkflow
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.file import (
    AttachmentDeleteResponse,
    AttachmentIngestRetryItem,
    AttachmentIngestRetryRequest,
    AttachmentIngestRetryResponse,
    AttachmentItem,
    AttachmentUploadResponse,
)
from src.schemas.message import MessageItem
from src.services.file_service import FileService
from src.services.message_service import MessageService

router = APIRouter()


@router.post(
    "/conversations/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=AttachmentUploadResponse,
    summary="上传会话附件",
)
async def upload_conversation_attachments(
    conversation_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> AttachmentUploadResponse:
    """Upload one or more files and keep them ready for the next message send."""

    attachments = await FileService(db).upload_conversation_attachments(
        user=current_user,
        conversation_public_id=conversation_id,
        files=files,
    )
    return AttachmentUploadResponse(
        message="附件上传成功。",
        data=[AttachmentItem.model_validate(attachment) for attachment in attachments],
    )


@router.delete(
    "/attachments/{attachment_id}",
    response_model=AttachmentDeleteResponse,
    summary="删除未绑定附件",
)
async def delete_unbound_attachment(
    attachment_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> AttachmentDeleteResponse:
    """Delete an uploaded attachment before it is bound to a formal message."""

    FileService(db).delete_unbound_attachment(
        user=current_user,
        attachment_public_id=attachment_id,
    )
    return AttachmentDeleteResponse(message="附件删除成功。")


@router.post(
    "/attachments/{attachment_id}/ingest/retry",
    response_model=AttachmentIngestRetryResponse,
    summary="重试附件入库",
)
async def retry_attachment_ingestion(
    attachment_id: str,
    payload: AttachmentIngestRetryRequest | None = None,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> AttachmentIngestRetryResponse:
    """Retry parsing/indexing for an existing attachment without uploading it again."""

    file_service = FileService(db)
    attachment, conversation = file_service.get_owned_attachment(current_user, attachment_id)
    knowledge_base_ids = (
        [payload.knowledge_base_id]
        if payload is not None and payload.knowledge_base_id
        else []
    )
    context = AgentTurnContext(
        conversation_public_id=conversation.public_id,
        user_public_id=current_user.public_id,
        trigger_message_public_id=f"retry_{attachment.public_id}",
        user_message_text="重试附件入库",
        attachment_public_ids=[attachment.public_id],
        knowledge_base_public_ids=knowledge_base_ids,
    )
    result = DocumentIngestWorkflow(db).run(
        context,
        ActionIntent(
            intent_type="document_ingest",
            confidence=1.0,
            source="attachment_retry_api",
            reason="用户明确重试已上传附件的入库处理。",
        ),
    )
    assistant_message = MessageService(db).create_assistant_message(
        user=current_user,
        conversation_public_id=conversation.public_id,
        content=result.reply_text,
        extra_metadata={
            "reply_type": "workflow_notice",
            "intent_type": result.intent_type,
            "workflow_name": result.workflow_name,
            "source": "attachment_ingest_retry",
            "attachment_public_id": attachment.public_id,
            "indexed_documents": result.output_snapshot.get("indexed_documents", []),
            "skipped_documents": result.output_snapshot.get("skipped_documents", []),
        },
    )
    refreshed_attachment, _ = file_service.get_owned_attachment(current_user, attachment_id)
    snapshot = result.output_snapshot
    return AttachmentIngestRetryResponse(
        message=result.reply_text,
        data=AttachmentIngestRetryItem(
            attachment=AttachmentItem.model_validate(refreshed_attachment),
            assistant_message=MessageItem.model_validate(assistant_message).model_dump(mode="json"),
            indexed_documents=snapshot.get("indexed_documents", []),
            skipped_documents=snapshot.get("skipped_documents", []),
        ),
    )
