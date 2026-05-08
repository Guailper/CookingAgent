"""日志初始化工具。"""

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(log_level: str = "INFO") -> None:
    """初始化全局日志格式与级别。

    如果根日志已经有处理器，就只更新级别，避免重复注册导致日志输出多次。
    """

    root_logger = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)

    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    logging.basicConfig(level=level, format=LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger。"""

    return logging.getLogger(name)
