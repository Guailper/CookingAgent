"""消息数据访问层。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.message import Message


class MessageRepository:
    """封装 messages 表的常用查询与写入操作。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, message: Message) -> Message:
        """把新消息加入当前事务。"""

        self.db.add(message)
        self.db.flush()
        return message

    def list_by_conversation_id(self, conversation_id: int) -> list[Message]:
        """按创建时间升序返回指定会话的消息列表。"""

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
