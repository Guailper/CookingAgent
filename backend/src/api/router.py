"""Top-level API router registration."""

from fastapi import APIRouter

from src.api.v1.endpoints import agent, auth, conversations, files, messages, voice

api_router = APIRouter()

api_router.include_router(agent.router, tags=["智能体"])
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["会话"])
api_router.include_router(messages.router, prefix="/conversations", tags=["消息"])
api_router.include_router(files.router, tags=["附件"])
api_router.include_router(voice.router, tags=["语音"])
