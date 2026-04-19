# 智能做菜助手 Agent 后端项目结构说明

## 1. 说明

这份文档是在 [agent_backend_requirements.md](/d:/AppData/Code/CookingAgent/backend/agent_backend_requirements.md:1) 的基础上，进一步给出一套可以直接落地的后端项目结构。

这里我做一个明确假设：

- 后端语言：Python
- Web 框架：FastAPI
- 数据校验：Pydantic
- 数据库：MySQL 8.0+，建议直接使用 MySQL 8.4 LTS
- 数据库 ORM：SQLAlchemy
- MySQL 驱动：`PyMySQL` 或 `asyncmy`
- 数据迁移：Alembic
- 异步任务：Celery 或 RQ
- 文件存储：本地存储或对象存储

如果你后面决定不用 FastAPI，这套结构仍然能复用大部分分层思想。

## 2. 推荐的后端目录结构

```text
backend/
├─ src/
│  ├─ main.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ logging.py
│  │  ├─ security.py
│  │  ├─ exceptions.py
│  │  └─ constants.py
│  ├─ api/
│  │  ├─ router.py
│  │  ├─ deps.py
│  │  └─ v1/
│  │     ├─ router.py
│  │     └─ endpoints/
│  │        ├─ auth.py
│  │        ├─ conversations.py
│  │        ├─ messages.py
│  │        ├─ files.py
│  │        └─ agent.py
│  ├─ schemas/
│  │  ├─ common.py
│  │  ├─ auth.py
│  │  ├─ conversation.py
│  │  ├─ message.py
│  │  ├─ file.py
│  │  ├─ agent.py
│  │  └─ recipe.py
│  ├─ db/
│  │  ├─ base.py
│  │  ├─ session.py
│  │  ├─ models/
│  │  │  ├─ user.py
│  │  │  ├─ conversation.py
│  │  │  ├─ message.py
│  │  │  ├─ attachment.py
│  │  │  ├─ parse_result.py
│  │  │  └─ agent_run.py
│  │  └─ repositories/
│  │     ├─ user_repository.py
│  │     ├─ conversation_repository.py
│  │     ├─ message_repository.py
│  │     ├─ file_repository.py
│  │     └─ agent_run_repository.py
│  ├─ services/
│  │  ├─ auth_service.py
│  │  ├─ conversation_service.py
│  │  ├─ message_service.py
│  │  ├─ file_service.py
│  │  ├─ parse_service.py
│  │  ├─ retrieval_service.py
│  │  ├─ recipe_service.py
│  │  └─ agent_service.py
│  ├─ agent/
│  │  ├─ base_agent.py
│  │  ├─ orchestrator.py
│  │  ├─ intents.py
│  │  ├─ context_builder.py
│  │  ├─ response_builder.py
│  │  ├─ prompts/
│  │  │  ├─ system_prompts.py
│  │  │  ├─ recipe_prompts.py
│  │  │  └─ qa_prompts.py
│  │  ├─ tools/
│  │  │  ├─ file_reader.py
│  │  │  ├─ retriever.py
│  │  │  ├─ vision_tool.py
│  │  │  └─ recipe_formatter.py
│  │  └─ workflows/
│  │     ├─ text_chat_workflow.py
│  │     ├─ document_qa_workflow.py
│  │     ├─ image_qa_workflow.py
│  │     ├─ recipe_generation_workflow.py
│  │     └─ ingredient_analysis_workflow.py
│  ├─ parsers/
│  │  ├─ base_parser.py
│  │  ├─ pdf_parser.py
│  │  ├─ docx_parser.py
│  │  ├─ pptx_parser.py
│  │  ├─ txt_parser.py
│  │  ├─ image_parser.py
│  │  └─ ocr_parser.py
│  ├─ multimodal/
│  │  ├─ image_understanding.py
│  │  ├─ ocr_service.py
│  │  └─ ingredient_detector.py
│  ├─ search/
│  │  ├─ chunker.py
│  │  ├─ embeddings.py
│  │  ├─ vector_store.py
│  │  └─ retriever.py
│  ├─ tasks/
│  │  ├─ parse_tasks.py
│  │  ├─ embedding_tasks.py
│  │  └─ cleanup_tasks.py
│  ├─ storage/
│  │  ├─ base_storage.py
│  │  ├─ local_storage.py
│  │  └─ object_storage.py
│  ├─ utils/
│  │  ├─ time.py
│  │  ├─ ids.py
│  │  ├─ file_types.py
│  │  └─ text.py
│  └─ tests/
│     ├─ conftest.py
│     ├─ test_auth.py
│     ├─ test_files.py
│     ├─ test_agent_chat.py
│     └─ test_recipe_workflow.py
├─ alembic/
├─ uploads/
├─ scripts/
├─ .env.example
├─ requirements.txt
├─ alembic.ini
└─ README.md
```

