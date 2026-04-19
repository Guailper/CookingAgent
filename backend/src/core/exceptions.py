"""项目异常定义与统一处理器。"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """业务异常。

    用于表示“我们预期内的错误”，例如未登录、参数非法、资源不存在等。
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """处理业务异常，统一返回稳定的响应结构。"""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """兜底处理未捕获异常，避免把原始堆栈直接暴露给客户端。"""

    logger.exception("Unhandled exception occurred.", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "服务内部出现未处理异常。",
            "detail": None,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """把项目异常处理器统一注册到 FastAPI 应用上。"""

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
