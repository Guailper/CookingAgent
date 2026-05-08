"""Transcription-only voice service using either a local model or an upstream API."""

import json
import urllib.error
import urllib.request
import uuid
import wave
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from src.core.config import get_settings
from src.core.constants import ALLOWED_AUDIO_EXTENSIONS
from src.core.exceptions import AppException


@lru_cache(maxsize=4)
def _get_faster_whisper_model(
    model_size_or_path: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
    num_workers: int,
    download_root: str,
    local_files_only: bool,
):
    """Cache the local faster-whisper model so we do not reload it on every request."""

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AppException(
            503,
            "VOICE_TRANSCRIBE_LOCAL_DEPENDENCY_MISSING",
            "本地语音转写依赖未安装，请先执行 `pip install -r backend/requirements.txt`。",
        ) from exc

    try:
        model_kwargs = {
            "device": device,
            "compute_type": compute_type,
            "cpu_threads": cpu_threads,
            "num_workers": num_workers,
            "local_files_only": local_files_only,
        }
        if download_root:
            model_kwargs["download_root"] = download_root

        return WhisperModel(model_size_or_path, **model_kwargs)
    except AppException:
        raise
    except Exception as exc:
        raise AppException(
            503,
            "VOICE_TRANSCRIBE_LOCAL_MODEL_LOAD_FAILED",
            f"本地语音模型加载失败，请检查模型配置或运行环境：{exc}",
        ) from exc


