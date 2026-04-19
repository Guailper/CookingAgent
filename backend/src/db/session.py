"""数据库会话与建表辅助工具。"""

from src.core.logging import get_logger
from src.db.base import Base, SessionLocal, engine, get_db
from src.db.models import import_all_models

logger = get_logger(__name__)


def create_all_tables() -> None:
    """导入所有模型并创建数据库表。

    这里显式导入模型是有意为之，因为 SQLAlchemy 只有在模型被导入后，
    才能把它们注册到 `Base.metadata` 中。
    """

    import_all_models()
    Base.metadata.create_all(bind=engine)
    logger.info("All registered tables have been created or already exist.")


def get_session_factory():
    """返回底层会话工厂，方便脚本或任务系统按需创建会话。"""

    return SessionLocal