## 3. 顶层目录说明

### `backend/src/`

这是后端业务代码主目录，所有真正运行的应用代码都建议放在这里。

你可以理解为：

- `src` 里面是“应用程序本体”
- `backend` 根目录更多放配置、脚本、迁移、说明文档和运行资源

### `backend/alembic/`

这个目录专门放数据库迁移脚本。

适合存放：

- 表结构变更脚本
- 字段新增、删除、修改脚本
- 数据初始化迁移脚本

不要把业务逻辑写在这里。

### `backend/uploads/`

这个目录用于本地开发环境下存储用户上传的文件。

适合存放：

- PDF
- Word
- PPT
- 图片
- 临时解析中间文件

注意：

- 生产环境最好不要直接把用户文件长期放本地磁盘
- 生产环境更适合接对象存储
- 这个目录通常不提交真实数据到 Git

### `backend/scripts/`

这个目录放运维和开发辅助脚本。

适合存放：

- 初始化脚本
- 数据导入脚本
- 清理临时文件脚本
- 本地启动辅助脚本

### `backend/.env.example`

这个文件用于给团队说明环境变量模板。

适合放：

- MySQL 连接串示例
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_CHARSET`
- Redis 地址示例
- 大模型 API Key 占位
- OCR 服务配置示例

### `backend/requirements.txt`

放 Python 依赖。

如果后面你想更规范，也可以改成：

- `pyproject.toml`
- `poetry.lock`

但作为 MVP，`requirements.txt` 已经足够。

## 4. `src` 内部分层说明

## `src/main.py`

这是后端应用入口文件。

职责：

- 创建 FastAPI 实例
- 注册总路由
- 初始化中间件
- 初始化异常处理
- 注册启动与关闭事件

一句话理解：

这是整个后端服务的启动点。

## `src/core/`

这个目录放“全局基础能力”，所有模块都会依赖它。

### `config.py`

放配置读取逻辑。

适合管理：

- 数据库配置
- MySQL 主机、端口、库名、用户、密码、字符集
- Redis 配置
- 文件上传大小限制
- 模型服务地址
- OCR 服务地址
- 对象存储配置

### `logging.py`

放日志初始化逻辑。

适合管理：

- 控制台日志格式
- 文件日志格式
- request id
- 错误日志统一输出

### `security.py`

放认证和安全相关基础能力。

适合放：

- JWT 生成与校验
- 密码哈希
- 权限校验辅助函数

### `exceptions.py`

放全局异常定义。

适合放：

- 业务异常基类
- 文件解析异常
- 认证异常
- 参数异常
- Agent 执行异常

### `constants.py`

放常量定义。

适合放：

- 支持的文件类型
- 任务状态枚举
- 意图类型常量
- 默认分页参数

## `src/api/`

这个目录专门放接口层代码。

它只负责：

- 接收请求
- 做基础校验
- 调用 service
- 返回响应

它不应该承载复杂业务逻辑。

### `router.py`

总路由注册文件。

作用：

- 汇总所有版本路由
- 统一挂载到应用

### `deps.py`

放 API 依赖项。

适合放：

- 获取数据库 Session
- 获取当前登录用户
- 权限依赖

### `v1/`

放第一版 API。

这样做的好处是以后可以平滑升级成：

- `/api/v1/...`
- `/api/v2/...`

### `v1/endpoints/`

这里按业务领域拆接口文件。

#### `auth.py`

存放用户认证接口：

- 注册
- 登录
- 当前用户信息

#### `conversations.py`

存放会话接口：

- 创建会话
- 获取会话列表
- 获取单个会话详情

#### `messages.py`

存放消息接口：

- 发送消息
- 获取会话消息列表

#### `files.py`

存放文件相关接口：

- 上传文件
- 获取文件元信息
- 获取解析结果

#### `agent.py`

存放 Agent 统一入口：

- 聊天
- 流式响应
- 触发工作流

## `src/schemas/`

这个目录放请求和响应的数据结构定义。

它的职责是：

- 定义 API 输入格式
- 定义 API 输出格式
- 保持前后端字段统一

### 适合拆分方式

#### `common.py`

放公共返回结构：

- 分页
- 通用错误
- 通用成功响应

#### `auth.py`

放认证请求与响应结构。

#### `conversation.py`

放会话相关 schema。

#### `message.py`

放消息相关 schema。

#### `file.py`

放文件上传和解析相关 schema。

#### `agent.py`

放 Agent 请求和响应 schema。

#### `recipe.py`

放结构化菜谱结果 schema。

这个文件很重要，因为你这个项目最终要输出结构化做菜流程。

## `src/db/`

这个目录专门放数据库层内容。

### `base.py`

放 ORM 基类。

### `session.py`

放 MySQL 连接和 Session 管理。

### `models/`

这个目录放数据库表模型。

建议一个实体一个文件。

#### `user.py`

存放用户表模型。

#### `conversation.py`

存放会话表模型。

#### `message.py`

存放消息表模型。

#### `attachment.py`

存放上传文件元数据表模型。

#### `parse_result.py`

存放解析结果表模型。

#### `agent_run.py`

存放 Agent 运行记录表模型。

### `repositories/`

这个目录放数据库访问逻辑。

职责：

- 查库
- 写库
- 更新状态
- 封装基础 CRUD

这样 service 层就不需要直接写 SQL。

## 4.1 MySQL 落地建议

既然数据库已经确定为 MySQL，建议在项目一开始就把下面这些约束定死，这样后面不会因为字符集、字段类型或检索方案反复返工。

### 1. MySQL 版本

- 建议使用 MySQL 8.0+
- 如果是新项目，优先 MySQL 8.4 LTS

原因：

- 原生支持 `JSON` 类型
- 更适合保存结构化解析结果、Agent 运行快照和配置字段

根据 MySQL 官方文档，MySQL 支持原生 `JSON` 数据类型，并会对写入的 JSON 做校验；同时 `utf8mb4` 是推荐的 Unicode 字符集，`InnoDB` 是事务型默认存储引擎。这里我据此做了下面这些工程建议。

### 2. 存储引擎

- 所有核心业务表统一使用 `InnoDB`

适用表：

- `user`
- `conversation`
- `message`
- `attachment`
- `parse_result`
- `agent_run`

原因：

- 支持事务
- 支持行级锁
- 更适合并发聊天、文件上传和状态更新

### 3. 字符集与排序规则

- 字符集统一使用 `utf8mb4`
- 排序规则优先 `utf8mb4_0900_ai_ci`
- 如果环境不支持，再退回 `utf8mb4_unicode_ci`

原因：

- 项目里会长期处理中文、英文、标点、表情和 OCR 文本
- `utf8mb4` 能避免 `utf8mb3` 带来的字符截断问题

### 4. 建议字段类型

对这类 Agent 项目，MySQL 字段建议如下：

- 主键：内部主键优先 `BIGINT UNSIGNED`
- 外部展示 ID：可额外保留 `VARCHAR(64)` 形式的业务 ID，例如 `conv_xxx`
- 普通短文本：`VARCHAR`
- 长文本消息：`TEXT` 或 `LONGTEXT`
- 文档全文、OCR 结果：`LONGTEXT`
- 结构化结果：`JSON`
- 时间字段：`DATETIME(3)` 或 `TIMESTAMP(3)`
- 状态字段：`VARCHAR(32)` 或枚举型字符串

推荐使用 `JSON` 的字段包括：

- `parse_result.structured_result`
- `parse_result.ocr_result`
- `agent_run.input_snapshot`
- `agent_run.output_snapshot`

推荐使用 `LONGTEXT` 的字段包括：

- `message.content`
- `parse_result.raw_text`

### 5. 索引建议

MySQL 表建议尽早建好以下索引：

- `user.email` 唯一索引
- `conversation.user_id + created_at`
- `message.conversation_id + created_at`
- `attachment.message_id`
- `attachment.conversation_id`
- `parse_result.file_id`
- `agent_run.conversation_id + created_at`
- `agent_run.message_id`

这样能支撑最常见的查询：

- 查询某个用户的会话列表
- 查询某个会话的消息流
- 查询某条消息关联的文件
- 查询某个附件的解析结果
- 查询某次 Agent 执行记录

### 6. MySQL 与向量检索的边界

这个项目后面如果做语义检索，我建议把职责分开：

- MySQL：存业务主数据
- 向量库或独立检索组件：存 embedding 和向量索引

也就是说：

- `user`、`conversation`、`message`、`attachment`、`agent_run` 放 MySQL
- 文档切片和向量索引不要优先硬塞进 MySQL

MVP 阶段如果暂时不做向量检索，MySQL 完全够用。

如果后期要做检索增强，再单独接：

- 本地向量库
- 专门的向量数据库
- 搜索引擎服务

### 7. 事务边界建议

MySQL 事务建议只包住“强一致业务步骤”，例如：

- 创建消息 + 创建 Agent 运行记录
- 上传文件元数据 + 附件关系记录
- 解析完成后更新附件状态 + 写入解析结果

不要把“大模型调用”或“长时间 OCR”放在数据库事务里等待完成。

### 8. 配置建议

如果数据库明确使用 MySQL，建议在配置中显式出现这些字段：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=cooking_agent
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_CHARSET=utf8mb4
DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/cooking_agent?charset=utf8mb4
```

