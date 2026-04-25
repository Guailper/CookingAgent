# 智能做菜助手 Agent 后端开发文档

## 1. 文档目的

本文档基于以下两份文档继续向下细化，目标是把“需求”转成“具体开发动作”：

- [agent_backend_requirements.md](/d:/AppData/Code/CookingAgent/backend/agent_backend_requirements.md:1)
- [agent_backend_structure.md](/d:/AppData/Code/CookingAgent/backend/agent_backend_structure.md:1)

这份文档重点回答四个问题：

1. 当前后端开发到哪一步了
2. 后续应该按什么顺序开发
3. 每个模块具体落在哪些文件
4. 每个阶段完成后如何验收

## 2. 当前项目现状

当前仓库里的后端已经有了基础目录，但大部分仍是占位状态。

已存在的基础结构：

- [backend/src/main.py](/d:/AppData/Code/CookingAgent/backend/src/main.py:1)
- [backend/src/core/config.py](/d:/AppData/Code/CookingAgent/backend/src/core/config.py:1)
- [backend/src/core/constants.py](/d:/AppData/Code/CookingAgent/backend/src/core/constants.py:1)
- [backend/src/api/router.py](/d:/AppData/Code/CookingAgent/backend/src/api/router.py:1)
- [backend/src/api/deps.py](/d:/AppData/Code/CookingAgent/backend/src/api/deps.py:1)
- [backend/src/api/v1/endpoints/auth.py](/d:/AppData/Code/CookingAgent/backend/src/api/v1/endpoints/auth.py:1)
- [backend/src/api/v1/endpoints/conversations.py](/d:/AppData/Code/CookingAgent/backend/src/api/v1/endpoints/conversations.py:1)
- [backend/src/db/base.py](/d:/AppData/Code/CookingAgent/backend/src/db/base.py:1)

当前实际状态判断：

- 目录结构已经开始搭建
- 业务逻辑尚未真正实现
- 路由层、数据库层、服务层、Agent 层都还没有进入可运行状态
- 适合现在开始按模块逐步补齐

## 3. 开发目标

后端开发目标分成两个层次。

### 3.1 MVP 目标

第一阶段先让系统具备最小可用能力：

- 用户注册与登录
- 创建会话与发送消息
- 语音输入转写
- 上传文件和图片
- 解析 PDF / Word / PPT / 图片
- OCR 提取图片文字
- 文本问答
- 附件问答
- 基础菜谱生成
- 返回结构化菜谱结果

### 3.2 第二阶段目标

在 MVP 之后继续扩展：

- 检索增强问答
- 文档切片与向量索引
- 更强的图片理解
- 多轮上下文优化
- 异步解析任务和状态追踪
- 更完整的日志、监控与错误治理

## 4. 开发原则

开发时统一遵守这些原则：

- 接口层只处理收参、鉴权、调 service，不直接写复杂业务逻辑
- service 层负责业务流程编排
- repository 层负责 MySQL 数据访问
- parser 只负责解析，不负责业务理解
- Agent 层负责意图识别、上下文组装、工作流分发和结果构建
- 结构化结果优先，不要只返回长文本
- 所有与中文、OCR、文档全文相关的内容，数据库字段优先按 `utf8mb4 + LONGTEXT/JSON` 设计

## 5. 技术栈与基础约束

建议统一使用以下技术方案：

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- MySQL 8.0+，优先 MySQL 8.4 LTS
- Redis
- Celery 或 RQ

数据库约束：

- 存储引擎：InnoDB
- 字符集：utf8mb4
- 排序规则：utf8mb4_0900_ai_ci
- JSON 类型用于结构化解析结果和 Agent 快照

## 6. 开发阶段拆分

建议把后端开发拆成 8 个阶段。

## 阶段 0：基础可运行骨架

目标：

- 让 FastAPI 服务能够启动
- 配置系统从硬编码改为环境变量
- 建立全局异常、日志、常量、路由注册机制

需要完成的文件：

- `backend/src/main.py`
- `backend/src/core/config.py`
- `backend/src/core/constants.py`
- `backend/src/core/exceptions.py`
- `backend/src/core/logging.py`
- `backend/src/api/router.py`
- `backend/src/api/v1/router.py`

具体开发内容：

- 创建 FastAPI app
- 注册 `/api/v1`
- 建立健康检查接口
- 从 `.env` 读取 MySQL、Redis、模型、OCR 配置
- 替换掉当前 `config.py` 中的硬编码 MySQL 配置

交付物：

- 服务本地可启动
- 打开接口文档页
- 健康检查返回 200

验收标准：

