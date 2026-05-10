# CookingAgent

> 面向菜谱问答场景的 AI Agent 全栈应用，支持 RAG 知识库、多轮会话、附件解析、语音输入与用户认证。

![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?style=flat-square)
![Milvus](https://img.shields.io/badge/Milvus-RAG-00a1ea?style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-8+-4479a1?style=flat-square)

## 项目亮点

- **菜谱智能问答**：围绕食材搭配、烹饪步骤、技巧建议和菜单规划提供对话式回答。
- **RAG 知识增强**：使用本地 Markdown 菜谱数据切片、向量化并写入 Milvus，回答时自动检索相关上下文。
- **Agent 工作流**：按意图分发到问答、附件解析、文档入库、记忆更新等流程，保留可扩展边界。
- **完整聊天工作台**：支持会话列表、消息历史、乐观消息、附件上传、语音转写和工作区搜索。
- **业务数据持久化**：用户、会话、消息、附件、解析结果、记忆项与 Agent 运行记录均落库保存。
- **可选缓存与限流**：Redis 可用于验证码、登录、Agent 请求限流和短期缓存。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | React 18, TypeScript, Vite, React Markdown |
| 后端 | FastAPI, SQLAlchemy 2.x, Alembic, PyMySQL, Pydantic 2.x |
| Agent | LangChain, OpenAI-compatible Chat Model Adapter |
| RAG | Milvus, pymilvus, sentence-transformers, FlagEmbedding |
| 语音 | faster-whisper 或 OpenAI-compatible Whisper API |
| 数据 | MySQL, Redis 可选, 本地上传目录 |

## 目录结构

```text
CookingAgent
├─ frontend/                 # React 聊天工作台
│  ├─ src/components/        # 登录、聊天、设置等 UI 组件
│  ├─ src/hooks/             # 工作台与认证状态编排
│  └─ src/services/          # 前端 API 封装
├─ backend/
│  ├─ main.py                # FastAPI 应用入口
│  ├─ agent/                 # Agent 编排、工作流、工具与提示词
│  ├─ src/api/               # HTTP 路由
│  ├─ src/services/          # 业务服务层
│  ├─ src/repositories/      # 数据访问层
│  ├─ src/rag/               # 切片、Embedding、Rerank、Milvus 检索
│  └─ scripts/               # RAG 数据入库脚本
├─ data/                     # 本地菜谱 Markdown 数据
├─ models/                   # 本地 embedding / rerank / whisper 模型目录
└─ PROJECT_SUMMARY.md        # 项目实现说明
```

## 核心链路

```text
用户输入问题 / 上传附件 / 录音
  -> 前端创建或选择会话
  -> 调用 /api/v1/agent/chat
  -> 后端保存用户消息与 AgentRun
  -> AgentOrchestrator 解析意图
  -> AnswerWorkflow 构建 RAG 上下文
  -> LangChain 调用模型与工具
  -> 保存助手回复
  -> 前端刷新真实消息
```

## 快速启动

### 1. 准备环境

- Python 3.10+
- Node.js 18+
- MySQL 8+
- Milvus 2.4+
- Redis 可选

### 2. 配置环境变量

在项目根目录创建 `.env`，按需填写：

```env
APP_SECRET_KEY=change-this-in-dev
AUTO_CREATE_TABLES=true

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=cooking_agent_db
MYSQL_USER=root
MYSQL_PASSWORD=

AGENT_MODEL_PROVIDER=kimi
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_API_KEY=your-api-key
KIMI_MODEL_ID=kimi-k2.6

MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=rag_chunks
RAG_DEFAULT_KNOWLEDGE_BASE_IDS=cookbook
RAG_EMBEDDING_MODEL_PATH=models/bge-small-zh-v1.5
RAG_RERANK_MODEL_PATH=models/bge-reranker-v2-m3

VOICE_TRANSCRIBE_PROVIDER=local_faster_whisper
VOICE_LOCAL_MODEL=small

REDIS_ENABLED=false
REDIS_URL=redis://127.0.0.1:6379/0
```

前端默认把 `/api` 代理到 `http://127.0.0.1:8000`。如需修改：

```env
VITE_BACKEND_URL=http://127.0.0.1:8000
```

### 3. 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

后端地址：

- 健康检查：`http://127.0.0.1:8000/health`
- API 文档：`http://127.0.0.1:8000/docs`

### 4. 写入 RAG 菜谱数据

确保 Milvus 与本地 embedding / rerank 模型可用后执行：

```bash
cd backend
python scripts/index_data_to_milvus.py --data-dir data --knowledge-base-id cookbook --rebuild
```

脚本会扫描 `data/**/*.md`，切片后写入配置的 Milvus collection。

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 Vite 输出的本地地址即可使用。

## 主要接口

| 能力 | 路由 |
| --- | --- |
| 注册 / 登录 / 当前用户 | `/api/v1/auth/*` |
| 会话管理 | `/api/v1/conversations` |
| 会话消息 | `/api/v1/conversations/{id}/messages` |
| Agent 对话 | `/api/v1/agent/chat` |
| 附件上传与清理 | `/api/v1/conversations/{id}/attachments`, `/api/v1/attachments/{id}` |
| 语音转写 | `/api/v1/voice/transcriptions` |

## 测试与构建

```bash
# 后端单元测试
cd backend
python -m unittest discover src/tests

# 前端类型检查与构建
cd frontend
npm run build
```

## 开发提示

- 开发环境可用 `AUTO_CREATE_TABLES=true` 自动建表；生产环境建议使用迁移流程。
- `.env` 中的 API Key、数据库密码、SMTP 密码不要提交到仓库。
- 如果未配置主模型，Agent 会进入降级路径，但 RAG、附件、语音等能力仍需要各自依赖可用。
- 本地语音转写依赖 `faster-whisper`，也可以切换到 OpenAI-compatible Whisper API。

## License

本项目基于 [Apache-2.0](LICENSE) 许可证发布。
