# CookingAgent Agent 应用开发面试总结

更新时间：2026-06-03  
适用场景：Agent 应用开发、RAG 应用开发、AI 全栈工程、LangChain 工程化岗位面试

## 1. 项目一句话

CookingAgent 是一个面向中文做菜场景的全栈 AI Agent 应用。项目把 LangChain Tool Calling Agent、RAG 知识库、长期记忆、会话摘要、附件解析入库、语音转写、联网搜索、天气查询和 React 聊天工作台整合到同一个产品闭环中。

面试时可以这样开场：

> 我做的是一个中文烹饪智能助手，不是只调一次大模型 API，而是围绕真实 Agent 应用搭了一套完整链路：前端支持会话、流式回复、附件和语音；后端用 FastAPI 分层；Agent 侧有意图识别、工作流编排、RAG 预检索、工具调用、模型 fallback、长期记忆和运行快照；RAG 侧支持多格式文档入库、Milvus 检索、rerank、缓存和 RAGAS 评测。

## 2. 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18、TypeScript、Vite、SSE 流式消费、MediaRecorder 录音 |
| 后端 API | FastAPI、Pydantic、SQLAlchemy、PyMySQL |
| Agent | LangChain 1.x、`create_agent`、Tool Calling、结构化输出 |
| 模型接入 | OpenAI-compatible ChatOpenAI 适配，支持 Kimi、AIHubMix、小米、OpenAI、本地模型 fallback |
| RAG | Milvus、sentence-transformers / OpenAI-compatible embedding、FlagEmbedding rerank、关键词召回、RRF 融合 |
| 文档解析 | MinerU CLI，支持 PDF、DOCX、PPTX、XLSX、JPG、PNG |
| 记忆 | MySQL `memory_items`、会话滚动摘要、规则/模型混合抽取 |
| 工具 | RAG、长期记忆、附件上下文、SerpApi、QWeather、菜谱格式化、可选 MCP 工具 |
| 缓存与限流 | Redis best-effort 缓存、固定窗口限流 |
| 评测 | Pytest、RAGAS、检索指标、Agent 评测方案文档 |

## 3. 总体架构

核心调用链路：

```text
Frontend Chat Workspace
  -> FastAPI /api/v1/agent/chat/stream
  -> AgentService
  -> AgentContextProvider
  -> AgentOrchestrator
  -> IntentResolver
  -> Workflow(answer / attachment_parse / document_ingest / memory_update)
  -> LangChainAgentRunner
  -> create_agent(model + tools + system_prompt)
  -> SSE delta / done
  -> messages + agent_runs persistence
```

后端分层比较清晰：

- `src/api`：FastAPI 路由、认证依赖、SSE 协议。
- `src/services`：业务事务，例如消息、文件、语音、Agent 回合。
- `src/repositories`：SQLAlchemy 数据访问。
- `agent`：Agent 编排、上下文契约、工作流、工具、提示词、RAG 预处理。
- `src/rag`：索引、切分、embedding、Milvus、rerank 和检索。

项目的设计重点是把“业务会话”和“Agent 推理”分开：`AgentService` 负责持久化和事务，`AgentOrchestrator` 负责选择工作流，`LangChainAgentRunner` 只负责把上下文、工具和模型交给 LangChain 执行。

## 4. 一轮对话如何运行

1. 前端通过 SSE endpoint 发送消息：`/api/v1/agent/chat/stream`。
2. 后端校验当前用户和会话归属，先保存用户消息。
3. `AgentContextProvider` 组装上下文：最近消息、会话摘要、长期记忆、附件 ID、知识库 ID、请求选项。
4. 创建 `agent_runs` 记录，保存 `input_snapshot`，便于排查和离线评测。
5. `ActionIntentResolver` 做高层意图识别：规则 + 本地小模型融合。
6. `AgentOrchestrator` 分派到对应 workflow：
   - 普通回答：`AnswerWorkflow`
   - 附件解析：`AttachmentParseWorkflow`
   - 附件入库：`DocumentIngestWorkflow`
   - 长期记忆更新：`MemoryUpdateWorkflow`
