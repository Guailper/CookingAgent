"""系统日志初始化工具。"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.core.config import BACKEND_ROOT

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_DIR = BACKEND_ROOT / "logs"
MAX_LOG_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5


class _ExactLevelFilter(logging.Filter):
    """只允许指定级别的日志进入对应文件，避免信息日志和警告日志混在一起。"""

    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self.level


def setup_logging(log_level: str = "INFO", log_dir: str | Path | None = None) -> None:
    """初始化控制台日志和文件日志。

    控制台沿用启动进程的日志级别；文件日志按用途拆分：
    `backend.log` 记录全部运行日志，`debug.log`、`info.log`、`warning.log`
    和 `error.log` 分别记录对应级别的信息，便于定位模型、数据库和接口问题。
    """

    root_logger = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)

    root_logger.setLevel(level)
    _ensure_console_handler(root_logger, level, formatter)
    _ensure_file_handlers(root_logger, level, formatter, Path(log_dir or DEFAULT_LOG_DIR))


def _ensure_console_handler(
    root_logger: logging.Logger,
    level: int,
    formatter: logging.Formatter,
) -> None:
    """保留终端日志输出，让开发时仍能直接在控制台看到运行状态。"""

    for handler in root_logger.handlers:
        if not isinstance(handler, RotatingFileHandler):
            handler.setLevel(level)
            handler.setFormatter(formatter)
            return

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def _ensure_file_handlers(
    root_logger: logging.Logger,
    level: int,
    formatter: logging.Formatter,
    log_dir: Path,
) -> None:
    """创建按级别拆分的日志文件处理器，并保证重复初始化不会重复写入。"""

    log_dir.mkdir(parents=True, exist_ok=True)
    handler_specs = [
        ("backend.log", level, None),
        ("debug.log", logging.DEBUG, _ExactLevelFilter(logging.DEBUG)),
        ("info.log", logging.INFO, _ExactLevelFilter(logging.INFO)),
        ("warning.log", logging.WARNING, _ExactLevelFilter(logging.WARNING)),
        ("error.log", logging.ERROR, None),
    ]

    for filename, handler_level, level_filter in handler_specs:
        log_path = log_dir / filename
        if _has_file_handler(root_logger, log_path):
            continue

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(handler_level)
        file_handler.setFormatter(formatter)
        if level_filter is not None:
            file_handler.addFilter(level_filter)
        root_logger.addHandler(file_handler)


def _has_file_handler(root_logger: logging.Logger, log_path: Path) -> bool:
    """判断目标日志文件是否已经注册，避免热重载时重复追加同一条日志。"""

    resolved_log_path = log_path.resolve()
    for handler in root_logger.handlers:
        if not isinstance(handler, RotatingFileHandler):
            continue
        handler_path = Path(handler.baseFilename).resolve()
        if handler_path == resolved_log_path:
            return True
    return False


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger，由统一初始化逻辑决定输出到哪里。"""

    return logging.getLogger(name)