- `uvicorn` 或等价命令启动成功
- `/health` 或 `/api/v1/health` 可访问
- 配置可从环境变量读取

## 阶段 1：数据库基础层

目标：

- 打通 MySQL 连接
- 建立 ORM 基类
- 建立 Session 管理
- 创建第一批核心表

需要新增的目录和文件：

- `backend/src/db/session.py`
- `backend/src/db/models/user.py`
- `backend/src/db/models/conversation.py`
- `backend/src/db/models/message.py`
- `backend/src/db/models/attachment.py`
- `backend/src/db/models/parse_result.py`
- `backend/src/db/models/agent_run.py`
- `backend/alembic/`
- `backend/alembic.ini`

具体开发内容：

- 建立 SQLAlchemy engine
- 建立 sessionmaker
- 建立 ORM Base
- 建立 Alembic 迁移
- 创建初始数据库表

交付物：

- MySQL 能连接
- Alembic 初始迁移成功
- 六张核心表创建成功

验收标准：

- 本地 MySQL 中可以看到表
- 迁移脚本可重复执行
- 表字符集、引擎、索引符合约束

## 阶段 2：认证与会话基础接口

目标：

- 实现用户注册与登录
- 实现会话创建和查询

需要新增或完善的文件：

- `backend/src/api/v1/endpoints/auth.py`
- `backend/src/api/v1/endpoints/conversations.py`
- `backend/src/schemas/auth.py`
- `backend/src/schemas/conversation.py`
- `backend/src/services/auth_service.py`
- `backend/src/services/conversation_service.py`
- `backend/src/db/repositories/user_repository.py`
- `backend/src/db/repositories/conversation_repository.py`
- `backend/src/core/security.py`

具体开发内容：

- 注册接口
- 登录接口
- 当前用户接口
- 创建会话接口
- 获取会话列表接口
- 获取单个会话详情接口

交付物：

- 前端可接入注册登录
- 用户可以创建会话

验收标准：

- 注册成功写入 MySQL
- 登录返回 token
- 会话接口必须鉴权

## 阶段 3：消息系统

目标：

- 打通会话中的消息读写
- 为后续 Agent 对话建立消息上下文基础

需要新增的文件：

- `backend/src/api/v1/endpoints/messages.py`
- `backend/src/schemas/message.py`
- `backend/src/services/message_service.py`
- `backend/src/db/repositories/message_repository.py`

具体开发内容：

- 发送消息接口
- 获取会话消息列表接口
- 保存用户消息与系统消息
- 支持消息角色字段，例如 `user`、`assistant`、`system`

交付物：

- 会话中能保存消息历史
- 后端可以按时间顺序取回上下文

验收标准：

- 同一会话下消息顺序正确
- 不同用户之间消息隔离

## 阶段 4：文件上传与存储

目标：

- 支持文件上传
- 保存附件元数据
- 为解析模块提供可访问文件

需要新增的目录和文件：

- `backend/src/api/v1/endpoints/files.py`
- `backend/src/schemas/file.py`
- `backend/src/services/file_service.py`
- `backend/src/storage/base_storage.py`
- `backend/src/storage/local_storage.py`
- `backend/src/db/repositories/file_repository.py`

具体开发内容：

- 上传单个文件
- 上传多个文件
- 校验类型和大小
- 保存到 `backend/uploads/`
- 创建附件记录

支持文件类型：

- pdf
- doc
- docx
- ppt
- pptx
- txt
- jpg
- jpeg
- png
- webp

交付物：

- 前端可以上传文件
- 后端能生成附件记录和文件路径

验收标准：

- 非法文件类型会被拒绝
- 大文件会被拦截
- 数据库和磁盘中的文件状态一致

## 阶段 5：解析与 OCR

目标：

- 让上传内容真正变成可被 Agent 使用的数据

需要新增的目录和文件：

- `backend/src/parsers/base_parser.py`
- `backend/src/parsers/pdf_parser.py`
- `backend/src/parsers/docx_parser.py`
- `backend/src/parsers/pptx_parser.py`
- `backend/src/parsers/txt_parser.py`
- `backend/src/parsers/image_parser.py`
- `backend/src/parsers/ocr_parser.py`
- `backend/src/multimodal/ocr_service.py`
- `backend/src/services/parse_service.py`

具体开发内容：

- PDF 文本提取
- Word 文本提取
- PPT 文本提取
- txt 内容读取
- 图片 OCR
- 解析结果写入 `parse_result`
- 附件状态更新为 `pending / processing / completed / failed`

交付物：

- 每个附件都能获得统一的解析结果结构

验收标准：

- 上传 PDF 后可提取文本
- 上传图片后可提取文字
- 解析失败时有标准错误状态

