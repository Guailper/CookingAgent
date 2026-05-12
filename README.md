# CookingAgent

> 一个面向做菜场景的中文 AI Agent 全栈应用：把菜谱知识库、实时工具、多轮会话、附件和语音输入整合到同一个聊天工作台里。项目中使用的数据来源于 [HowToCook](https://github.com/Anduin2017/HowToCook))

![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?style=flat-square)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1c3c3c?style=flat-square)
![Milvus](https://img.shields.io/badge/Milvus-RAG-00a1ea?style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-8+-4479a1?style=flat-square)

## 功能概览

- **菜谱问答**：回答食材处理、步骤规划、火候控制、替换方案和菜单搭配。
- **RAG 知识库**：内置 `data/cook/dishes` 菜谱 Markdown 数据，切片后写入 Milvus 检索。
- **联网补充**：知识库未命中时可用 SerpApi 自动补充网页搜索上下文，并要求回答引用来源。
- **天气工具**：通过 QWeather 查询当前或未来 7 天内天气，用于时令菜、采购和用餐建议。
- **模型降级链**：支持 Kimi、Xiaomi、AIHubMix、OpenAI-compatible、本地 OpenAI-compatible 服务等候选模型 fallback。
- **多轮聊天工作台**：支持会话、历史消息、附件上传、语音转写、工作区搜索和设置面板。
- **业务持久化**：用户、验证码、会话、消息、附件、解析结果、记忆项、AgentRun 运行快照均落库。
- **缓存与限流**：Redis 可选，用于登录、验证码、Agent 请求限流和短期缓存。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React, TypeScript, Vite, React Markdown |
| 后端 | FastAPI, SQLAlchemy, Alembic, PyMySQL, Pydantic |
| Agent | LangChain, Tool Calling |
| RAG | Milvus, pymilvus, sentence-transformers, FlagEmbedding |
| 工具 | WebSearch, WeatherSearch, Voice2Text |
| 存储 | MySQL, Redis 可选, 本地文件系统 |

## 项目结构

```text
CookingAgent
├─ frontend/                 # React 前端工作台
│  ├─ src/components/        # 登录、聊天、设置组件
│  ├─ src/hooks/             # 认证与聊天状态编排
│  └─ src/services/          # API 请求封装
├─ backend/
│  ├─ main.py                # FastAPI 应用入口
│  ├─ agent/                 # Agent 编排、工作流、工具、提示词
│  │  ├─ tools/              # RAG、附件、天气、网页搜索、菜谱格式化工具
│  │  ├─ workflows/          # 问答、附件解析、文档入库、记忆更新
│  │  └─ web/                # RAG miss 后的网页搜索上下文构建
│  ├─ src/api/               # API 路由
│  ├─ src/services/          # 业务服务
│  ├─ src/repositories/      # 数据访问
│  ├─ src/rag/               # 切片、Embedding、Rerank、Milvus 检索
│  └─ scripts/               # 数据入库脚本
├─ data/                     # 本地菜谱 Markdown 数据，当前约 322 篇
├─ models/                   # 本地 embedding / rerank / whisper 模型
└─ README.md
```

## 工作流

```text
用户输入 / 附件 / 语音
  -> 前端调用 /api/v1/agent/chat
  -> 保存用户消息与 AgentRun
  -> 解析意图并选择工作流
  -> 默认检索 Milvus 菜谱知识库
  -> 未命中时可补充 SerpApi 网页搜索
  -> LangChain Agent 调用模型和工具
  -> 失败时尝试候选模型，全部失败后返回本地降级回复
  -> 保存助手消息和运行快照
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8+
- Milvus 2.4+
- Redis 可选

### 2. 配置 `.env`

在项目根目录创建 `.env`，按需填写：

```env
# App
APP_SECRET_KEY=change-this-in-dev
AUTO_CREATE_TABLES=true

# MySQL
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=cooking_agent_db
MYSQL_USER=root
MYSQL_PASSWORD=

# Agent model
AGENT_MODEL_PROVIDER=kimi
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_API_KEY=your-kimi-api-key
KIMI_MODEL_ID=kimi-k2.6
AGENT_MODEL_FALLBACK_ORDER=kimi,xiaomi,aihubmix,local

# Optional fallback providers
XIAOMI_BASE_URL=
XIAOMI_API_KEY=
XIAOMI_MODEL_ID=
AIHUBMIX_BASE_URL=
AIHUBMIX_API_KEY=
AIHUBMIX_MODEL_ID=gpt-4o-mini
LOCAL_MODEL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_MODEL_API_KEY=not-needed
LOCAL_MODEL_ID=

# RAG
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=rag_chunks
RAG_DEFAULT_KNOWLEDGE_BASE_IDS=cookbook
RAG_EMBEDDING_MODEL_PATH=models/bge-small-zh-v1.5
RAG_RERANK_MODEL_PATH=models/bge-reranker-v2-m3

# Tools
SERPAPI_API_KEY=
WEATHER_API_KEY=

# Voice
VOICE_TRANSCRIBE_PROVIDER=local_faster_whisper
VOICE_LOCAL_MODEL=small

# Redis
REDIS_ENABLED=false
REDIS_URL=redis://127.0.0.1:6379/0
```

前端开发代理默认指向 `http://127.0.0.1:8000`，可通过 `VITE_BACKEND_URL` 覆盖。

### 3. 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

- 健康检查：`http://127.0.0.1:8000/health`
- API 文档：`http://127.0.0.1:8000/docs`

### 4. 写入菜谱知识库

```bash
cd backend
python scripts/index_data_to_milvus.py --data-dir data --knowledge-base-id cookbook --rebuild
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## API 一览

| 能力 | 路由 |
| --- | --- |
| 认证与用户 | `/api/v1/auth/*` |
| 会话 | `/api/v1/conversations` |
| 消息 | `/api/v1/conversations/{id}/messages` |
| Agent 对话 | `/api/v1/agent/chat` |
| 附件 | `/api/v1/conversations/{id}/attachments`, `/api/v1/attachments/{id}` |
| 语音转写 | `/api/v1/voice/transcriptions` |

## 测试与构建

```bash
# 后端测试
cd backend
python -m unittest discover src/tests

# 前端构建
cd frontend
npm run build
```

## 开发备注

- `AUTO_CREATE_TABLES=true` 适合本地开发；生产环境建议使用迁移流程。
- `SERPAPI_API_KEY` 和 `WEATHER_API_KEY` 为空时，对应工具会优雅降级。
- 模型候选顺序由 `AGENT_MODEL_FALLBACK_ORDER` 控制，未配置时会按可用环境变量自动推断。
- `.env` 内的 API Key、数据库密码、SMTP 密码不要提交。

## License

[Apache-2.0](LICENSE)
