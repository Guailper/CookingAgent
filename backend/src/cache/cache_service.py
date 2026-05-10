"""Small Redis cache facade used by business services."""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any

from src.cache.redis_client import get_redis_client
from src.core.config import Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """Wrap Redis operations so callers can degrade cleanly when cache fails."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = get_redis_client()

    @property
    def available(self) -> bool:
        return self.client is not None

    def build_key(self, *parts: object) -> str:
        normalized_parts = [self.settings.redis_key_prefix]
        normalized_parts.extend(str(part).strip().replace(" ", "_") for part in parts)
        return ":".join(part for part in normalized_parts if part)

    def get_json(self, key: str) -> Any | None:
        if self.client is None:
            return None

        try:
            raw_value = self.client.get(key)
            if raw_value is None:
                return None
            return json.loads(raw_value)
        except Exception as exc:
            logger.warning("Redis get_json failed.", extra={"key": key}, exc_info=exc)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> bool:
        if self.client is None or ttl_seconds <= 0:
            return False

        try:
            payload = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                default=self._json_default,
            )
            return bool(self.client.setex(key, ttl_seconds, payload))
        except Exception as exc:
            logger.warning("Redis set_json failed.", extra={"key": key}, exc_info=exc)
            return False

    def delete(self, *keys: str) -> None:
        if self.client is None or not keys:
            return

        try:
            self.client.delete(*keys)
        except Exception as exc:
            logger.warning("Redis delete failed.", extra={"keys": keys}, exc_info=exc)

    def delete_pattern(self, pattern: str) -> None:
        if self.client is None:
            return

        try:
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                self.client.delete(*keys)
        except Exception as exc:
            logger.warning("Redis delete_pattern failed.", extra={"pattern": pattern}, exc_info=exc)

    def increment_with_ttl(self, key: str, ttl_seconds: int) -> int | None:
        if self.client is None or ttl_seconds <= 0:
            return None

        try:
            pipeline = self.client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, ttl_seconds, nx=True)
            current_count, _ = pipeline.execute()
            return int(current_count)
        except Exception as exc:
            logger.warning("Redis increment_with_ttl failed.", extra={"key": key}, exc_info=exc)
            return None

    def ttl(self, key: str) -> int | None:
        if self.client is None:
            return None

        try:
            ttl_seconds = int(self.client.ttl(key))
        except Exception as exc:
            logger.warning("Redis ttl failed.", extra={"key": key}, exc_info=exc)
            return None

        return ttl_seconds if ttl_seconds > 0 else None

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
