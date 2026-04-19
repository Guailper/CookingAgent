"""项目公共常量。

这些值主要用于统一默认配置、状态值和基础业务约定，
避免在不同文件里出现重复的硬编码字符串。
"""

# 应用元信息。
APP_NAME = "智能做菜助手 Agent"
APP_VERSION = "0.1.0"
API_V1_PREFIX = "/api/v1"
TOKEN_TYPE_BEARER = "bearer"

# 用户相关常量。
USER_STATUS_ACTIVE = "active"

# 会话相关常量。
DEFAULT_CONVERSATION_TITLE = "新对话"
CONVERSATION_STATUS_ACTIVE = "active"

# 消息相关常量。
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_SYSTEM = "system"
MESSAGE_ROLE_TOOL = "tool"
MESSAGE_STATUS_COMPLETED = "completed"
MESSAGE_TYPE_TEXT = "text"

# 附件与解析状态。
ATTACHMENT_STORAGE_LOCAL = "local"
PARSE_STATUS_PENDING = "pending"
PARSE_STATUS_COMPLETED = "completed"
EMBEDDING_STATUS_PENDING = "pending"

# Agent 运行状态。
AGENT_RUN_STATUS_PENDING = "pending"
AGENT_RUN_STATUS_RUNNING = "running"
AGENT_RUN_STATUS_COMPLETED = "completed"
AGENT_RUN_STATUS_FAILED = "failed"

# 令牌相关常量。
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
