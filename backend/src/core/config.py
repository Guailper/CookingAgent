"""后端统一配置中心。"""

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
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_UPLOAD_DIR = BACKEND_ROOT / "uploads"


def _get_bool_env(name: str, default: bool = False) -> bool:
    """把常见的真值字符串转换成布尔值。"""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    """读取整数环境变量，失败时返回安全默认值。"""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    """读取浮点环境变量，失败时返回安全默认值。"""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        return default


def _get_agent_provider_default() -> str:
    """根据环境变量自动推断智能体默认 provider。"""

    explicit_provider = os.getenv("AGENT_MODEL_PROVIDER") or os.getenv("PROVIDER")
    if explicit_provider and explicit_provider.strip():
        return explicit_provider.strip().lower()

    kimi_base_url = os.getenv("KIMI_BASE_URL")
    kimi_api_key = os.getenv("KIMI_API_KEY")
    if kimi_base_url and kimi_api_key:
        return "kimi"

    base_url = (
        os.getenv("AGENT_MODEL_BASE_URL")
        or os.getenv("MODEL_BASE_URL")
        or os.getenv("AIHUBMIX_BASE_URL")
    )
    api_key = (
        os.getenv("AGENT_MODEL_API_KEY")
        or os.getenv("MODEL_API_KEY")
        or os.getenv("AIHUBMIX_API_KEY")
    )
    return "aihubmix" if base_url and api_key else "disabled"


def _get_voice_provider_default() -> str:
    """根据当前环境自动推断语音转写 provider。"""

    local_model = os.getenv("VOICE_LOCAL_MODEL")
    if local_model and local_model.strip():
        return "local_faster_whisper"

    base_url = os.getenv("VOICE_TRANSCRIBE_BASE_URL") or os.getenv("AIHUBMIX_BASE_URL")
    api_key = os.getenv("VOICE_TRANSCRIBE_API_KEY") or os.getenv("AIHUBMIX_API_KEY")
    return "openai_compatible" if base_url and api_key else "disabled"


def _resolve_agent_model_base_url(provider: str) -> str:
    """按 provider 解析聊天模型 base URL。

    Kimi 是当前项目优先使用的大模型，因此当 provider 明确为 `kimi` 时，
    先读取 `KIMI_BASE_URL`，再回退到通用 `AGENT_MODEL_BASE_URL`。
    """

    if provider == "kimi":
        return (
            os.getenv("KIMI_BASE_URL")
            or os.getenv("AGENT_MODEL_BASE_URL")
            or os.getenv("MODEL_BASE_URL")
            or ""
        ).strip()

    return (
        os.getenv("AGENT_MODEL_BASE_URL")
        or os.getenv("MODEL_BASE_URL")
        or os.getenv("AIHUBMIX_BASE_URL")
        or os.getenv("KIMI_BASE_URL")
        or ""
    ).strip()


def _resolve_agent_model_api_key(provider: str) -> str:
    """按 provider 解析聊天模型 API key。"""

    if provider == "kimi":
        return (
            os.getenv("KIMI_API_KEY")
            or os.getenv("AGENT_MODEL_API_KEY")
            or os.getenv("MODEL_API_KEY")
            or ""
        ).strip()

    return (
        os.getenv("AGENT_MODEL_API_KEY")
        or os.getenv("MODEL_API_KEY")
        or os.getenv("AIHUBMIX_API_KEY")
        or os.getenv("KIMI_API_KEY")
        or ""
    ).strip()


def _resolve_agent_model_name(provider: str) -> str:
    """按 provider 解析聊天模型名称。"""

    if provider == "kimi":
        return (
            os.getenv("KIMI_MODEL_ID")
            or os.getenv("AGENT_MODEL_NAME")
            or os.getenv("MODEL_NAME")
            or os.getenv("MODEL_ID")
            or "kimi-k2.6"
        ).strip()

    return (
        os.getenv("AGENT_MODEL_NAME")
        or os.getenv("MODEL_NAME")
        or os.getenv("MODEL_ID")
        or os.getenv("AIHUBMIX_MODEL_ID")
        or os.getenv("KIMI_MODEL_ID")
        or "gpt-4o-mini"
    ).strip()