class VoiceService:
    """Validate uploaded audio and return text transcripts for the text chat flow."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def transcribe_audio(self, upload: UploadFile, language: str = "zh") -> dict[str, int | str | None]:
        """Transcribe a short audio clip and normalize the response payload."""

        filename = Path(upload.filename or "voice-input").name
        normalized_language = language.strip() or "zh"
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise AppException(
                400,
                "UNSUPPORTED_AUDIO_TYPE",
                "当前仅支持 webm、wav、mp3、m4a 格式的语音文件。",
            )

        file_bytes = await upload.read()
        if not file_bytes:
            raise AppException(400, "EMPTY_AUDIO_FILE", "当前语音文件为空，无法转写。")

        max_audio_size_bytes = self.settings.max_audio_size_mb * 1024 * 1024
        if len(file_bytes) > max_audio_size_bytes:
            raise AppException(
                400,
                "AUDIO_FILE_TOO_LARGE",
                f"当前语音文件超过 {self.settings.max_audio_size_mb}MB 限制。",
            )

        duration_ms = self._guess_duration_ms(file_ext=file_ext, file_bytes=file_bytes)
        self._validate_audio_duration(duration_ms)

        transcript, provider_duration_ms = self._transcribe_with_provider(
            filename=filename,
            mime_type=upload.content_type or "application/octet-stream",
            file_bytes=file_bytes,
            language=normalized_language,
        )
        if duration_ms is None:
            duration_ms = provider_duration_ms

        return {
            "transcript": transcript,
            "duration_ms": duration_ms,
            "mime_type": upload.content_type or "application/octet-stream",
            "file_size": len(file_bytes),
        }

    def _transcribe_with_provider(
        self,
        *,
        filename: str,
        mime_type: str,
        file_bytes: bytes,
        language: str,
    ) -> tuple[str, int | None]:
        """Route transcription requests to the configured provider implementation."""

        provider = self.settings.voice_transcribe_provider
        if provider == "disabled":
            raise AppException(
                503,
                "VOICE_TRANSCRIBE_NOT_CONFIGURED",
                "语音转写服务尚未配置，请先补充转写 provider 的环境变量。",
            )

        if provider in {"openai_compatible", "openai", "aihubmix"}:
            transcript = self._call_openai_compatible_api(
                filename=filename,
                mime_type=mime_type,
                file_bytes=file_bytes,
                language=language,
            )
            return transcript, None

        if provider == "local_faster_whisper":
            return self._call_local_faster_whisper(
                file_bytes=file_bytes,
                language=language,
            )

        raise AppException(
            503,
            "VOICE_TRANSCRIBE_PROVIDER_UNSUPPORTED",
            "当前语音转写 provider 暂不受支持。",
        )

    def _call_openai_compatible_api(
        self,
        *,
        filename: str,
        mime_type: str,
        file_bytes: bytes,
        language: str,
    ) -> str:
        """Call an OpenAI-compatible /audio/transcriptions endpoint without extra deps."""

        if not self.settings.voice_transcribe_base_url or not self.settings.voice_transcribe_api_key:
            raise AppException(
                503,
                "VOICE_TRANSCRIBE_NOT_CONFIGURED",
                "语音转写服务缺少 base URL 或 API key 配置。",
            )

        body, content_type = self._build_multipart_body(
            fields={
                "model": self.settings.voice_transcribe_model,
                "language": language,
            },
            file_field_name="file",
            filename=filename,
            mime_type=mime_type,
            file_bytes=file_bytes,
        )

        request = urllib.request.Request(
            url=f"{self.settings.voice_transcribe_base_url.rstrip('/')}/audio/transcriptions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.voice_transcribe_api_key}",
                "Content-Type": content_type,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.voice_request_timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_payload = exc.read().decode("utf-8", errors="ignore")
            raise AppException(
                502,
                "VOICE_TRANSCRIBE_UPSTREAM_FAILED",
                f"语音转写上游服务返回异常：{error_payload or exc.reason}",
            ) from exc
        except urllib.error.URLError as exc:
            raise AppException(
                502,
                "VOICE_TRANSCRIBE_UPSTREAM_UNAVAILABLE",
                "当前无法连接语音转写上游服务，请稍后重试。",
            ) from exc
        except json.JSONDecodeError as exc:
            raise AppException(
                502,
                "VOICE_TRANSCRIBE_INVALID_RESPONSE",
                "语音转写上游返回了无法解析的响应。",
            ) from exc

        transcript = payload.get("text") or payload.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise AppException(
                502,
                "VOICE_TRANSCRIBE_EMPTY_RESULT",
                "语音转写成功返回，但未得到有效文本结果。",
            )

        return transcript.strip()

    def _call_local_faster_whisper(
        self,
        *,
        file_bytes: bytes,
        language: str,
    ) -> tuple[str, int | None]:
        """Run local speech-to-text with faster-whisper instead of an external API."""

        model = _get_faster_whisper_model(
            self.settings.voice_local_model,
            self.settings.voice_local_device,
            self.settings.voice_local_compute_type,
            self.settings.voice_local_cpu_threads,
            self.settings.voice_local_num_workers,
            self.settings.voice_local_download_root,
            self.settings.voice_local_files_only,
        )

        normalized_language = None if language.lower() == "auto" else language

        try:
            audio_stream = BytesIO(file_bytes)
            segments, info = model.transcribe(
                audio_stream,
                task="transcribe",
                language=normalized_language,
                beam_size=self.settings.voice_local_beam_size,
                vad_filter=self.settings.voice_local_vad_filter,
                condition_on_previous_text=False,
            )
            transcript = "".join(segment.text for segment in segments).strip()
        except AppException:
            raise
        except Exception as exc:
            raise AppException(
                502,
                "VOICE_TRANSCRIBE_LOCAL_RUNTIME_FAILED",
                f"本地语音转写执行失败，请检查模型文件或音频格式：{exc}",
            ) from exc

        if not transcript:
            raise AppException(
                502,
                "VOICE_TRANSCRIBE_EMPTY_RESULT",
                "语音转写成功返回，但未得到有效文本结果。",
            )

        duration_seconds = getattr(info, "duration", None)
        duration_ms = (
            int(duration_seconds * 1000)
            if isinstance(duration_seconds, (int, float))
            else None
        )
        return transcript, duration_ms

    def _build_multipart_body(
        self,
        *,
        fields: dict[str, str],
        file_field_name: str,
        filename: str,
        mime_type: str,
        file_bytes: bytes,
    ) -> tuple[bytes, str]:
        """Encode multipart/form-data for urllib-based upstream requests."""

        boundary = f"----CookingAgentBoundary{uuid.uuid4().hex}"
        chunks: list[bytes] = []

        for field_name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    (
                        f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'
                    ).encode("utf-8"),
                    value.encode("utf-8"),
                    b"\r\n",
                ]
            )

        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{file_field_name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
                file_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )

        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    def _guess_duration_ms(self, *, file_ext: str, file_bytes: bytes) -> int | None:
        """Only WAV duration is cheap to compute locally without extra dependencies."""

        if file_ext != ".wav":
            return None

        try:
            with wave.open(BytesIO(file_bytes), "rb") as handle:
                frame_count = handle.getnframes()
                frame_rate = handle.getframerate()
        except (wave.Error, EOFError):
            return None

        if frame_rate <= 0:
            return None

        return int(frame_count / frame_rate * 1000)

    def _validate_audio_duration(self, duration_ms: int | None) -> None:
        """Enforce the configured duration limit when duration metadata is available."""

        if duration_ms is None:
            return

        max_duration_ms = self.settings.max_audio_duration_seconds * 1000
        if duration_ms > max_duration_ms:
            raise AppException(
                400,
                "AUDIO_DURATION_EXCEEDED",
                f"当前语音时长超过 {self.settings.max_audio_duration_seconds} 秒限制。",
            )
