"""Unified agent chat endpoint for the assistant reply flow."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.cache.cache_service import CacheService
from src.cache.rate_limiter import RateLimiter
from src.core.config import get_settings
from src.schemas.agent import AgentChatData, AgentChatRequest, AgentChatResponse, AgentRunItem
from src.schemas.message import MessageItem
from src.services.agent_service import AgentService

router = APIRouter()


@router.post("/agent/chat", response_model=AgentChatResponse, summary="智能体对话")
async def agent_chat(
    payload: AgentChatRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> AgentChatResponse:
    """Create a user message, run the agent, and return the assistant reply."""

    _apply_agent_rate_limit(request, current_user.public_id)
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


def _apply_agent_rate_limit(request: Request, user_public_id: str) -> None:
    settings = get_settings()
    cache = CacheService(settings)
    RateLimiter(cache).require_allowed(
        key=cache.build_key(
            "rate_limit",
            "agent",
            user_public_id,
            _request_client_id(request),
        ),
        limit=settings.agent_rate_limit_count,
        window_seconds=settings.agent_rate_limit_window_seconds,
        error_code="AGENT_RATE_LIMITED",
        message="智能体请求过于频繁，请稍后再试。",
    )


def _request_client_id(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
