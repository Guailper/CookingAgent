"""Schemas for the MVP agent chat endpoint."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.message import MessageExtraMetadata, MessageItem


class AgentChatRequest(BaseModel):
    """Request body for the unified agent chat endpoint."""

    conversation_id: str = Field(..., min_length=1, description="会话 public_id")
    content: str = Field(default="", description="用户输入文本")
    attachment_ids: list[str] = Field(default_factory=list, description="待绑定附件 ID 列表")
    extra_metadata: MessageExtraMetadata | None = Field(
        default=None,
        description="附加元数据，可通过 input_source 标记 keyboard 或 voice。",
    )


class AgentRunItem(BaseModel):
    """Frontend-safe view of one agent execution record."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    intent_type: str
    workflow_name: str
    run_status: str
    model_name: str | None
    input_snapshot: dict[str, Any] | list[Any] | None
    output_snapshot: dict[str, Any] | list[Any] | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentChatData(BaseModel):
    """Combined result returned after one agent chat execution."""

    user_message: MessageItem
    assistant_message: MessageItem
    agent_run: AgentRunItem


class AgentChatResponse(BaseModel):
    """Envelope for one successful agent chat round."""

    message: str
    data: AgentChatData
