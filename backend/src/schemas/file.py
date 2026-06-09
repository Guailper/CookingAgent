"""Pydantic models for attachment upload and deletion endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import EMBEDDING_STATUS_PENDING


class AttachmentItem(BaseModel):
    """Frontend-safe attachment metadata returned by upload and message APIs."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    original_name: str
    file_ext: str
    mime_type: str
    file_size: int
    attachment_kind: str
    parse_status: str
    embedding_status: str = EMBEDDING_STATUS_PENDING
    created_at: datetime


class AttachmentUploadResponse(BaseModel):
    """Response returned after uploading one or more attachments."""

    message: str
    data: list[AttachmentItem]


class AttachmentDeleteResponse(BaseModel):
    """Response returned after deleting an unbound attachment."""

    message: str


class AttachmentIngestRetryRequest(BaseModel):
    """Optional target override when retrying ingestion for an existing attachment."""

    knowledge_base_id: str | None = Field(default=None, max_length=128)


class AttachmentIngestRetryItem(BaseModel):
    """Retry result returned to the workspace after synchronous ingestion."""

    attachment: AttachmentItem
    assistant_message: dict[str, Any]
    indexed_documents: list[dict[str, Any]]
    skipped_documents: list[dict[str, Any]]


class AttachmentIngestRetryResponse(BaseModel):
    """Response returned after retrying ingestion without uploading again."""

    message: str
    data: AttachmentIngestRetryItem
