"""LangChain chat model construction."""

from typing import Any

from src.core.config import AgentModelCandidate, Settings
from src.core.exceptions import AppException


def build_chat_model(
    settings: Settings,
    model_config: AgentModelCandidate | None = None,
) -> Any:
    """Create the configured OpenAI-compatible LangChain chat model."""

    provider = (
        model_config.provider if model_config is not None else settings.agent_model_provider
    ).strip().lower()
    base_url = (
        model_config.base_url if model_config is not None else settings.agent_model_base_url
    ).strip()
    api_key = (
        model_config.api_key if model_config is not None else settings.agent_model_api_key
    ).strip()
    model_name = (
        model_config.model_name if model_config is not None else settings.agent_model_name
    ).strip()

    if provider == "disabled":
        raise AppException(
            503,
            "AGENT_MODEL_NOT_CONFIGURED",
            "智能体模型尚未配置，请补充 AGENT_MODEL_BASE_URL 和 AGENT_MODEL_API_KEY。",
        )

    if provider not in {
        "openai",
        "aihubmix",
        "kimi",
        "xiaomi",
        "local",
    }:
        raise AppException(
            503,
            "AGENT_MODEL_PROVIDER_UNSUPPORTED",
            f"当前智能体 provider `{provider}` 暂不支持。",
        )

    if not base_url or not api_key:
        raise AppException(
            503,
            "AGENT_MODEL_NOT_CONFIGURED",
            "智能体模型缺少 base URL 或 API key 配置。",
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise AppException(
            500,
            "AGENT_LANGCHAIN_NOT_INSTALLED",
            "缺少 langchain-openai 依赖，请先安装 backend/requirements.txt。",
        ) from exc

    extra_body: dict[str, Any] = {}
    if _should_disable_reasoning(settings, provider, model_name):
        # Kimi K2.5 的 thinking 是 Moonshot 请求体字段；通过 extra_body 传递，
        # 避免 LangChain/OpenAI SDK 把它当成未知标准参数处理。
        extra_body["thinking"] = {"type": "disabled"}

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        temperature=_resolve_temperature(settings, provider, model_name),
        max_tokens=(
            settings.agent_max_output_tokens
            if settings.agent_max_output_tokens > 0
            else None
        ),
        timeout=settings.agent_request_timeout_seconds,
        extra_body=extra_body or None,
    )


def _resolve_temperature(
    settings: Settings,
    provider: str,
    model_name: str | None = None,
) -> float:
    """返回当前 provider 可接受的 temperature。

    Moonshot/Kimi 的部分模型会拒绝非 1 的 temperature。项目 `.env` 里
    仍允许保留通用的 `AGENT_TEMPERATURE=0.4`，这里在模型调用边界做兼容，
    避免运行时因为供应商参数约束进入 fallback。
    """

    normalized_model_name = _normalize_model_name(model_name or settings.agent_model_name)
    if _is_kimi_model(provider, normalized_model_name):
        if _should_disable_reasoning(settings, provider, normalized_model_name):
            return 0.6
        return 1.0

    return settings.agent_temperature


def _should_disable_reasoning(
    settings: Settings,
    provider: str,
    model_name: str | None = None,
) -> bool:
    """判断是否要传递供应商专用的关闭推理参数。

    `.env` 里可以保留 `AGENT_DISABLE_REASONING=true`，但 Kimi/Moonshot 的
    OpenAI-compatible 接口不一定接受 GLM 风格的 `thinking` 字段，因此这里
    只对已知需要该参数的 provider 或模型启用，避免请求被上游拒绝。
    """

    if not settings.agent_disable_reasoning:
        return False

    normalized_model_name = _normalize_model_name(model_name or settings.agent_model_name)
    if _is_kimi_model(provider, normalized_model_name):
        return True

    if provider in {"aihubmix"} and normalized_model_name.startswith("glm-"):
        return True

    return normalized_model_name.startswith("glm-")


def _normalize_model_name(model_name: str | None) -> str:
    return (model_name or "").strip().lower()


def _is_kimi_model(provider: str, normalized_model_name: str) -> bool:
    return provider in {"kimi", "moonshot"} or normalized_model_name.startswith("kimi-")
