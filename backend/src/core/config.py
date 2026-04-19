"""应用配置读取模块。

这里集中管理环境变量读取和类型转换逻辑，避免数据库、日志和应用设置
在不同文件里各自读取一遍环境变量。
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv

from src.core.constants import ACCESS_TOKEN_EXPIRE_MINUTES, API_V1_PREFIX, APP_NAME, APP_VERSION

load_dotenv()


def _get_bool_env(name: str, default: bool = False) -> bool:
    """把环境变量转换成布尔值。"""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    """把环境变量转换成整数；格式非法时退回默认值。"""

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """应用运行配置。"""

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

    @property
    def database_url(self) -> str:
        """返回 SQLAlchemy 使用的 MySQL 连接串。"""

        safe_password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{safe_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )


@lru_cache
def get_settings() -> Settings:
    """读取并缓存应用配置。"""

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
    )