## 阶段 6：Agent 基础对话

目标：

- 实现统一的 Agent 对话入口
- 实现文本聊天和多轮上下文

需要新增的目录和文件：

- `backend/src/api/v1/endpoints/agent.py`
- `backend/src/schemas/agent.py`
- `backend/src/services/agent_service.py`
- `backend/src/agent/base_agent.py`
- `backend/src/agent/orchestrator.py`
- `backend/src/agent/intents.py`
- `backend/src/agent/context_builder.py`
- `backend/src/agent/response_builder.py`
- `backend/src/agent/prompts/system_prompts.py`
- `backend/src/agent/workflows/text_chat_workflow.py`

具体开发内容：

- 统一对话入口 `POST /api/agent/chat`
- 意图识别
- 上下文拼装
- 调用模型
- 保存运行记录
- 保存系统回复消息

交付物：

- 纯文本聊天可用
- 多轮上下文可用

验收标准：

- 同一会话里第二轮能带上第一轮上下文
- Agent 运行记录成功落表

## 阶段 7：文档问答、图片问答、菜谱生成

目标：

- 真正实现智能做菜助手的核心能力

需要新增的文件：

- `backend/src/agent/workflows/document_qa_workflow.py`
- `backend/src/agent/workflows/image_qa_workflow.py`
- `backend/src/agent/workflows/recipe_generation_workflow.py`
- `backend/src/agent/workflows/ingredient_analysis_workflow.py`
- `backend/src/agent/prompts/recipe_prompts.py`
- `backend/src/agent/prompts/qa_prompts.py`
- `backend/src/agent/tools/file_reader.py`
- `backend/src/agent/tools/vision_tool.py`
- `backend/src/agent/tools/recipe_formatter.py`
- `backend/src/services/recipe_service.py`
- `backend/src/schemas/recipe.py`

具体开发内容：

- 文档摘要
- 文档问答
- 图片问答
- 食材识别
- 菜谱生成
- 菜谱结构化输出

返回结果至少包括：

- 菜名
- 人数
- 耗时
- 难度
- 食材
- 调味料
- 步骤
- 注意事项

交付物：

- 系统能根据文字、文件、图片生成答案
- 菜谱输出是结构化数据

验收标准：

- 文档问答能引用上传内容
- 图片问答能结合 OCR 或图像语义
- 做菜请求返回结构化 recipe

## 阶段 8：异步任务、检索增强、稳定性提升

目标：

- 提升性能与可扩展性

需要新增的目录和文件：

- `backend/src/tasks/parse_tasks.py`
- `backend/src/tasks/embedding_tasks.py`
- `backend/src/tasks/cleanup_tasks.py`
- `backend/src/search/chunker.py`
- `backend/src/search/embeddings.py`
- `backend/src/search/vector_store.py`
- `backend/src/search/retriever.py`
- `backend/src/services/retrieval_service.py`

具体开发内容：

- 文件解析异步化
- OCR 异步化
- 文档切片
- 向量检索
- 检索增强问答
- 日志、监控、失败重试

交付物：

- 长文档处理不阻塞聊天主链路
- 文档问答可走检索增强

验收标准：

- 异步任务有状态跟踪
- 大文件解析耗时不阻塞同步接口

## 7. 模块开发清单

下面是从“开发视角”对每一层要做什么的总结。

### 7.1 API 层

负责：

- 收请求
- 返回响应
- 调用 service
- 绑定 schema

必须完成的接口：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `POST /api/v1/messages`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/files/upload`
- `GET /api/v1/files/{file_id}`
- `GET /api/v1/files/{file_id}/parse-result`
- `POST /api/v1/agent/chat`

### 7.2 Service 层

负责：

- 编排业务流程
- 调用 repository
- 调用 parser
- 调用 Agent

必须完成的 service：

- `auth_service.py`
- `conversation_service.py`
- `message_service.py`
- `file_service.py`
- `parse_service.py`
- `agent_service.py`
- `recipe_service.py`

### 7.3 Repository 层

负责：

- MySQL 查库写库
- 封装基础 CRUD

必须完成的 repository：

- `user_repository.py`
- `conversation_repository.py`
- `message_repository.py`
- `file_repository.py`
- `agent_run_repository.py`

### 7.4 Agent 层

负责：

- 任务识别
- 上下文拼装
- workflow 分发
- 输出结构化结果

必须完成的 workflow：

- `text_chat_workflow.py`
- `document_qa_workflow.py`
- `image_qa_workflow.py`
- `recipe_generation_workflow.py`

## 8. 数据库开发任务

数据库表建议按下面顺序落地。

### 第一批表

- `users`
- `conversations`
- `messages`

### 第二批表

- `attachments`
- `parse_results`
- `agent_runs`

### 第一批必须加的索引

- `users.email` 唯一索引
- `conversations.user_id, created_at`
- `messages.conversation_id, created_at`
- `attachments.message_id`
- `parse_results.file_id`
- `agent_runs.conversation_id, created_at`

### 字段类型约束

- 长消息和全文解析结果使用 `LONGTEXT`
- 结构化结果和快照使用 `JSON`
- 时间字段使用 `DATETIME(3)` 或 `TIMESTAMP(3)`

## 9. 配置开发任务

建议尽快补齐以下配置项。

必须支持的环境变量：

- `APP_ENV`
- `APP_DEBUG`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_CHARSET`
- `DATABASE_URL`
- `REDIS_URL`
- `UPLOAD_DIR`
- `MAX_UPLOAD_SIZE_MB`
- `MODEL_API_KEY`
- `MODEL_BASE_URL`
- `OCR_PROVIDER`
- `OCR_API_KEY`

