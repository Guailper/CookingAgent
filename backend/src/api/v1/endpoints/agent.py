"""Unified agent chat endpoint for the assistant reply flow."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.schemas.agent import AgentChatData, AgentChatRequest, AgentChatResponse, AgentRunItem
from src.schemas.message import MessageItem
from src.services.agent_service import AgentService

router = APIRouter()


@router.post("/agent/chat", response_model=AgentChatResponse, summary="智能体对话")
async def agent_chat(
    payload: AgentChatRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> AgentChatResponse:
    """创建用户消息，执行智能体，并返回助手回复。

    这里会把“是否发生降级”直接反映到响应 message 上，
    这样开发联调时即使不立刻去查 agent_run，也能先看出这次是不是走了本地兜底。
    """

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
        knowledge_base_public_ids=payload.knowledge_base_ids,
        request_options=payload.options,
        extra_metadata=extra_metadata,
    )

    output_snapshot = agent_run.output_snapshot if isinstance(agent_run.output_snapshot, dict) else {}
    response_message = (
        "智能体主模型本次不可用，已返回降级回答。"
        if output_snapshot.get("degraded")
        else "智能体回复成功。"
    )

    return AgentChatResponse(
        message=response_message,
        data=AgentChatData(
            user_message=MessageItem.model_validate(user_message),
            assistant_message=MessageItem.model_validate(assistant_message),
            agent_run=AgentRunItem.model_validate(agent_run),
        ),
    )
