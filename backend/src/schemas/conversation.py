"""会话相关的请求与响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import DEFAULT_CONVERSATION_TITLE


class CreateConversationRequest(BaseModel):
    """创建会话请求体。"""

    title: str = Field(
        default=DEFAULT_CONVERSATION_TITLE,
        min_length=1,
        max_length=255,
        description="会话标题",
    )


class ConversationItem(BaseModel):
    """返回给前端的会话信息。"""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    title: str
    status: str
    latest_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationResponse(BaseModel):
    """单个会话创建响应。"""

    message: str
    data: ConversationItem


class ConversationDetailResponse(BaseModel):
    """单个会话详情响应。"""

    message: str
    data: ConversationItem


class ConversationListResponse(BaseModel):
    """会话列表响应。"""

    message: str
    data: list[ConversationItem]