7. 普通回答工作流先执行默认 RAG，必要时补充 Web 搜索，再调用 LangChain Agent。
8. `LangChainAgentRunner` 根据候选模型顺序做 fallback，流式返回 `delta`。
9. 成功后保存助手消息，更新 `agent_runs.output_snapshot`，再异步性质地尝试更新会话摘要和长期记忆。
10. 失败时走本地兜底回复，并把失败原因、fallback 信息写入运行快照。

## 5. Agent 编排亮点

### 5.1 意图识别不是全交给大模型

项目的意图识别只判断“要触发什么系统动作”，不把 RAG 问答和普通问答拆开。实现上用规则和本地小模型融合：

- 规则识别明确的高风险动作，例如“把附件加入知识库”“解析附件”“记住我的偏好”。
- 小模型输出结构化 `intent_type / confidence / reason`。
- 按 `INTENT_RULE_WEIGHT` 和 `INTENT_MODEL_WEIGHT` 融合分数。
- 对附件解析、文档入库这类有副作用动作加安全门：必须有附件，并且规则侧明确命中，才允许触发。

面试可讲取舍：

> 我没有让大模型自由决定所有动作，因为文档入库、附件解析这类操作会改变后端状态。规则负责安全边界，小模型负责补充语义判断，这样能降低误触发副作用工具的风险。

### 5.2 Workflow 化

项目把 Agent 能力拆成工作流，而不是全部塞进一个 prompt：

- `AnswerWorkflow`：统一回答、RAG/Web 上下文、引用校验。
- `AttachmentParseWorkflow`：调用 MinerU 解析附件，保存 parse result。
- `DocumentIngestWorkflow`：解析附件、内容主题校验、切分、embedding、写入 Milvus。
- `MemoryUpdateWorkflow`：抽取和更新长期记忆。

这样做的好处：

- API endpoint 不需要知道每种 Agent 任务细节。
- 新增能力时优先新增 workflow 或 tool。
- 每个工作流都有独立的 `output_snapshot`，方便评测和追踪。

### 5.3 模型 fallback

模型由 `model_factory.py` 统一构造，支持 Kimi、AIHubMix、小米、OpenAI、本地 OpenAI-compatible 服务。`LangChainAgentRunner` 会按候选顺序尝试模型。

流式场景下的处理策略：

- 如果模型在尚未输出文本前失败，可以切换下一个候选模型。
- 如果已经输出了部分文本，再失败则抛出错误，避免同一轮回答前后模型混杂。
- fallback 尝试会写入 `model_fallback` 元数据，便于线上排障。

这是 Agent 应用工程化里很关键的一点：模型不可用不是异常情况，而是必须设计的运行状态。

## 6. RAG 设计

### 6.1 入库链路

本地菜谱数据支持多种格式：Markdown、TXT、JSON、JSONL、CSV。附件入库支持 PDF、Office 和图片，经 MinerU 解析为 Markdown 后再入库。

入库流程：

```text
source document
  -> DocumentLoader / MinerU
  -> TextChunker
  -> EmbeddingClient
  -> RagIndexingService
  -> MilvusRagRepository
```

切分策略：

- 优先按 Markdown 标题和段落切分。
- 保留 `section_title`、`heading_path`、`source_path` 等元数据。
- 控制 target size、max size 和 overlap，兼顾召回和上下文长度。

### 6.2 检索链路

回答前默认执行 `RagContextBuilder`：

1. `RetrievalPolicy` 判断是否需要检索。
2. `QueryRewriter` 把多轮对话里的问题改写成独立检索 query。
3. `RagRetriever` 做向量召回。
4. 如果开启 hybrid search，再做关键词召回。
5. 用 RRF 融合向量和关键词候选。
6. 可选 rerank。
7. Redis 缓存检索结果。
8. 返回结构化 `RagContext`，写入 `agent_runs.output_snapshot`。

面试可讲亮点：

> 我把 RAG 分成控制面和数据面。控制面决定这一轮是否检索、如何改写 query、是否补充 Web；数据面负责 chunk、embedding、Milvus、rerank 和缓存。这样后续替换 embedding 或调整检索策略，不会影响 Agent 主链路。

