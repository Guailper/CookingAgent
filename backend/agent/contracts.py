"""Agent 层与 service 层之间的稳定数据契约。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentContextMessage:
    """传入 LangChain Agent 的轻量历史消息。"""

    role: str
    content: str


@dataclass(frozen=True)
class AgentTurnContext:
    """执行一轮 Agent 对话所需的业务上下文。"""

    conversation_public_id: str
    user_public_id: str
    trigger_message_public_id: str
    user_message_text: str
    recent_messages: list[AgentContextMessage] = field(default_factory=list)
    attachment_public_ids: list[str] = field(default_factory=list)
    knowledge_base_public_ids: list[str] = field(default_factory=list)
    request_options: dict[str, Any] = field(default_factory=dict)
    attachment_context: list[dict[str, Any]] = field(default_factory=list)
    rag_context: "RagContext | None" = None


@dataclass(frozen=True)
class AgentTurnResult:
    """LangChain Agent 返回给 service 层的统一结果。"""

    reply_text: str
    intent_type: str
    workflow_name: str
    model_name: str | None = None
    output_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionIntent:
    """The high-level action selected before workflow execution."""

    intent_type: str
    confidence: float
    source: str
    reason: str


@dataclass(frozen=True)
class RagContext:
    """Structured result of the backend default RAG retrieval step."""

    enabled: bool
    status: str
    query: str
    knowledge_base_public_ids: list[str] = field(default_factory=list)
    chunks: list["RetrievedChunk"] = field(default_factory=list)
    decision: "RetrievalDecision | None" = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class RetrievalDecision:
    """Decision made before running vector retrieval."""

    should_retrieve: bool
    reason: str
    source: str


@dataclass(frozen=True)
class RetrievedChunk:
    """RAG 检索结果的标准片段结构。"""

    content: str
    document_title: str | None = None
    chunk_index: int | None = None
    page_no: int | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
