"""后端统一配置中心。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
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

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_UPLOAD_DIR = BACKEND_ROOT / "uploads"
DEFAULT_MINERU_OUTPUT_DIR = DEFAULT_UPLOAD_DIR / "mineru"

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env", override=True)


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


def _get_agent_model_fallback_order(primary_provider: str) -> list[str]:
    """Return provider priority for model fallback."""

    configured_order = _get_csv_env("AGENT_MODEL_FALLBACK_ORDER", [])
    if configured_order:
        return configured_order

    order = [primary_provider]
    if os.getenv("XIAOMI_BASE_URL") and os.getenv("XIAOMI_API_KEY"):
        order.append("xiaomi")
    if os.getenv("AIHUBMIX_BASE_URL") and os.getenv("AIHUBMIX_API_KEY"):
        order.append("aihubmix")
    if (
        os.getenv("LOCAL_MODEL_BASE_URL")
        or os.getenv("OLLAMA_BASE_URL")
        or os.getenv("LOCAL_MODEL_ID")
        or os.getenv("LOCAL_MODEL_NAME")
        or os.getenv("OLLAMA_MODEL_ID")
        or os.getenv("OLLAMA_MODEL_NAME")
    ):
        order.append("local")

    return order


def _build_agent_model_candidates(
    *,
    primary_provider: str,
    primary_base_url: str,
    primary_api_key: str,
    primary_model_name: str,
) -> list[AgentModelCandidate]:
    """Build configured model endpoints in retry priority order."""

    candidates: list[AgentModelCandidate] = []
    seen_providers: set[str] = set()
    for raw_provider in _get_agent_model_fallback_order(primary_provider):
        provider = _normalize_agent_fallback_provider(raw_provider, primary_provider)
        if not provider or provider in seen_providers:
            continue

        candidate = _resolve_agent_model_candidate(
            provider=provider,
            primary_provider=primary_provider,
            primary_base_url=primary_base_url,
            primary_api_key=primary_api_key,
            primary_model_name=primary_model_name,
        )
        if candidate is None:
            continue

        seen_providers.add(provider)
        candidates.append(candidate)

    return candidates


def _normalize_agent_fallback_provider(raw_provider: str, primary_provider: str) -> str:
    provider = (raw_provider or "").strip().lower()
    if provider in {"primary", "default"}:
        return primary_provider
    if provider == "ollama":
        return "local"
    return provider


def _resolve_agent_model_candidate(
    *,
    provider: str,
    primary_provider: str,
    primary_base_url: str,
    primary_api_key: str,
    primary_model_name: str,
) -> AgentModelCandidate | None:
    if provider == "disabled":
        return None

    if provider == primary_provider:
        base_url = primary_base_url
        api_key = primary_api_key
        model_name = primary_model_name
    elif provider in {"kimi", "moonshot"}:
        base_url = os.getenv("KIMI_BASE_URL", "").strip()
        api_key = os.getenv("KIMI_API_KEY", "").strip()
        model_name = os.getenv("KIMI_MODEL_ID", "kimi-k2.6").strip()
    elif provider == "xiaomi":
        base_url = os.getenv("XIAOMI_BASE_URL", "").strip()
        api_key = os.getenv("XIAOMI_API_KEY", "").strip()
        model_name = os.getenv("XIAOMI_MODEL_ID", "").strip()
    elif provider == "aihubmix":
        base_url = os.getenv("AIHUBMIX_BASE_URL", "").strip()
        api_key = os.getenv("AIHUBMIX_API_KEY", "").strip()
        model_name = os.getenv("AIHUBMIX_MODEL_ID", "gpt-4o-mini").strip()
    elif provider == "openai":
        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or "https://api.openai.com/v1"
        ).strip()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model_name = os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini").strip()
    elif provider == "local":
        base_url = (
            os.getenv("LOCAL_MODEL_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or ""
        ).strip()
        api_key = (
            os.getenv("LOCAL_MODEL_API_KEY")
            or os.getenv("OLLAMA_API_KEY")
            or "not-needed"
        ).strip()
        model_name = (
            os.getenv("LOCAL_MODEL_ID")
            or os.getenv("LOCAL_MODEL_NAME")
            or os.getenv("OLLAMA_MODEL_ID")
            or os.getenv("OLLAMA_MODEL_NAME")
            or ""
        ).strip()
    else:
        return None

    if not base_url or not model_name:
        return None
    if provider != "local" and not api_key:
        return None

    return AgentModelCandidate(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
    )


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


def _get_json_object_env(name: str) -> dict[str, Any]:
    """Read a JSON object from an environment variable."""

    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return {}

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}

    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class AgentModelCandidate:
    """One OpenAI-compatible chat model endpoint in the fallback chain."""

    provider: str
    base_url: str
    api_key: str
    model_name: str


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
    redis_enabled: bool
    redis_url: str
    redis_key_prefix: str
    redis_socket_timeout_seconds: int
    current_user_cache_ttl_seconds: int
    conversation_cache_ttl_seconds: int
    message_cache_ttl_seconds: int
    rag_cache_ttl_seconds: int
    email_code_rate_limit_count: int
    email_code_rate_limit_window_seconds: int
    login_rate_limit_count: int
    login_rate_limit_window_seconds: int
    agent_rate_limit_count: int
    agent_rate_limit_window_seconds: int

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
    mineru_command: str
    mineru_output_dir: str
    mineru_backend: str
    mineru_method: str
    mineru_lang: str
    mineru_api_url: str
    mineru_parse_timeout_seconds: int
    mineru_extra_args: list[str]
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
    agent_summary_trigger_messages: int
    agent_summary_batch_messages: int
    agent_summary_max_chars: int
    agent_temperature: float
    agent_max_output_tokens: int
    agent_disable_reasoning: bool
    agent_model_candidates: list[AgentModelCandidate]
    agent_mcp_servers: dict[str, dict[str, Any]]
    weather_api_key: str
    weather_api_base_url: str
    weather_geo_base_url: str
    weather_request_timeout_seconds: int
    serpapi_api_key: str
    serpapi_search_url: str
    web_search_request_timeout_seconds: int

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
    rag_query_rewrite_enabled: bool
    rag_query_rewrite_temperature: float
    rag_query_rewrite_max_chars: int
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

    @property
    def mineru_output_dir_path(self) -> Path:
        """把 MinerU 解析产物目录解析成绝对路径。"""

        return Path(self.mineru_output_dir).expanduser().resolve()


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
        redis_enabled=_get_bool_env("REDIS_ENABLED", False),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
        redis_key_prefix=os.getenv("REDIS_KEY_PREFIX", "cooking_agent").strip(),
        redis_socket_timeout_seconds=_get_int_env("REDIS_SOCKET_TIMEOUT_SECONDS", 2),
        current_user_cache_ttl_seconds=_get_int_env("CURRENT_USER_CACHE_TTL_SECONDS", 300),
        conversation_cache_ttl_seconds=_get_int_env("CONVERSATION_CACHE_TTL_SECONDS", 60),
        message_cache_ttl_seconds=_get_int_env("MESSAGE_CACHE_TTL_SECONDS", 60),
        rag_cache_ttl_seconds=_get_int_env("RAG_CACHE_TTL_SECONDS", 1800),
        email_code_rate_limit_count=_get_int_env("EMAIL_CODE_RATE_LIMIT_COUNT", 5),
        email_code_rate_limit_window_seconds=_get_int_env(
            "EMAIL_CODE_RATE_LIMIT_WINDOW_SECONDS",
            300,
        ),
        login_rate_limit_count=_get_int_env("LOGIN_RATE_LIMIT_COUNT", 10),
        login_rate_limit_window_seconds=_get_int_env("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300),
        agent_rate_limit_count=_get_int_env("AGENT_RATE_LIMIT_COUNT", 20),
        agent_rate_limit_window_seconds=_get_int_env("AGENT_RATE_LIMIT_WINDOW_SECONDS", 300),
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
        mineru_command=os.getenv("MINERU_COMMAND", "mineru").strip() or "mineru",
        mineru_output_dir=_resolve_project_path(
            os.getenv("MINERU_OUTPUT_DIR", str(DEFAULT_MINERU_OUTPUT_DIR)).strip()
        ),
        mineru_backend=os.getenv("MINERU_BACKEND", "pipeline").strip(),
        mineru_method=os.getenv("MINERU_METHOD", "auto").strip(),
        mineru_lang=os.getenv("MINERU_LANG", "ch").strip(),
        mineru_api_url=os.getenv("MINERU_API_URL", "").strip(),
        mineru_parse_timeout_seconds=_get_int_env("MINERU_PARSE_TIMEOUT_SECONDS", 1800),
        mineru_extra_args=_get_csv_env("MINERU_EXTRA_ARGS", []),
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
        agent_summary_trigger_messages=_get_int_env("AGENT_SUMMARY_TRIGGER_MESSAGES", 12),
        agent_summary_batch_messages=_get_int_env("AGENT_SUMMARY_BATCH_MESSAGES", 8),
        agent_summary_max_chars=_get_int_env("AGENT_SUMMARY_MAX_CHARS", 1200),
        agent_temperature=_get_float_env("AGENT_TEMPERATURE", 0.4),
        agent_max_output_tokens=_get_int_env("AGENT_MAX_OUTPUT_TOKENS", 800),
        agent_disable_reasoning=_get_bool_env(
            "AGENT_DISABLE_REASONING",
            agent_model_name.strip().lower().startswith("glm-"),
        ),
        agent_model_candidates=_build_agent_model_candidates(
            primary_provider=agent_provider,
            primary_base_url=agent_base_url.strip(),
            primary_api_key=agent_api_key.strip(),
            primary_model_name=agent_model_name.strip(),
        ),
        agent_mcp_servers=_get_json_object_env("AGENT_MCP_SERVERS_JSON"),
        weather_api_key=(
            os.getenv("WEATHER_API_KEY")
            or ""
        ).strip(),
        weather_api_base_url=os.getenv(
            "WEATHER_API_BASE_URL",
            "https://devapi.qweather.com/v7/weather",
        ).strip(),
        weather_geo_base_url=os.getenv(
            "WEATHER_GEO_BASE_URL",
            "https://geoapi.qweather.com/geo/v2/city/lookup",
        ).strip(),
        weather_request_timeout_seconds=_get_int_env("WEATHER_REQUEST_TIMEOUT_SECONDS", 10),
        serpapi_api_key=(
            os.getenv("SERPAPI_API_KEY")
            or os.getenv("SERP_API_KEY")
            or ""
        ).strip(),
        serpapi_search_url=os.getenv(
            "SERPAPI_SEARCH_URL",
            "https://serpapi.com/search.json",
        ).strip(),
        web_search_request_timeout_seconds=_get_int_env(
            "WEB_SEARCH_REQUEST_TIMEOUT_SECONDS",
            15,
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
        rag_query_rewrite_enabled=_get_bool_env("RAG_QUERY_REWRITE_ENABLED", True),
        rag_query_rewrite_temperature=_get_float_env("RAG_QUERY_REWRITE_TEMPERATURE", 0.6),
        rag_query_rewrite_max_chars=_get_int_env("RAG_QUERY_REWRITE_MAX_CHARS", 180),
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
