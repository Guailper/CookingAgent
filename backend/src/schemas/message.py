"""消息相关的请求与响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import MESSAGE_ROLE_USER, MESSAGE_STATUS_COMPLETED, MESSAGE_TYPE_TEXT


class CreateMessageRequest(BaseModel):
    """创建消息请求体。"""

    content: str = Field(..., min_length=1, description="消息正文")
    message_type: str = Field(default=MESSAGE_TYPE_TEXT, max_length=32, description="消息类型")


class MessageItem(BaseModel):
    """返回给前端的消息信息。"""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    conversation_id: int
    user_id: int | None
    role: str = MESSAGE_ROLE_USER
    message_type: str
    content: str
    status: str = MESSAGE_STATUS_COMPLETED
    extra_metadata: dict | list | None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    """单条消息响应。"""

    message: str
    data: MessageItem


class MessageListResponse(BaseModel):
    """消息列表响应。"""

    message: str
    data: list[MessageItem]
