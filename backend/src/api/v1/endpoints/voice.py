"""Voice transcription endpoint used by the frontend message composer."""

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.api.deps import get_current_user
from src.schemas.voice import VoiceTranscriptionItem, VoiceTranscriptionResponse
from src.services.voice_service import VoiceService

router = APIRouter()


@router.post(
    "/voice/transcriptions",
    response_model=VoiceTranscriptionResponse,
    summary="将语音输入转写为文本",
)
async def transcribe_voice(
    file: UploadFile = File(...),
    language: str = Form(default="zh"),
    _current_user=Depends(get_current_user),
) -> VoiceTranscriptionResponse:
    """Transcribe recorded audio into plain text without creating a voice message."""

    result = await VoiceService().transcribe_audio(file, language=language)
    return VoiceTranscriptionResponse(
        message="语音转写成功。",
        data=VoiceTranscriptionItem.model_validate(result),
    )