建议创建文件：

- `backend/.env.example`

## 10. 测试开发任务

测试要跟开发同步推进，不要最后再补。

至少要覆盖：

- 注册登录
- 会话创建
- 消息发送
- 语音转写
- 文件上传
- PDF 解析
- OCR
- Agent 聊天
- 菜谱结构化输出

建议新增文件：

- `backend/src/tests/conftest.py`
- `backend/src/tests/test_auth.py`
- `backend/src/tests/test_conversations.py`
- `backend/src/tests/test_messages.py`
- `backend/src/tests/test_files.py`
- `backend/src/tests/test_agent_chat.py`
- `backend/src/tests/test_recipe_workflow.py`

## 11. 交付节奏建议

建议按下面节奏推进：

### 第 1 周

- 阶段 0
- 阶段 1
- 阶段 2

目标：

- 服务启动
- MySQL 接通
- 用户和会话功能跑通

### 第 2 周

- 阶段 3
- 阶段 4
- 阶段 5

目标：

- 消息流、文件上传、文件解析和 OCR 跑通

### 第 3 周

- 阶段 6
- 阶段 7

目标：

- Agent 基础对话、文档问答、图片问答、菜谱生成跑通

### 第 4 周

- 阶段 8
- 测试补齐
- 稳定性优化

目标：

- 异步任务、检索增强、日志和错误处理补齐

## 12. 阶段验收清单

每个阶段结束时，统一检查下面这些问题：

- 代码是否按目录分层放置
- 是否补齐 schema
- 是否补齐 service
- 是否补齐 repository
- 是否补齐单元测试或接口测试
- 是否补齐错误处理
- 是否更新文档

## 13. 本文档对应的下一步动作

基于当前项目状态，最建议立刻开始做的事情是：

1. 完成 `main.py`、`router.py`、`config.py` 的真实实现
2. 建立 `session.py` 和第一批数据库模型
3. 建立认证、会话、消息的 schema 和 service
4. 建立文件上传与本地存储
5. 再进入解析、OCR 和 Agent 编排

## 14. 结论

这份开发文档可以作为后端实际开发的执行指南使用。

它和需求文档的区别是：

- 需求文档回答“系统要做什么”
- 结构文档回答“代码该怎么组织”
- 开发文档回答“先做什么、后做什么、具体做到哪些文件、如何验收”

如果继续推进，下一步最合适的是再补一份：

- MySQL 数据库表结构设计文档

这样你就可以直接进入建表和写接口阶段。

## 15. 语音输入与文件上传接入设计

### 15.1 设计目标

- 在不破坏现有纯文本消息主链路的前提下，补齐“语音转文字输入”和“消息附件上传”。
- 语音能力本轮只做转写，不做语音播放、语音播报和实时流式通话。
- 文件上传能力本轮只服务于聊天消息，不单独扩展成资料库或附件中心。

### 15.2 建议调整的数据结构

- `backend/src/schemas/message.py`
  - 为创建消息请求增加 `attachment_ids`
  - 为创建消息请求增加 `extra_metadata`
- `backend/src/db/models/attachment.py`
  - 建议把 `message_id` 调整为“上传成功后可暂时为空，消息发送成功后再绑定”
  - 建议增加 `attachment_kind`，便于区分 `document | image`
- `backend/src/db/models/message.py`
  - 保持 `message_type=text` 作为默认值
  - 通过 `extra_metadata.input_source` 标记本条消息来自 `keyboard` 还是 `voice`
- `backend/src/core/constants.py`
  - 增加允许上传的文档格式、图片格式、音频格式常量
  - 增加附件数量与大小限制常量

