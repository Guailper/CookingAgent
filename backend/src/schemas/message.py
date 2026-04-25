"""Pydantic models for chat message requests and responses."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import (
    INPUT_SOURCE_KEYBOARD,
    INPUT_SOURCE_VOICE,
    MESSAGE_ROLE_USER,
    MESSAGE_STATUS_COMPLETED,
    MESSAGE_TYPE_TEXT,
)
from src.schemas.file import AttachmentItem


class MessageExtraMetadata(BaseModel):
    """Metadata for text messages, including whether the text came from voice input."""

    model_config = ConfigDict(extra="allow")

    input_source: Literal[INPUT_SOURCE_KEYBOARD, INPUT_SOURCE_VOICE] | None = Field(
        default=None,
        description="输入来源，仅支持 keyboard 或 voice。",
    )


class CreateMessageRequest(BaseModel):
    """Create a text chat message with optional attachments and metadata."""

    content: str = Field(default="", description="消息正文")
    message_type: Literal[MESSAGE_TYPE_TEXT] = Field(
        default=MESSAGE_TYPE_TEXT,
        description="当前仅支持 text 文本消息。",
    )
    attachment_ids: list[str] = Field(default_factory=list, description="待绑定附件 ID 列表")
    extra_metadata: MessageExtraMetadata | None = Field(
        default=None,
        description="附加元数据，可通过 input_source 标记 keyboard 或 voice。",
    )


class MessageItem(BaseModel):
    """Serialized chat message returned to the frontend workspace."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    conversation_id: int
    user_id: int | None
    role: str = MESSAGE_ROLE_USER
    message_type: str
    content: str
    status: str = MESSAGE_STATUS_COMPLETED
    extra_metadata: dict[str, Any] | list[Any] | None
    attachments: list[AttachmentItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    """Single-message response envelope."""

    message: str
    data: MessageItem


class MessageListResponse(BaseModel):
    """Conversation message list response envelope."""

    message: str
    data: list[MessageItem]
