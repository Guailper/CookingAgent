"""Unified agent chat endpoint for the assistant reply flow."""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db_session
from src.cache.cache_service import CacheService
from src.cache.rate_limiter import RateLimiter
from src.core.config import get_settings
from src.schemas.agent import AgentChatRequest, AgentRunItem
from src.schemas.message import MessageItem
from src.services.agent_service import AgentService

router = APIRouter()


@router.post("/agent/chat/stream", summary="Stream agent chat")
async def agent_chat_stream(
    payload: AgentChatRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    """Create a user message, stream the assistant reply, and persist the result."""

    _apply_agent_rate_limit(request, current_user.public_id)
    extra_metadata = (
        payload.extra_metadata.model_dump(exclude_none=True)
        if payload.extra_metadata is not None
        else None
    )

    def event_stream():
        for event in AgentService(db).chat_stream(
            user=current_user,
            conversation_public_id=payload.conversation_id,
            content=payload.content,
            attachment_public_ids=payload.attachment_ids,
            knowledge_base_public_ids=payload.knowledge_base_ids,
            request_options={**payload.options, "stream": True},
            extra_metadata=extra_metadata,
        ):
            yield _format_sse(event["event"], _serialize_stream_payload(event["event"], event["data"]))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _serialize_stream_payload(event_name: str, payload):
    if event_name == "delta":
        return payload
    if event_name == "user_message":
        return MessageItem.model_validate(payload).model_dump(mode="json")
    if event_name == "agent_run":
        return AgentRunItem.model_validate(payload).model_dump(mode="json")
    if event_name == "done":
        return {
            "user_message": MessageItem.model_validate(payload["user_message"]).model_dump(mode="json"),
            "assistant_message": MessageItem.model_validate(payload["assistant_message"]).model_dump(mode="json"),
            "agent_run": AgentRunItem.model_validate(payload["agent_run"]).model_dump(mode="json"),
        }
    return payload


def _format_sse(event_name: str, payload) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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

