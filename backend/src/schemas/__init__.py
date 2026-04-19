"""接口请求与响应模型包。"""

from src.schemas.auth import AuthResponse, CurrentUserResponse, LoginRequest, RegisterRequest, UserProfile
from src.schemas.conversation import (
    ConversationDetailResponse,
    ConversationItem,
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
)
from src.schemas.message import (
    CreateMessageRequest,
    MessageItem,
    MessageListResponse,
    MessageResponse,
)

__all__ = [
    "AuthResponse",
    "ConversationDetailResponse",
    "ConversationItem",
    "ConversationListResponse",
    "ConversationResponse",
    "CreateConversationRequest",
    "CurrentUserResponse",
    "LoginRequest",
    "CreateMessageRequest",
    "MessageItem",
    "MessageListResponse",
    "MessageResponse",
    "RegisterRequest",
    "UserProfile",
]