如果后端走 SQLAlchemy Async，也可以使用：

```env
DATABASE_URL=mysql+asyncmy://root:your_password@127.0.0.1:3306/cooking_agent?charset=utf8mb4
```

## `src/services/`

这个目录放业务服务层，是后端的核心业务组织层。

原则：

- 一个服务负责一个业务域
- service 里写“业务逻辑”
- service 可以调用 repository、parser、agent、storage

### `auth_service.py`

负责：

- 注册
- 登录
- token 生成
- 用户校验

### `conversation_service.py`

负责：

- 创建会话
- 会话列表
- 会话标题管理
- 会话状态管理

### `message_service.py`

负责：

- 保存消息
- 获取历史消息
- 组装上下文消息

### `file_service.py`

负责：

- 上传文件
- 校验文件类型
- 保存文件元数据
- 调用存储模块

### `parse_service.py`

负责：

- 根据文件类型选择 parser
- 触发 OCR
- 保存解析结果

### `retrieval_service.py`

负责：

- 文档切片
- 向量化
- 检索相关内容

### `recipe_service.py`

负责：

- 把 Agent 输出转成结构化菜谱
- 统一补齐菜谱字段
- 做菜谱类结果校验

### `agent_service.py`

负责：

- 接收聊天请求
- 调用 orchestrator
- 管理 Agent 执行生命周期