### 6.3 引用与幻觉控制

`CitationValidator` 做了两类保护：

- 用户明确要求“根据知识库/根据资料/根据文档”时，如果 RAG 和 Web 都没有证据，就拒答，而不是硬编。
- 如果 RAG 命中，会在回答末尾追加已核验来源；如果模型声称“来源：知识库”但本轮没有 RAG 命中，会追加校验说明纠正。

可用于回答“如何降低幻觉”：

> 我没有只靠 prompt 说不要幻觉，而是把证据状态结构化，并在回答后做引用校验。显式证据请求没有命中时直接拒答；命中时把真实 chunk 的 source path 和标题追加到回答中。

## 7. 长期记忆与上下文管理

项目有两层上下文压缩：

1. 最近消息：直接进入 LangChain messages。
2. 会话摘要：长会话达到阈值后，用模型滚动生成摘要。
3. 长期记忆：保存用户偏好、忌口、厨具、健康目标等。

长期记忆实现：

- `MemoryUpdateWorkflow` 优先用 LangChain structured output 抽取记忆。
- 模型失败时退回规则抽取。
- 写入 MySQL `memory_items`。
- 有去重逻辑，显式“更新/修改/改成”会更新同类型最新记忆。
- 回答时由 `AgentContextProvider` 查询相关记忆并注入 system prompt。
- Agent 也可以调用 `search_user_memory` 工具再次查看。

面试可讲取舍：

> 当前长期记忆没有上向量库，而是按用户取最近记忆后做轻量关键词排序。因为早期用户记忆规模不大，这样更简单可控；如果规模扩大，可以把 repository 方法替换成向量检索，Agent 层契约不需要变。

## 8. 工具设计

本地工具包括：

- `rag_search`：按本轮知识库 ID 检索。
- `search_user_memory`：查询长期记忆。
- `read_attachment_context`：读取附件上下文。
- `web_search`：SerpApi 联网搜索。
- `get_weather`：QWeather 天气查询。
- `format_recipe_plan`：菜谱格式化工具。

可选 MCP 工具接入：

- 通过 `AGENT_MCP_SERVERS_JSON` 配置 MCP server。
- 当前只允许 MCP 提供 RAG/Web/Weather 类工具名，避免任意 MCP 工具覆盖本地业务逻辑。

面试可讲原则：

> Agent 工具不是越多越好。我把工具限定为和烹饪任务强相关的工具，并且对 MCP 工具做白名单过滤，避免把不可控能力暴露给 Agent。

## 9. 附件、语音与多模态输入

附件链路：

- 前端限制扩展名和大小，支持 PDF、DOCX、PPTX、XLSX、JPG、PNG。
- 后端再次校验数量、扩展名、大小和会话归属。
- 文件写入本地上传目录，记录 hash、mime、大小、解析状态。
- MinerU 解析为 Markdown，结果保存到 `parse_results`。
- 入库前通过独立内容校验模型判断是否为烹饪相关资料。
- 非烹饪资料、低置信度资料、校验模型失败都不写入知识库。

语音链路：

- 前端用 MediaRecorder 录音。
- 后端支持 OpenAI-compatible `/audio/transcriptions` 或本地 faster-whisper。
- 校验音频扩展名、大小和可获取的时长。
- 转写结果回填输入框，不直接创建语音消息。

注意诚实表达：

> 当前附件解析和入库工作流已经实现，但 `read_attachment_context` 工具里的附件上下文注入还没有完全打通，后续应该把 parse result 自动注入 `AgentTurnContext.attachment_context`，并把解析/入库改造成异步任务。

## 10. 前端工作台

前端不是简单页面，而是一个聊天 workspace：

- 会话列表、会话切换、新建会话。
- 消息列表和 Markdown 展示。
- SSE 流式解析：`user_message`、`delta`、`done`。
- 乐观用户消息和 streaming assistant 占位消息。
- 附件上传、移除、入库重试。
- 语音录制、转写、错误提示。
- 搜索会话和 prompt suggestion。
- 统一错误映射，把后端错误码转换成用户可理解的提示。

