"""Unified agent chat endpoint for the MVP assistant reply flow."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.agent import AgentChatData, AgentChatResponse, AgentRunItem, AgentChatRequest
from src.schemas.message import MessageItem
from src.services.agent_service import AgentService

router = APIRouter()


@router.post("/agent/chat", response_model=AgentChatResponse, summary="智能体对话")
async def agent_chat(
    payload: AgentChatRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> AgentChatResponse:
    """Create a user message, run the MVP agent, and return the assistant reply."""

    extra_metadata = (
        payload.extra_metadata.model_dump(exclude_none=True)
        if payload.extra_metadata is not None
        else None
    )
    user_message, assistant_message, agent_run = AgentService(db).chat(
        user=current_user,
        conversation_public_id=payload.conversation_id,
        content=payload.content,
        attachment_public_ids=payload.attachment_ids,
        extra_metadata=extra_metadata,
    )
    return AgentChatResponse(
        message="智能体回复成功。",
        data=AgentChatData(
            user_message=MessageItem.model_validate(user_message),
            assistant_message=MessageItem.model_validate(assistant_message),
            agent_run=AgentRunItem.model_validate(agent_run),
        ),
    )
