"""会话数据访问层。"""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.db.models.conversation import Conversation


class ConversationRepository:
    """封装 conversations 表的常用查询与写入操作。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, conversation: Conversation) -> Conversation:
        """把新会话加入当前事务。"""

        self.db.add(conversation)
        self.db.flush()
        return conversation

    def list_by_user_id(self, user_id: int) -> list[Conversation]:
        """查询某个用户的会话列表。"""

        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(
                desc(Conversation.latest_message_at),
                desc(Conversation.created_at),
            )
        )
        return list(self.db.scalars(stmt).all())

    def get_by_public_id_and_user_id(self, public_id: str, user_id: int) -> Conversation | None:
        """查询某个用户下的指定会话。"""

        stmt = select(Conversation).where(
            Conversation.public_id == public_id,
            Conversation.user_id == user_id,
        )
        return self.db.scalar(stmt)