面试可讲点：

> 前端没有等后端完整返回后再更新，而是先显示 optimistic user message，再显示 streaming assistant message，最后用后端真实 message 替换临时消息。这样能降低用户感知延迟。

## 11. 数据持久化与可观测基础

核心表：

- `users`：用户账号。
- `conversations`：会话。
- `messages`：消息。
- `attachments`：附件。
- `parse_results`：附件解析结果。
- `agent_runs`：一次 Agent 执行快照。
- `memory_items`：用户长期记忆。
- `conversation_summaries`：滚动摘要。

`agent_runs` 是面试重点：

- 保存 `input_snapshot`：用户消息、最近消息、摘要、记忆、附件、知识库 ID。
- 保存 `output_snapshot`：意图、工作流、RAG 结果、Web 结果、引用校验、工具调用数、fallback 信息。
- 保存状态、模型名、错误码、开始/完成时间。

价值：

- 线上排障可以知道模型为什么这样回答。
- 离线评测可以复用真实运行快照。
- 后续做成本统计、工具轨迹评估、模型对比有数据基础。

## 12. RAG 评测与参数调优

### 12.1 评测目标

RAG 评测分两类问题：

- 检索是否找对资料：应该命中哪个菜谱文件、命中排名是否靠前、是否漏掉关键上下文。
- 生成是否忠实可用：回答是否基于 retrieved contexts、是否覆盖 reference、是否相关、是否编造。

所以项目没有只看 RAGAS 分数，而是把确定性的检索指标和 LLM judge 指标分开。

### 12.2 当前评测资产

- 评测脚本：`backend/scripts/evaluate_rag_with_ragas.py`。
- Case 文件：`backend/eval/ragas_cases.jsonl`，当前是 30 条中文菜谱问答 case。
- 每条 case 包含：`question`、`reference`、`knowledge_base_ids`、`source_path` 或 `expected_source_paths`。
- 评测输出：
  - `samples_*.jsonl`：项目真实 RAG + Agent 运行样本。
  - `retrieval_metrics_*.json`：确定性检索指标。
  - `scores_*.csv`：RAGAS 指标。

运行方式：

```powershell
# 只跑检索和样本生成，不调用 RAGAS judge，适合快速调检索参数
python backend/scripts/evaluate_rag_with_ragas.py --limit 30 --skip-evaluate

# 跑完整 RAGAS 评测
python backend/scripts/evaluate_rag_with_ragas.py --limit 30
```

脚本默认关闭 Web Search fallback，因为这一步要隔离本地知识库质量。如果打开联网搜索，RAGAS 看到的回答来源会混入网页，难以判断本地 RAG 是否真的有效。

### 12.3 指标解释

确定性检索指标：

| 指标 | 含义 | 用途 |
| --- | --- | --- |
| `hit_at_k` | 返回的 top-k chunk 中是否包含期望来源文档 | 判断能不能找对资料 |
| `recall_at_k` | 期望来源被召回的比例 | 多来源问题是否漏文档 |
| `reciprocal_rank` / MRR | 第一个正确来源的排名倒数 | 判断正确结果是否排在前面 |

RAGAS 指标：

| 指标 | 含义 | 主要观察点 |
| --- | --- | --- |
| `faithfulness` | 回答是否被上下文支持 | 防幻觉 |
| `context_precision` | 检索上下文是否少噪声 | 检索精度 |
| `context_recall` | 检索上下文是否覆盖答案所需信息 | 检索召回 |
| `response_relevancy` | 回答是否贴合用户问题 | 生成相关性 |
| `answer_correctness` | 回答与 reference 是否一致 | 最终答案质量 |

当前仓库中保留的一次 30 case 评测基线：

- `retrieval_metrics_20260525_101622.json`：`hit_at_k=1.0`，`recall_at_k=1.0`，`mrr=0.9167`。
- `scores_20260525_105833.csv` 平均值：`faithfulness=0.7318`，`context_precision=0.9194`，`context_recall=0.9333`，`answer_relevancy=0.8517`，`answer_correctness=0.6779`。

