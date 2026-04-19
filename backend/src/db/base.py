"""数据库基类、引擎和会话工厂。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import get_settings

settings = get_settings()

# 统一从配置中心读取数据库参数，避免连接信息分散在多个文件中。
engine = create_engine(
    settings.database_url,
    echo=settings.sqlalchemy_echo,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
)

# 关闭 autocommit/autoflush，保持事务边界清晰；expire_on_commit=False 更适合接口层读取。
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """所有 ORM 模型共享的声明式基类。"""

    # 统一约束 MySQL 表引擎、字符集和排序规则，避免每张表重复声明。
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_0900_ai_ci",
    }


# 临时保留旧名字，避免现有代码中导入 `Baase` 时直接报错。
Baase = Base


def get_db():
    """为 FastAPI 依赖注入提供数据库会话，并在请求结束后自动释放。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    # 直接运行此文件时，测试数据库连接是否成功。
    try:
        with engine.connect() as connection:
            print("数据库连接成功！")
    except Exception as e:
        print(f"数据库连接失败: {e}")