## `src/agent/`

这是整个项目最关键的目录之一。

这里专门存放 Agent 编排逻辑，不放通用 CRUD，不放 HTTP 路由。

### `base_agent.py`

定义 Agent 基类。

适合放：

- 标准输入输出定义
- workflow 公共方法
- 日志与追踪基础逻辑

### `orchestrator.py`

这是 Agent 总调度器。

职责：

- 识别用户任务类型
- 选择对应 workflow
- 决定是否走文件解析、图像理解、检索增强

这个文件可以理解成“大脑中的路由器”。

### `intents.py`

存放意图类型定义和分类逻辑。

例如：

- recipe_generation
- document_qa
- image_qa
- ingredient_analysis

### `context_builder.py`

负责组装模型输入上下文。

适合整合：

- 用户当前消息
- 历史会话
- 解析结果
- 检索结果

### `response_builder.py`

负责把模型原始输出转成系统标准输出。

例如：

- 普通文本回答
- 结构化菜谱
- 文档摘要结果

### `prompts/`

这里放提示词模板。

建议按任务拆：

- 系统角色提示词
- 菜谱生成提示词
- 文档问答提示词

不要把长提示词散落在业务代码里。

### `tools/`

这里放 Agent 可调用工具。

例如：

- 读取文件解析结果
- 调用向量检索
- 调用图像理解
- 格式化菜谱输出

