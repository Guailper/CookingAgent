"""Attachment upload and cleanup endpoints for the chat workspace."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.file import AttachmentDeleteResponse, AttachmentItem, AttachmentUploadResponse
from src.services.file_service import FileService

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
