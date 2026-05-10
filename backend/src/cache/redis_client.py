"""Redis client factory with safe optional dependency handling."""

from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)
_redis_client: Any | None = None


def get_redis_client() -> Any | None:
    """Return a shared Redis client, or None when Redis is disabled/unavailable."""

    global _redis_client
    settings = get_settings()
    if not settings.redis_enabled:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
    except ImportError:
        logger.warning("Redis package is not installed; cache is disabled.")
        return None

    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
            decode_responses=True,
        )
        client.ping()
        _redis_client = client
    except Exception as exc:
        logger.warning("Redis is unavailable; cache is disabled.", exc_info=exc)
        return None

    return _redis_client


def clear_redis_client_cache() -> None:
    """Clear the cached Redis client, mainly for tests or config reloads."""

    global _redis_client
    _redis_client = None