def _resolve_project_path(raw_path: str) -> str:
    """把项目根目录下的相对路径解析成绝对路径。"""

    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return str(path.resolve())

    return str((PROJECT_ROOT / path).resolve())


def _get_csv_env(name: str, default: list[str]) -> list[str]:
    """读取逗号分隔的环境变量，并过滤空值。"""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    values = [value.strip() for value in raw_value.split(",")]
    return [value for value in values if value]


@dataclass(frozen=True)
class Settings:
    """后端服务共享的不可变运行时配置。"""

    app_name: str
    app_version: str
    api_v1_prefix: str
    debug: bool
    log_level: str
    auto_create_tables: bool
    sqlalchemy_echo: bool
    app_secret_key: str
    access_token_expire_minutes: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_use_ssl: bool
    smtp_use_tls: bool
    smtp_timeout_seconds: int

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

    agent_model_provider: str
    agent_model_base_url: str
    agent_model_api_key: str
    agent_model_name: str
    agent_request_timeout_seconds: int
    agent_max_context_messages: int
    agent_temperature: float
    agent_max_output_tokens: int
    agent_disable_reasoning: bool

    project_root: str
    rag_embedding_provider: str
    rag_embedding_model_path: str
    rag_embedding_normalize: bool
    rag_embedding_base_url: str
    rag_embedding_api_key: str
    rag_embedding_model: str
    rag_rerank_provider: str
    rag_rerank_model_path: str
    rag_rerank_use_fp16: bool
    rag_rerank_base_url: str
    rag_rerank_api_key: str
    rag_rerank_model: str
    milvus_uri: str
    milvus_token: str
    milvus_database: str
    milvus_collection: str
    rag_vector_top_k: int
    rag_final_top_k: int
    rag_min_score: float
    rag_chunk_target_size: int
    rag_chunk_max_size: int
    rag_chunk_overlap_size: int
    rag_request_timeout_seconds: int
    rag_default_knowledge_base_ids: list[str]

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
        """返回 SQLAlchemy 使用的 MySQL 连接串。"""

        safe_password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{safe_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )

    @property
    def upload_dir_path(self) -> Path:
        """把上传目录解析成绝对路径。"""

        return Path(self.upload_dir).expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    """读取并缓存环境变量配置。"""

    # 语音配置只用于语音转文本，不用于实时通话场景。
    voice_base_url = os.getenv("VOICE_TRANSCRIBE_BASE_URL") or os.getenv("AIHUBMIX_BASE_URL", "")
    voice_api_key = os.getenv("VOICE_TRANSCRIBE_API_KEY") or os.getenv("AIHUBMIX_API_KEY", "")
    voice_local_download_root = os.getenv("VOICE_LOCAL_DOWNLOAD_ROOT", "").strip()
    agent_provider = os.getenv(
        "AGENT_MODEL_PROVIDER",
        _get_agent_provider_default(),
    ).strip().lower()
    agent_base_url = _resolve_agent_model_base_url(agent_provider)
    agent_api_key = _resolve_agent_model_api_key(agent_provider)
    agent_model_name = _resolve_agent_model_name(agent_provider)

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
        smtp_host=os.getenv("SMTP_HOST", "smtp.qq.com").strip(),
        smtp_port=_get_int_env("SMTP_PORT", 465),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
        smtp_from=os.getenv("SMTP_FROM", "").strip(),
        smtp_use_ssl=_get_bool_env("SMTP_USE_SSL", True),
        smtp_use_tls=_get_bool_env("SMTP_USE_TLS", False),
        smtp_timeout_seconds=_get_int_env("SMTP_TIMEOUT_SECONDS", 10),
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
        agent_model_provider=agent_provider,
        agent_model_base_url=agent_base_url.strip(),
        agent_model_api_key=agent_api_key.strip(),
        agent_model_name=agent_model_name.strip(),
        agent_request_timeout_seconds=_get_int_env("AGENT_REQUEST_TIMEOUT_SECONDS", 90),
        agent_max_context_messages=_get_int_env("AGENT_MAX_CONTEXT_MESSAGES", 10),
        agent_temperature=_get_float_env("AGENT_TEMPERATURE", 0.4),
        agent_max_output_tokens=_get_int_env("AGENT_MAX_OUTPUT_TOKENS", 800),
        agent_disable_reasoning=_get_bool_env(
            "AGENT_DISABLE_REASONING",
            agent_model_name.strip().lower().startswith("glm-"),
        ),
        project_root=str(PROJECT_ROOT.resolve()),
        rag_embedding_provider=os.getenv(
            "RAG_EMBEDDING_PROVIDER",
            "local_huggingface",
        ).strip().lower(),
        rag_embedding_model_path=_resolve_project_path(
            os.getenv("RAG_EMBEDDING_MODEL_PATH", "models/bge-small-zh-v1.5").strip()
        ),
        rag_embedding_normalize=_get_bool_env("RAG_EMBEDDING_NORMALIZE", True),
        rag_embedding_base_url=(
            os.getenv("RAG_EMBEDDING_BASE_URL")
            or os.getenv("AGENT_MODEL_BASE_URL")
            or os.getenv("MODEL_BASE_URL")
            or os.getenv("AIHUBMIX_BASE_URL")
            or ""
        ).strip(),
        rag_embedding_api_key=(
            os.getenv("RAG_EMBEDDING_API_KEY")
            or os.getenv("AGENT_MODEL_API_KEY")
            or os.getenv("MODEL_API_KEY")
            or os.getenv("AIHUBMIX_API_KEY")
            or ""
        ).strip(),
        rag_embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        rag_rerank_provider=os.getenv(
            "RAG_RERANK_PROVIDER",
            "local_huggingface",
        ).strip().lower(),
        rag_rerank_model_path=_resolve_project_path(
            os.getenv("RAG_RERANK_MODEL_PATH", "models/bge-reranker-v2-m3").strip()
        ),
        rag_rerank_use_fp16=_get_bool_env("RAG_RERANK_USE_FP16", True),
        rag_rerank_base_url=os.getenv("RAG_RERANK_BASE_URL", "").strip(),
        rag_rerank_api_key=os.getenv("RAG_RERANK_API_KEY", "").strip(),
        rag_rerank_model=os.getenv("RAG_RERANK_MODEL", "bge-reranker-v2-m3").strip(),
        milvus_uri=os.getenv("MILVUS_URI", "http://127.0.0.1:19530").strip(),
        milvus_token=os.getenv("MILVUS_TOKEN", "").strip(),
        milvus_database=os.getenv("MILVUS_DATABASE", "default").strip(),
        milvus_collection=os.getenv("MILVUS_COLLECTION", "rag_chunks").strip(),
        rag_vector_top_k=_get_int_env("RAG_VECTOR_TOP_K", 20),
        rag_final_top_k=_get_int_env("RAG_FINAL_TOP_K", 5),
        rag_min_score=_get_float_env("RAG_MIN_SCORE", 0.25),
        rag_chunk_target_size=_get_int_env("RAG_CHUNK_TARGET_SIZE", 700),
        rag_chunk_max_size=_get_int_env("RAG_CHUNK_MAX_SIZE", 1000),
        rag_chunk_overlap_size=_get_int_env("RAG_CHUNK_OVERLAP_SIZE", 100),
        rag_request_timeout_seconds=_get_int_env("RAG_REQUEST_TIMEOUT_SECONDS", 30),
        rag_default_knowledge_base_ids=_get_csv_env(
            "RAG_DEFAULT_KNOWLEDGE_BASE_IDS",
            ["cookbook"],
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