面试里可以这样解释：

> 这组结果说明检索链路已经能稳定找对资料，而且正确文档大部分排得比较靠前；但 faithfulness 和 answer_correctness 还有提升空间，说明后续优化重点不只是召回，还包括上下文裁剪、引用约束和回答 prompt。

### 12.4 RAG 参数基线

当前关键参数来自 `example.env` 和 `Settings`：

| 参数 | 当前值 | 控制内容 |
| --- | ---: | --- |
| `RAG_CHUNK_TARGET_SIZE` | 700 | chunk 目标长度 |
| `RAG_CHUNK_MAX_SIZE` | 1000 | 单个 chunk 最大长度 |
| `RAG_CHUNK_OVERLAP_SIZE` | 100 | 相邻 chunk 重叠 |
| `RAG_VECTOR_TOP_K` | 20 | 向量召回候选数 |
| `RAG_FINAL_TOP_K` | 5 | 最终注入模型的 chunk 数 |
| `RAG_MIN_SCORE` | 0.25 | Milvus 向量召回最低分 |
| `RAG_HYBRID_SEARCH_ENABLED` | true | 是否启用关键词召回 |
| `RAG_KEYWORD_TOP_K` | 20 | 关键词召回候选数 |
| `RAG_KEYWORD_SCAN_LIMIT` | 5000 | 关键词扫描上限 |
| `RAG_RRF_K` | 60 | RRF 融合平滑参数 |
| `RAG_QUERY_REWRITE_ENABLED` | true | 是否启用 query rewrite |
| `RAG_QUERY_REWRITE_TEMPERATURE` | 0.6 | query rewrite 生成温度 |
| `RAG_QUERY_REWRITE_MAX_CHARS` | 180 | 改写 query 最大长度 |

模型侧参数：

- Embedding 默认本地 `models/bge-small-zh-v1.5`。
- Rerank 默认本地 `models/bge-reranker-v2-m3`。
- RAGAS judge 会复用项目模型配置，也可通过 `RAGAS_MODEL_PROVIDER` 和 `RAGAS_MODEL_NAME` 单独指定。

### 12.5 调参顺序

推荐调参顺序：

1. 固定评测集和知识库版本，不同时改多个变量。
2. 先跑 `--skip-evaluate`，只看 `hit_at_k / recall_at_k / MRR`，低成本调检索。
3. 先调 chunk，再调召回范围，再调阈值，再调 rerank 和融合。
4. 检索指标稳定后，再跑完整 RAGAS，看回答忠实度和正确性。
5. 对低分 case 打开 `samples_*.jsonl`，人工看 retrieved contexts 和 response，判断是检索问题还是生成问题。
6. 把有效参数固化到 `.env` / `example.env`，把失败 case 加入 regression 集。

### 12.6 具体参数怎么调

| 现象 | 优先检查 | 调参方向 |
| --- | --- | --- |
| `hit_at_k` 低，正确文档没召回 | `RAG_VECTOR_TOP_K`、关键词召回、query rewrite | 增大 `RAG_VECTOR_TOP_K`，开启/增大 `RAG_KEYWORD_TOP_K`，检查 query rewrite 是否改偏 |
| `MRR` 低，正确文档在后面 | rerank、RRF、chunk 粒度 | 确认 rerank 开启；调小 `RAG_RRF_K` 让高排名候选更突出；减少噪声 chunk |
| `context_precision` 低 | `RAG_FINAL_TOP_K`、`RAG_MIN_SCORE` | 减小 `RAG_FINAL_TOP_K`，提高 `RAG_MIN_SCORE`，减少低相关片段进入 prompt |
| `context_recall` 低 | chunk 长度、top-k、overlap | 增大 `RAG_FINAL_TOP_K` 或 `RAG_VECTOR_TOP_K`；适当增大 chunk 或 overlap |
| `faithfulness` 低 | prompt、引用校验、上下文噪声 | 强化“只能基于资料回答”；降低噪声；无证据时拒答 |
| `answer_correctness` 低但检索命中高 | 生成 prompt、reference 覆盖、chunk 内容位置 | 优化回答模板；把关键步骤/用量所在 chunk 排到前面 |
| 延迟太高 | vector top-k、keyword scan、rerank | 降低 `RAG_VECTOR_TOP_K`、`RAG_KEYWORD_SCAN_LIMIT`，或只对较少候选 rerank |

