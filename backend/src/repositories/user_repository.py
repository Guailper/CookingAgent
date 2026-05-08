"""用户数据访问层。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.user import User


class UserRepository:
    """封装 users 表的常用查询与写入操作。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        """根据数据库主键查询用户。"""

        return self.db.get(User, user_id)

    def get_by_public_id(self, public_id: str) -> User | None:
        """根据对外业务 ID 查询用户。"""

        stmt = select(User).where(User.public_id == public_id)
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> User | None:
        """根据邮箱查询用户。"""

        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def create(self, user: User) -> User:
        """把新用户加入当前事务。"""

        self.db.add(user)
        self.db.flush()
        return user