### `workflows/`

这里放不同任务的工作流实现。

建议一类任务一个 workflow 文件。

#### `text_chat_workflow.py`

只处理普通文本对话。

#### `document_qa_workflow.py`

处理“文档 + 问题”。

#### `image_qa_workflow.py`

处理“图片 + 问题”。

#### `recipe_generation_workflow.py`

处理菜谱生成。

#### `ingredient_analysis_workflow.py`

处理食材识别和组合分析。

## `src/parsers/`

这个目录专门放附件解析器。

原则：

- 一个文件类型一个 parser
- 每个 parser 只负责“解析”
- 不把业务理解逻辑塞进 parser

### `base_parser.py`

定义统一 parser 接口。

### `pdf_parser.py`

负责 PDF 文本提取。

### `docx_parser.py`

负责 Word 文本提取。

### `pptx_parser.py`

负责 PPT 文本提取。

### `txt_parser.py`

负责 txt 文本读取。

### `image_parser.py`

负责图片文件基础处理。

### `ocr_parser.py`

负责图中文字识别。

## `src/multimodal/`

这个目录专门放多模态理解能力。

它和 `parsers` 的区别是：

- `parsers` 更偏“抽取”
- `multimodal` 更偏“理解”

### `image_understanding.py`

做图像语义理解。

例如：

- 图里是什么菜
- 图里有哪些食材

### `ocr_service.py`

做 OCR 封装。

### `ingredient_detector.py`

做食材识别和标准化。

例如把：

- “西红柿”
- “番茄”

统一成系统内部同一种食材标识。

## `src/search/`

这个目录是为后续文档问答和长期对话准备的。

如果第一期不做向量检索，也建议把目录预留出来。

### `chunker.py`

负责把长文档切成小块。

### `embeddings.py`

负责生成向量。

### `vector_store.py`

负责向量存储读写。

如果项目主数据库使用 MySQL，这里建议默认不要直接把向量索引主存放在 MySQL 里，而是把它看成一个独立检索组件。

### `retriever.py`

负责按问题召回内容。

## `src/tasks/`

这个目录放异步任务。

因为文件解析、OCR、向量化都适合异步化。

### `parse_tasks.py`

处理文件解析任务。

### `embedding_tasks.py`

处理向量化任务。

### `cleanup_tasks.py`

处理临时文件清理、过期数据清理。

## `src/storage/`

这个目录封装文件存储方式。

### `base_storage.py`

定义统一存储接口。

