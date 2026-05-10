"""Redis-backed fixed-window rate limiting."""

from src.cache.cache_service import CacheService
from src.core.exceptions import AppException


class RateLimiter:
    """Apply best-effort rate limits when Redis is available."""

    def __init__(self, cache: CacheService | None = None) -> None:
        self.cache = cache or CacheService()

    def require_allowed(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
        error_code: str,
        message: str,
    ) -> None:
        current_count = self.cache.increment_with_ttl(key, window_seconds)
        if current_count is None:
            return

        if current_count > limit:
            raise AppException(
                429,
                error_code,
                message,
                {"limit": limit, "window_seconds": window_seconds},
            )