具体参数取舍：

- `RAG_CHUNK_TARGET_SIZE=700`：适合菜谱类文档，因为一段菜谱通常包含原料、步骤、小贴士。太小会把“食材”和“做法”拆开，影响 answer correctness；太大则容易引入无关步骤，影响 context precision。
- `RAG_CHUNK_OVERLAP_SIZE=100`：解决标题、上下段步骤被切开的边界问题。overlap 太大会造成重复片段，降低上下文利用率。
- `RAG_VECTOR_TOP_K=20`：先保留足够召回候选，再交给 rerank 和 final top-k 裁剪。调大能提高召回，但会增加 Milvus 和 rerank 耗时。
- `RAG_FINAL_TOP_K=5`：最终给模型的上下文数量。菜谱问答通常 3 到 5 个 chunk 足够；如果问题跨多个来源可提高，但要观察 context precision。
- `RAG_MIN_SCORE=0.25`：用于过滤弱相关向量结果。阈值太低会带入相似但无关的菜，阈值太高会导致 miss。调它时重点看 miss 率和 context precision。
- `RAG_HYBRID_SEARCH_ENABLED=true`：中文菜名、精确食材、数字用量经常靠关键词更稳，所以用关键词召回补向量召回。
- `RAG_RRF_K=60`：用于平衡向量召回和关键词召回。K 越小越偏向各路召回的头部结果，K 越大越平滑。MRR 低时可以尝试调小，噪声多时结合 rerank 观察。
- `RAG_QUERY_REWRITE_ENABLED=true`：多轮问题里“刚才那个菜”“那一步”需要改写成独立 query。调参时要对比 raw query 和 rewritten query，如果改写添加了用户没说过的条件，就要降低温度或收紧 prompt。

### 12.7 一套可讲的调优案例

可以这样组织面试回答：

> 我先用 30 条菜谱 case 固定评测集，每条都标注 expected source path。第一阶段只跑 `--skip-evaluate`，不调用 judge 模型，先把检索调稳。当 `hit_at_k` 和 `recall_at_k` 到 1.0，但 MRR 还有 case 是 0.5 时，我重点看正确文档为什么排第二：如果是同名或相近菜谱干扰，就依赖 rerank 和 RRF；如果是 query 改写缺少菜名，就优化 query rewrite prompt。第二阶段再跑 RAGAS，如果 `context_precision` 高但 `answer_correctness` 低，说明资料找对了但生成没有完整覆盖 reference，就优化回答 prompt 和引用约束，而不是盲目增大 top-k。

### 12.8 Agent 评测规划

已经设计但待进一步落地的 Agent 评测：

- L0：工程正确性测试。
- L1：RAG 快速评测。
- L2：Agent 离线回放，评估意图、workflow、工具调用、来源、fallback。
- L3：发布候选评测，绑定 prompt/model/knowledge base/git sha。
- L4：线上抽样评测，从 `agent_runs` 回流失败 case。

面试回答：

> 我认为 Agent 评测不能只看最终答案，还要看轨迹。比如是否调用了禁止工具、是否在没有证据时强答、是否用了错误 workflow、是否伪造来源。这些都应该从 `agent_runs.output_snapshot` 里抽取规则指标。

## 13. 项目亮点总结

可以重点讲这 8 点：

1. 不是单轮聊天 demo，而是全栈 Agent 产品闭环。
2. Agent 主链路有清晰分层：Service、Context、Orchestrator、Workflow、Runner、Tools。
3. 意图识别采用规则 + 小模型融合，并保护副作用动作。
4. RAG 不是简单向量检索，包含 query rewrite、hybrid recall、RRF、rerank、缓存和引用校验。
5. 长期记忆有结构化抽取、规则 fallback、去重、更新和 prompt 注入。
6. 模型调用有多 provider fallback 和流式场景失败处理。
7. 附件入库前做烹饪主题校验，避免无关文档污染知识库。
8. `agent_runs` 记录输入输出快照，为排障、评测、回放和模型对比打基础。

