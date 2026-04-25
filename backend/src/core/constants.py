"""Project-wide constants shared by API, services, and persistence layers."""

# Application metadata.
APP_NAME = "智能做菜助手 Agent"
APP_VERSION = "0.1.0"
API_V1_PREFIX = "/api/v1"
TOKEN_TYPE_BEARER = "bearer"

# User states.
USER_STATUS_ACTIVE = "active"

# Conversation defaults.
DEFAULT_CONVERSATION_TITLE = "新的对话"
CONVERSATION_STATUS_ACTIVE = "active"

# Message roles, types, and metadata conventions.
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_SYSTEM = "system"
MESSAGE_ROLE_TOOL = "tool"
MESSAGE_STATUS_COMPLETED = "completed"
# Voice input is converted into plain text, so user messages stay text-only for now.
MESSAGE_TYPE_TEXT = "text"
INPUT_SOURCE_KEYBOARD = "keyboard"
INPUT_SOURCE_VOICE = "voice"

# Attachment and parsing states.
ATTACHMENT_STORAGE_LOCAL = "local"
ATTACHMENT_KIND_DOCUMENT = "document"
ATTACHMENT_KIND_IMAGE = "image"
PARSE_STATUS_PENDING = "pending"
PARSE_STATUS_COMPLETED = "completed"
PARSE_STATUS_FAILED = "failed"
EMBEDDING_STATUS_PENDING = "pending"

# Agent lifecycle states.
AGENT_RUN_STATUS_PENDING = "pending"
AGENT_RUN_STATUS_RUNNING = "running"
AGENT_RUN_STATUS_COMPLETED = "completed"
AGENT_RUN_STATUS_FAILED = "failed"

# Authentication defaults.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Upload and transcription limits.
DEFAULT_MAX_ATTACHMENT_FILES = 5
DEFAULT_MAX_UPLOAD_SIZE_MB = 10
DEFAULT_MAX_AUDIO_SIZE_MB = 10
DEFAULT_MAX_AUDIO_DURATION_SECONDS = 120
DEFAULT_VOICE_REQUEST_TIMEOUT_SECONDS = 60

ALLOWED_DOCUMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".txt",
)

ALLOWED_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
)

ALLOWED_AUDIO_EXTENSIONS = (
    ".webm",
    ".wav",
    ".mp3",
    ".m4a",
)