### 15.3 建议新增或扩展的后端文件

- `backend/src/api/v1/endpoints/messages.py`
  - 扩展消息创建接口，接收 `attachment_ids` 和 `extra_metadata`
- `backend/src/api/v1/endpoints/files.py`
  - 新增附件上传与附件删除接口
- `backend/src/api/v1/endpoints/voice.py`
  - 新增语音转写接口
- `backend/src/schemas/file.py`
  - 新增附件上传请求/响应模型
- `backend/src/schemas/voice.py`
  - 新增语音转写响应模型
- `backend/src/services/message_service.py`
  - 在创建消息后绑定 `attachment_ids`
  - 保证“消息创建 + 附件绑定”在一个事务内完成
- `backend/src/services/file_service.py`
  - 负责文件校验、命名、落盘、返回附件元数据
- `backend/src/services/voice_service.py`
  - 负责音频校验、调用语音转写能力、返回文本
- `backend/src/repositories/attachment_repository.py`
  - 新增附件查询、创建、删除、绑定方法
- `backend/src/core/config.py`
  - 增加 `MAX_UPLOAD_SIZE_MB`
  - 增加 `MAX_AUDIO_SIZE_MB`
  - 增加 `MAX_AUDIO_DURATION_SECONDS`
  - 增加 `VOICE_TRANSCRIBE_PROVIDER`
  - 增加 `VOICE_TRANSCRIBE_API_KEY`

### 15.4 推荐接口设计

#### 15.4.1 语音转写接口

```text
POST /api/v1/voice/transcriptions
Content-Type: multipart/form-data

fields:
- file
- language
```

作用：

- 校验音频格式、大小、时长
- 调用语音转写服务
- 返回转写文本，不直接创建消息

#### 15.4.2 附件上传接口

```text
POST /api/v1/conversations/{conversation_id}/attachments
Content-Type: multipart/form-data

fields:
- files[]
```

作用：

- 校验文档/图片格式与大小
- 生成附件记录
- 保存到本地存储或对象存储
- 返回 `attachment_ids`

#### 15.4.3 消息发送接口

```json
{
  "content": "请根据这些文件帮我总结重点",
  "message_type": "text",
  "attachment_ids": ["att_001", "att_002"],
  "extra_metadata": {
    "input_source": "voice"
  }
}
```

作用：

- 保持现有文本消息链路不变
- 仅扩展“绑定附件”和“标记输入来源”能力

### 15.5 推荐服务编排流程

#### 15.5.1 语音输入流程

1. 前端把录音文件发送到 `POST /api/v1/voice/transcriptions`
2. `voice_service.py` 校验文件并调用转写能力
3. 后端返回 `transcript`
4. 前端把文本写入输入框
5. 用户确认后再走现有消息发送接口

#### 15.5.2 文件上传并发送消息流程

1. 前端本地暂存待发送附件
2. 用户点击发送时，如果没有会话则先创建会话
3. 前端调用附件上传接口，拿到 `attachment_ids`
4. 前端调用消息接口，传入正文和 `attachment_ids`
5. `message_service.py` 创建消息后绑定附件
6. 后续解析、OCR、Agent 工作流继续复用已有附件与解析链路

### 15.6 事务与错误处理要求

- 附件上传成功但消息发送失败时，前端应收到可重试的错误信息。
- 消息创建成功但附件绑定失败时，后端必须回滚事务，避免出现“消息成功、附件丢失”的半完成状态。
- 删除附件接口只允许删除“尚未绑定正式消息”的附件。
- 语音转写失败时不写消息表、不写附件表，直接返回标准错误响应。

### 15.7 建议补充的测试

- `backend/src/tests/test_files.py`
  - 上传合法文档
  - 上传非法扩展名
  - 删除未绑定附件
- `backend/src/tests/test_messages.py`
  - 创建带 `attachment_ids` 的消息
  - 附件归属校验
- `backend/src/tests/test_voice.py`
  - 上传合法音频并返回转写文本
  - 上传非法音频格式
  - 上传超出大小限制的音频

### 15.8 推荐开发顺序

1. 先补 `schemas/message.py`、`db/models/attachment.py`、`core/constants.py`、`core/config.py`
2. 再补 `files.py`、`file_service.py`、`attachment_repository.py`
3. 再补 `messages.py` 和 `message_service.py` 的附件绑定逻辑
4. 再补 `voice.py` 和 `voice_service.py`
5. 最后补接口测试和异常路径测试

### 15.9 本轮不实现的内容

- 助手语音播报
- 音频消息播放器
- 实时流式语音通话
- 附件跨消息复用