## 14. 当前短板与改进路线

面试里被问“还有哪些不足”时，可以坦诚但要有方案：

| 短板 | 当前状态 | 改进方案 |
| --- | --- | --- |
| 异步任务 | 附件解析和入库仍偏同步 workflow | 引入任务队列和 worker，提供任务状态、进度、重试、取消 |
| 生产部署 | 缺少 Docker、CI/CD、Alembic 完整迁移 | 补齐 Docker Compose、迁移 baseline、GitHub Actions |
| 安全加固 | 基础认证已有，生产安全还不足 | HttpOnly Cookie、CORS/Host allowlist、安全响应头、日志脱敏 |
| 附件上下文 | 解析/入库已实现，Agent 读取附件上下文还未完全打通 | 将 parse result 注入 `AgentTurnContext.attachment_context` |
| 记忆管理 | 后端记忆存在，前端缺少用户可见管理页 | 增加记忆查看、删除、禁用、导出 |
| Agent 评测 | 有 RAGAS 和测试，缺少完整轨迹评测 | 建立 Agent case schema 和 rule/LLM judge 混合评分 |
| 可观测性 | 有日志和 run snapshot，缺少指标/trace | 增加 Prometheus、trace、成本和 latency dashboard |

## 15. 高频面试问答

### Q1：你这个项目和普通 ChatGPT 套壳有什么区别？

普通套壳通常只有前端输入和模型回复。这个项目有完整 Agent 工程链路：多轮会话持久化、长期记忆、RAG 知识库、附件解析入库、工具调用、意图识别、模型 fallback、流式 SSE、运行快照和评测脚本。模型只是执行层，核心是围绕真实业务构建上下文、证据、工具和状态管理。

### Q2：为什么要用 Agent，而不是普通 RAG QA？

因为用户任务不只有问答，还包括解析附件、把附件加入知识库、记住偏好、查天气、联网搜索等动作。Agent 可以在统一对话界面里选择工具和工作流。为了避免失控，项目没有让模型自由做所有决策，而是用 orchestrator 和 workflow 限定高层动作。

### Q3：RAG 如何保证答案可靠？

项目先用 retrieval policy 判断是否检索，再通过 query rewrite 提升多轮问题召回；检索侧做向量召回、关键词召回、RRF 融合和 rerank；回答侧通过 system prompt 告诉模型证据状态；最后用 citation validator 追加真实来源或在无证据时拒答。也就是说，可靠性不是只靠 prompt，而是贯穿检索、生成和后处理。

### Q4：如何处理模型不可用？

模型候选由配置生成，运行时按优先级尝试。非流式场景失败就切换候选；流式场景如果还没输出 token，可以切换，如果已经输出则中止并走错误处理，避免一个回答由多个模型拼接。所有尝试结果都会写入 `model_fallback` 快照。

### Q5：长期记忆如何避免乱记？

只保存明确长期有用的信息，例如忌口、过敏、口味、厨具、健康目标。抽取时使用结构化输出，失败后走规则 fallback；同时做去重，显式更新时才覆盖同类型记忆。prompt 里也声明如果长期记忆和本轮用户输入冲突，以本轮为准。

### Q6：附件为什么要做内容校验？

如果用户上传财务报表、代码文档等无关资料，直接进入向量库会污染知识库，后续 RAG 会召回错误内容。所以项目用独立的小模型做烹饪主题分类，只有 `cooking_related` 且置信度足够才入库，失败或不确定时 fail closed。

### Q7：如何设计 Agent 评测？

我会分层做：L0 跑单元和集成测试；L1 跑 RAGAS 和检索指标；L2 跑 Agent 离线 case，看意图、workflow、工具轨迹、来源和最终答案；L3 做发布门禁，绑定模型、prompt、知识库和 git sha；L4 从线上 `agent_runs` 抽样，脱敏后回流到 regression case。