### `local_storage.py`

本地开发时把文件存磁盘。

### `object_storage.py`

生产环境对接对象存储。

这样你的业务层不需要关心文件到底存在哪里。

## `src/utils/`

这个目录放通用工具函数。

适合放：

- 时间格式处理
- ID 生成
- 文件类型判断
- 文本清洗

不要把和业务强相关的逻辑放这里。

## `src/tests/`

这个目录放测试代码。

建议至少覆盖：

- 认证接口
- 文件上传
- Agent 对话入口
- 菜谱结构化输出

## 5. 这套结构下，什么文件夹存放什么

为了更直观，这里再用一句话总结：

- `api/`：只处理接口收发，不写重业务逻辑
- `schemas/`：定义请求和响应格式
- `db/models/`：定义数据库表
- `db/repositories/`：负责查库写库
- `services/`：写业务流程
- `agent/`：写 Agent 的编排、大模型调用和 workflow
- `parsers/`：解析 PDF、Word、PPT、图片
- `multimodal/`：做 OCR、图像理解、食材识别
- `search/`：做切片、向量化和检索
- `tasks/`：放异步任务
- `storage/`：封装文件存储
- `core/`：放全局配置、安全、日志、异常
- `utils/`：放通用工具方法
- `tests/`：放测试

## 6. 最关键的几个文件应该做什么

如果你准备从 0 开始建项目，我建议优先创建这些文件：

### `src/main.py`

先把服务跑起来。

### `src/api/v1/endpoints/agent.py`

先把统一聊天入口建出来。

### `src/services/agent_service.py`

先把聊天入口后的业务流程接起来。

### `src/agent/orchestrator.py`

先把意图识别和 workflow 分发逻辑建出来。

### `src/parsers/pdf_parser.py`

先支持 PDF 文本提取。

### `src/multimodal/ocr_service.py`

先支持图片 OCR。

### `src/services/recipe_service.py`

先保证做菜结果输出是结构化的。

## 7. 按你的项目目标，建议的开发顺序

如果按最小可用版本推进，推荐这样建：

1. 搭 `main.py`、`api/`、`core/`、`schemas/`
2. 搭 `db/` 和用户、会话、消息、附件表
3. 写 `auth_service.py`、`conversation_service.py`、`message_service.py`
4. 写 `file_service.py` 和 `storage/`
5. 写 `pdf_parser.py`、`docx_parser.py`、`pptx_parser.py`
6. 写 `ocr_service.py` 和图片解析
7. 写 `agent/orchestrator.py`
8. 写 `recipe_generation_workflow.py`
9. 写 `document_qa_workflow.py` 和 `image_qa_workflow.py`
10. 再补 `search/` 和异步 `tasks/`

## 8. 给你的一个简化落地建议

如果你现在不想一上来建太复杂，可以先做第一阶段简化版：

```text
backend/
├─ src/
│  ├─ main.py
│  ├─ api/
│  ├─ core/
│  ├─ schemas/
│  ├─ db/
│  ├─ services/
│  ├─ agent/
│  ├─ parsers/
│  ├─ multimodal/
│  └─ storage/
├─ uploads/
├─ requirements.txt
└─ .env.example
```

等第一版跑通以后，再逐步加：

- `search/`
- `tasks/`
- `tests/`
- `scripts/`
- `alembic/`

## 9. 结论

如果你要做的是一个真正可扩展的智能做菜助手 Agent，后端不能只按“接口文件堆在一起”的方式搭。

更合理的方式是：

- 用 `api` 管接口
- 用 `services` 管业务
- 用 `agent` 管智能流程
- 用 `parsers` 和 `multimodal` 管附件理解
- 用 `db` 管数据
- 用 `storage` 管文件

这样后面你增加：

- 更多文件格式
- 更复杂的食材识别
- 更强的菜谱工作流
- 更长的文档问答链路

都不会把项目结构拖乱。
