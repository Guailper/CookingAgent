"""Pydantic models for attachment upload and deletion endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    created_at: datetime


class AttachmentUploadResponse(BaseModel):
    """Response returned after uploading one or more attachments."""

    message: str
    data: list[AttachmentItem]


class AttachmentDeleteResponse(BaseModel):
    """Response returned after deleting an unbound attachment."""

    message: str
