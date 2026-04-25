"""Centralized environment-backed settings for the FastAPI backend."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from src.core.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    API_V1_PREFIX,
    APP_NAME,
    APP_VERSION,
    DEFAULT_MAX_ATTACHMENT_FILES,
    DEFAULT_MAX_AUDIO_DURATION_SECONDS,
    DEFAULT_MAX_AUDIO_SIZE_MB,
    DEFAULT_MAX_UPLOAD_SIZE_MB,
    DEFAULT_VOICE_REQUEST_TIMEOUT_SECONDS,
)

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UPLOAD_DIR = BACKEND_ROOT / "uploads"


def _get_bool_env(name: str, default: bool = False) -> bool:
    """Convert common truthy strings into booleans."""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    """Return an integer environment value with a safe fallback."""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_voice_provider_default() -> str:
    """Pick a sensible default voice provider based on the configured runtime."""

    local_model = os.getenv("VOICE_LOCAL_MODEL")
    if local_model and local_model.strip():
        return "local_faster_whisper"

    base_url = os.getenv("VOICE_TRANSCRIBE_BASE_URL") or os.getenv("AIHUBMIX_BASE_URL")
    api_key = os.getenv("VOICE_TRANSCRIBE_API_KEY") or os.getenv("AIHUBMIX_API_KEY")
    return "openai_compatible" if base_url and api_key else "disabled"


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings shared across backend services."""

    app_name: str
    app_version: str
    api_v1_prefix: str
    debug: bool
    log_level: str
    auto_create_tables: bool
    sqlalchemy_echo: bool
    app_secret_key: str
    access_token_expire_minutes: int
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    mysql_charset: str
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout: int
    db_pool_recycle: int
    upload_dir: str
    max_upload_size_mb: int
    max_message_attachments: int
    max_audio_size_mb: int
    max_audio_duration_seconds: int
    voice_transcribe_provider: str
    voice_transcribe_base_url: str
    voice_transcribe_api_key: str
    voice_transcribe_model: str
    voice_request_timeout_seconds: int
    voice_local_model: str
    voice_local_device: str
    voice_local_compute_type: str
    voice_local_cpu_threads: int
    voice_local_num_workers: int
    voice_local_download_root: str
    voice_local_files_only: bool
    voice_local_beam_size: int
    voice_local_vad_filter: bool

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy MySQL connection URL."""

        safe_password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{safe_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )

    @property
    def upload_dir_path(self) -> Path:
        """Resolve the configured upload directory as an absolute path."""

        return Path(self.upload_dir).expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    """Read and cache application settings from the environment."""

    # Voice settings are only used for speech-to-text, not call-style audio sessions.
    voice_base_url = os.getenv("VOICE_TRANSCRIBE_BASE_URL") or os.getenv("AIHUBMIX_BASE_URL", "")
    voice_api_key = os.getenv("VOICE_TRANSCRIBE_API_KEY") or os.getenv("AIHUBMIX_API_KEY", "")
    voice_local_download_root = os.getenv("VOICE_LOCAL_DOWNLOAD_ROOT", "").strip()

    return Settings(
        app_name=os.getenv("APP_NAME", APP_NAME),
        app_version=os.getenv("APP_VERSION", APP_VERSION),
        api_v1_prefix=os.getenv("API_V1_PREFIX", API_V1_PREFIX),
        debug=_get_bool_env("APP_DEBUG", False),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        auto_create_tables=_get_bool_env("AUTO_CREATE_TABLES", False),
        sqlalchemy_echo=_get_bool_env("SQLALCHEMY_ECHO", False),
        app_secret_key=os.getenv("APP_SECRET_KEY", "change-this-in-production"),
        access_token_expire_minutes=_get_int_env(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            ACCESS_TOKEN_EXPIRE_MINUTES,
        ),
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=_get_int_env("MYSQL_PORT", 3306),
        mysql_database=os.getenv("MYSQL_DATABASE", "cooking_agent_db"),
        mysql_user=os.getenv("MYSQL_USER", "root"),
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        mysql_charset=os.getenv("MYSQL_CHARSET", "utf8mb4"),
        db_pool_size=_get_int_env("DB_POOL_SIZE", 10),
        db_max_overflow=_get_int_env("DB_MAX_OVERFLOW", 20),
        db_pool_timeout=_get_int_env("DB_POOL_TIMEOUT", 30),
        db_pool_recycle=_get_int_env("DB_POOL_RECYCLE", 1800),
        upload_dir=os.getenv("UPLOAD_DIR", str(DEFAULT_UPLOAD_DIR)),
        max_upload_size_mb=_get_int_env("MAX_UPLOAD_SIZE_MB", DEFAULT_MAX_UPLOAD_SIZE_MB),
        max_message_attachments=_get_int_env(
            "MAX_MESSAGE_ATTACHMENTS",
            DEFAULT_MAX_ATTACHMENT_FILES,
        ),
        max_audio_size_mb=_get_int_env("MAX_AUDIO_SIZE_MB", DEFAULT_MAX_AUDIO_SIZE_MB),
        max_audio_duration_seconds=_get_int_env(
            "MAX_AUDIO_DURATION_SECONDS",
            DEFAULT_MAX_AUDIO_DURATION_SECONDS,
        ),
        voice_transcribe_provider=os.getenv(
            "VOICE_TRANSCRIBE_PROVIDER",
            _get_voice_provider_default(),
        ).strip().lower(),
        voice_transcribe_base_url=voice_base_url.strip(),
        voice_transcribe_api_key=voice_api_key.strip(),
        voice_transcribe_model=os.getenv("VOICE_TRANSCRIBE_MODEL", "whisper-1").strip(),
        voice_request_timeout_seconds=_get_int_env(
            "VOICE_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_VOICE_REQUEST_TIMEOUT_SECONDS,
        ),
        voice_local_model=os.getenv("VOICE_LOCAL_MODEL", "small").strip(),
        voice_local_device=os.getenv("VOICE_LOCAL_DEVICE", "auto").strip().lower(),
        voice_local_compute_type=os.getenv("VOICE_LOCAL_COMPUTE_TYPE", "int8").strip().lower(),
        voice_local_cpu_threads=_get_int_env("VOICE_LOCAL_CPU_THREADS", 0),
        voice_local_num_workers=_get_int_env("VOICE_LOCAL_NUM_WORKERS", 1),
        voice_local_download_root=voice_local_download_root,
        voice_local_files_only=_get_bool_env("VOICE_LOCAL_FILES_ONLY", False),
        voice_local_beam_size=_get_int_env("VOICE_LOCAL_BEAM_SIZE", 5),
        voice_local_vad_filter=_get_bool_env("VOICE_LOCAL_VAD_FILTER", True),
    )
