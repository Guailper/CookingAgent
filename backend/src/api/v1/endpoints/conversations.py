"""会话接口实现。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.conversation import (
    ConversationDetailResponse,
    ConversationItem,
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
)
from src.services.conversation_service import ConversationService

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationResponse, summary="创建会话")
async def create_conversation(
    payload: CreateConversationRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ConversationResponse:
    """创建一个新的用户会话。"""

    conversation = ConversationService(db).create_conversation(current_user, payload.title)
    return ConversationResponse(
        message="会话创建成功。",
        data=ConversationItem.model_validate(conversation),
    )


@router.get("", response_model=ConversationListResponse, summary="获取会话列表")
async def list_conversations(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ConversationListResponse:
    """返回当前用户的会话列表。"""

    conversations = ConversationService(db).list_conversations(current_user)
    return ConversationListResponse(
        message="获取会话列表成功。",
        data=[ConversationItem.model_validate(item) for item in conversations],
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse, summary="获取单个会话详情")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ConversationDetailResponse:
    """返回当前用户的单个会话详情。"""

    conversation = ConversationService(db).get_conversation(current_user, conversation_id)
    return ConversationDetailResponse(
        message="获取会话详情成功。",
        data=ConversationItem.model_validate(conversation),
    )
