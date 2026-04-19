"""API 总路由注册入口。

这里负责汇总所有接口模块，并统一挂到版本前缀下面。
后续无论新增认证、会话、上传还是 Agent 相关接口，都从这里接入。
"""

from fastapi import APIRouter

from src.api.v1.endpoints import auth, conversations, messages

api_router = APIRouter()

# 认证相关接口。
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])

# 会话相关接口。
api_router.include_router(conversations.router, prefix="/conversations", tags=["会话"])

# 消息相关接口。
api_router.include_router(messages.router, prefix="/conversations", tags=["消息"])
