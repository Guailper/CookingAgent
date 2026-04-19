"""ORM 模型统一导入入口。

这个文件的主要作用是集中导入所有模型，让 SQLAlchemy 可以完整注册 metadata，
同时也方便其他模块从一个入口拿到所有模型类。
"""

from src.db.models.agent_run import AgentRun
from src.db.models.attachment import Attachment
from src.db.models.conversation import Conversation
from src.db.models.message import Message
from src.db.models.parse_result import ParseResult
from src.db.models.user import User

__all__ = [
    "AgentRun",
    "Attachment",
    "Conversation",
    "Message",
    "ParseResult",
    "User",
]


def import_all_models() -> None:
    """保留一个显式调用入口，表达“导入模型以注册 metadata”的意图。"""

    _ = (User, Conversation, Message, Attachment, ParseResult, AgentRun)
