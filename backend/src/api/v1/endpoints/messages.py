"""Message endpoints for reading and writing conversation content."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.message import CreateMessageRequest, MessageItem, MessageListResponse, MessageResponse
from src.services.message_service import MessageService

router = APIRouter()


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    summary="发送消息",
)
async def create_message(
    conversation_id: str,
    payload: CreateMessageRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> MessageResponse:
    """Create a text message and bind any uploaded attachments in the same request."""

    extra_metadata = (
        payload.extra_metadata.model_dump(exclude_none=True)
        if payload.extra_metadata is not None
        else None
    )

    message = MessageService(db).create_user_message(
        user=current_user,
        conversation_public_id=conversation_id,
        content=payload.content,
        attachment_public_ids=payload.attachment_ids,
        extra_metadata=extra_metadata,
    )
    return MessageResponse(
        message="消息发送成功。",
        data=MessageItem.model_validate(message),
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="获取消息列表",
)
async def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> MessageListResponse:
    """Return all messages for the current user's conversation."""

    messages = MessageService(db).list_conversation_messages(
        user=current_user,
        conversation_public_id=conversation_id,
    )
    return MessageListResponse(
        message="获取消息列表成功。",
        data=[MessageItem.model_validate(item) for item in messages],
    )
