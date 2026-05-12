"""Weather query tool adapter."""

from datetime import datetime, timedelta
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.core.config import Settings, get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_DAY_OFFSET_RE = re.compile(r"^(?P<offset>[+-]?\d+)d$")
_MAX_FORECAST_DAYS = 7



def build_weather_tool(settings: Settings | None = None):
    """Create a weather tool backed by QWeather."""

    tool_settings = settings or get_settings()

    def get_weather(location: str, date: str = "now") -> str:
        """Query weather by city/district name and relative date such as now, 0d, 1d, or 2d."""

        city_name = (location or "").strip()
        query_date = (date or "now").strip().lower()
        if not city_name:
            return "请提供要查询天气的城市或区县名称。"

        if not tool_settings.weather_api_key:
            return "天气查询工具未配置 WEATHER_API_KEY，暂时无法查询实时天气。"

        date_offset = _parse_day_offset(query_date)
        if date_offset is None:
            return "天气查询日期仅支持 now、0d、1d、2d 这类相对日期格式。"
        if date_offset < 0:
            return "当前天气工具暂不支持查询历史天气，请改查当前或未来 7 天内的天气。"
        if date_offset >= _MAX_FORECAST_DAYS:
            return "当前天气工具最多支持查询未来 7 天内的天气。"

        try:
            with httpx.Client(timeout=tool_settings.weather_request_timeout_seconds) as client:
                location_id, resolved_name = _lookup_location_id(client, tool_settings, city_name)
                print(f"Resolved location '{city_name}' to id '{location_id}' with name '{resolved_name}'.")
                weather_data = _fetch_weather(client, tool_settings, location_id, date_offset)
                return _render_weather(resolved_name or city_name, date_offset, weather_data)
        except httpx.HTTPError as exc:
            logger.warning("Weather request failed.", exc_info=exc)
            return f"天气服务请求失败，暂时无法获取 {city_name} 的天气。"
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            logger.exception("Unexpected weather tool failure.", exc_info=exc)
            return f"天气查询失败，暂时无法获取 {city_name} 的天气。"

    return get_weather


def _parse_day_offset(date: str) -> int | None:
    if date in {"now", "0d", "today"}:
        return 0

    matched = _DAY_OFFSET_RE.match(date)
    if not matched:
        return None

    return int(matched.group("offset"))


def _lookup_location_id(
    client: httpx.Client,
    settings: Settings,
    city_name: str,
) -> tuple[str, str]:
    response = client.get(
        settings.weather_geo_base_url,
        params={
            "location": city_name,
            "key": settings.weather_api_key,
            "range": "cn",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "200" or not payload.get("location"):
        raise ValueError(f"未找到城市或区县：{city_name}。请尝试使用更明确的中文地名。")

    first_location = payload["location"][0]
    return str(first_location["id"]), str(first_location.get("name") or city_name)


def _fetch_weather(
    client: httpx.Client,
    settings: Settings,
    location_id: str,
    date_offset: int,
) -> dict[str, Any]:
    endpoint = "now" if date_offset == 0 else "7d"
    response = client.get(
        settings.weather_api_base_url + endpoint,
        params={
            "location": location_id,
            "key": settings.weather_api_key,
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "200":
        raise ValueError(f"天气服务返回异常：{payload.get('code', 'unknown')}")
    return payload


def _render_weather(location: str, date_offset: int, payload: dict[str, Any]) -> str:
    if date_offset == 0:
        now = payload.get("now") or {}
        weather = now.get("text") or "未知"
        temperature = now.get("temp") or "未知"
        feels_like = now.get("feelsLike")
        humidity = now.get("humidity")
        wind = now.get("windDir")
        details = [f"{location}当前天气：{weather}，气温 {temperature}°C"]
        if feels_like:
            details.append(f"体感 {feels_like}°C")
        if humidity:
            details.append(f"湿度 {humidity}%")
        if wind:
            details.append(f"风向 {wind}")
        return "，".join(details) + "。"

    daily_items = payload.get("daily") or []
    if date_offset >= len(daily_items):
        raise ValueError("天气服务没有返回对应日期的预报。")

    daily = daily_items[date_offset]
    target_date = daily.get("fxDate") or (
        datetime.now().date() + timedelta(days=date_offset)
    ).isoformat()
    return (
        f"{location}{target_date}天气：白天 {daily.get('textDay', '未知')}，"
        f"夜间 {daily.get('textNight', '未知')}，"
        f"气温 {daily.get('tempMin', '未知')}~{daily.get('tempMax', '未知')}°C，"
        f"湿度 {daily.get('humidity', '未知')}%，"
        f"风向 {daily.get('windDirDay', '未知')}。"
    )
