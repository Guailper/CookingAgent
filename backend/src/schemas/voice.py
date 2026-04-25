"""Pydantic models for voice transcription responses."""

from pydantic import BaseModel


class VoiceTranscriptionItem(BaseModel):
    """Normalized transcription payload returned to the frontend composer."""

    transcript: str
    duration_ms: int | None
    mime_type: str
    file_size: int


class VoiceTranscriptionResponse(BaseModel):
    """Envelope for a successful voice transcription request."""

    message: str
    data: VoiceTranscriptionItem