### Q8：RAG 参数具体是怎么调优的？

我会先固定 case 集和知识库版本，再分两阶段调。第一阶段只跑 `--skip-evaluate`，看 `hit_at_k`、`recall_at_k` 和 MRR，优先保证正确文档能召回且排名靠前。这个阶段主要调 chunk 大小、`RAG_VECTOR_TOP_K`、`RAG_MIN_SCORE`、hybrid search、RRF 和 rerank。第二阶段再跑完整 RAGAS，看 `faithfulness`、`context_precision`、`context_recall`、`answer_correctness`。如果检索命中高但答案不对，就不继续盲目调 top-k，而是看 prompt、上下文裁剪和引用约束。

当前基线参数是 chunk target 700、max 1000、overlap 100，向量召回 top-k 20，最终 top-k 5，min score 0.25，启用关键词召回和 RRF。仓库保留的一次 30 case 结果里，检索 `hit_at_k=1.0`、`recall_at_k=1.0`、`mrr=0.9167`，说明召回比较稳；后续重点是继续提升忠实度和最终答案正确性。

### Q9：如果让你继续做生产化，你优先做什么？

优先级是：一，补安全和部署底座，包括 Docker、迁移、CI、生产密钥校验、CORS/Host、安全头；二，把附件解析和知识库入库异步化；三，完善 Agent 轨迹评测和指标；四，做记忆管理、引用展示、任务进度等产品体验。

## 16. 面试 2 分钟项目介绍稿

我做了一个叫 CookingAgent 的中文烹饪智能助手。它不是简单调用大模型，而是一个完整的 Agent 应用：前端是 React 聊天工作台，支持会话、附件、语音和流式回复；后端是 FastAPI 分层架构，负责认证、消息、文件、语音、缓存和持久化；Agent 层用 LangChain `create_agent`，并把一次对话拆成上下文构建、意图识别、工作流编排、RAG 增强、工具调用和模型 fallback。

我重点做了几个工程化设计。第一，意图识别用规则和本地小模型融合，附件解析和文档入库这种有副作用动作必须规则明确命中，避免模型误触发。第二，RAG 不是简单向量检索，包含检索决策、查询改写、向量召回、关键词召回、RRF 融合、rerank、缓存和引用校验。第三，长期记忆通过结构化输出抽取用户偏好，并保存到 MySQL，回答时和会话摘要一起注入上下文。第四，每轮 Agent 都有 `agent_runs` 快照，记录输入、输出、RAG、工具、模型 fallback 和错误信息，方便排障和后续评测。

如果继续生产化，我会优先补异步任务队列、CI/CD、数据库迁移、安全加固和 Agent 轨迹评测，把当前 MVP 演进成可上线运行的 Agent 系统。

## 17. 代码导览

| 模块 | 位置 |
| --- | --- |
| Agent 主服务 | `backend/src/services/agent_service.py` |
| 编排器 | `backend/agent/orchestration/orchestrator.py` |
| 意图识别 | `backend/agent/orchestration/intent_resolver.py` |
| LangChain 运行器 | `backend/agent/runner.py` |
| 模型工厂 | `backend/agent/factories/model_factory.py` |
| 工具工厂 | `backend/agent/factories/tool_factory.py` |
| 回答工作流 | `backend/agent/workflows/answer_workflow.py` |
| 记忆工作流 | `backend/agent/workflows/memory_update_workflow.py` |
| 附件入库工作流 | `backend/agent/workflows/document_ingest_workflow.py` |
| RAG 上下文构建 | `backend/agent/rag/context_builder.py` |
| RAG 检索器 | `backend/src/rag/retriever.py` |
| 文档切分 | `backend/src/rag/chunker.py` |
| SSE API | `backend/src/api/v1/endpoints/agent.py` |
| 前端流式消费 | `apps/web/src/services/chat/chatService.ts` |
| 前端工作台状态 | `apps/web/src/hooks/chat/useWorkspace.ts` |
