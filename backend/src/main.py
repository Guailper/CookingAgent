"""FastAPI 应用入口。

这个文件负责把配置、日志、异常处理、数据库初始化和路由注册串起来，
让整个后端具备一个可继续扩展的最小可运行骨架。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.router import api_router
from src.core.config import get_settings
from src.core.constants import APP_NAME, APP_VERSION
from src.core.exceptions import register_exception_handlers
from src.core.logging import get_logger, setup_logging
from src.db.session import create_all_tables

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """在应用启动和关闭时执行统一的资源管理逻辑。"""

    logger.info("Starting backend application.")

    # 开发阶段可通过环境变量控制是否自动建表，避免每次启动都误改数据库。
    if settings.auto_create_tables:
        create_all_tables()
        logger.info("Database tables checked and created if necessary.")

    yield

    logger.info("Shutting down backend application.")


def create_application() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        debug=settings.debug,
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", summary="服务健康检查")
    async def health_check() -> dict[str, str]:
        """返回最基础的健康状态，便于部署和联调时探活。"""

        return {"status": "ok", "service": APP_NAME}

    return app


app = create_application()
