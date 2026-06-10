# LangSmith 离线 Agent 评测设计

日期：2026-06-10  
项目：CookingAgent  
状态：已确认设计，待用户审阅书面规格

## 1. 目标

为 CookingAgent 建立一套基于 LangSmith 的离线评测体系，覆盖当前代码中已声明的 Agent 能力、主要失败分支和有副作用的端到端工作流。

LangSmith 负责：

- 管理版本化数据集。
- 运行和对比 Experiment。
- 保存 Agent、模型和工具调用轨迹。
- 汇总规则评分、RAGAS 评分和 LLM-as-judge 评分。
- 按功能套件、风险等级和版本元数据筛选结果。

现有测试和 RAGAS 能力继续保留：

- Pytest 验证确定性代码边界和工程正确性。
- RAGAS 继续评估 RAG 忠实度、上下文质量和答案正确性。
- LangSmith 将各类离线结果组织为可比较的 Agent 行为实验。

本设计不包含线上 tracing、线上抽样评测和 CI 发布门禁，它们属于后续阶段。

## 2. 评测边界

完整离线评测边界不能只从 `AgentOrchestrator` 开始。文件上传、消息绑定和服务持久化发生在 Agent 工作流之外，但它们是附件解析和入库能力成立的必要条件。

```text
文件上传 / 消息绑定
        ↓
上下文构建 / 意图识别
        ↓
工作流路由
        ↓
回答 / 附件解析 / 文档入库 / 记忆更新
        ↓
RAG / Web / 工具调用 / 模型 fallback
        ↓
结果持久化 / 会话摘要 / 记忆副作用
```

所有有副作用的能力都必须至少包含成功、失败和边界场景。文件上传、解析、主题校验、向量化、检索和附件问答必须包含完整端到端场景。

## 3. 设计原则

### 3.1 复用真实项目入口

评测 Target 不实现简化版 Agent，而是调用项目真实入口：

- `AgentOrchestrator`
- `AgentService`
- `FileService`
- `AttachmentParseWorkflow`
- `DocumentIngestWorkflow`
- `MemoryUpdateWorkflow`
- `RagContextBuilder`
- `LangChainAgentRunner`

### 3.2 确定性优先

可以精确判断的行为使用规则评分器，不交给 LLM 判断。例如：

- 意图和工作流是否正确。
- 附件状态是否正确。
- 是否命中指定来源。
- 是否调用禁用工具。
- 是否发生正确的模型 fallback。
- 是否持久化正确状态。

### 3.3 场景可复现

离线评测默认使用：

- 隔离的测试数据库。
- 固定附件资产。
- 固定 RAG 知识库版本。
- Mock Web、天气、MinerU 故障和模型故障。
- 真实 Agent 模型和真实 RAG 作为可选完整运行配置。

外部服务 Mock 响应和故障注入必须由 Case 显式声明，不能隐式依赖机器状态。

### 3.4 允许预期失败

评测集应包含能够暴露已知缺口的 Case。此类 Case 标记为 `known_gap`，仍记录失败，但在修复前不作为发布硬门禁。

## 4. LangSmith 数据模型

每个 LangSmith Example 包含 `inputs`、`outputs` 和 `metadata`。

```json
{
  "inputs": {
    "runner_type": "agent_turn",
    "messages": [
      {"role": "user", "content": "蛋炒饭为什么推荐使用隔夜冷饭？"}
    ],
    "setup": {
      "knowledge_base_ids": ["cookbook"],
      "user_memories": [],
      "attachments": [],
      "mock_services": {
        "web_search": "disabled",
        "weather": "disabled"
      }
    }
  },
  "outputs": {
    "intent_type": "answer",
    "workflow_name": "answer_workflow",
    "required_source_paths": ["data/cook/dishes/staple/蛋炒饭.md"],
    "answer_rubric": [
      "说明隔夜饭水分较少",
      "说明更容易炒到粒粒分明",
      "提供现煮米饭快速降温的替代方案"
    ],
    "forbidden_claims": ["必须把米饭冷冻一整晚"],
    "tool_policy": {
      "must_call": [],
      "must_not_call": ["web_search", "get_weather"]
    }
  },
  "metadata": {
    "case_id": "rag_recipe_001",
    "suite": "answer_rag",
    "risk_level": "P1",
    "graders": ["deterministic", "ragas", "llm_judge"],
    "known_gap": false
  }
}
```

### 4.1 多步骤场景

附件端到端场景使用 `steps` 表达完整业务流程。

```json
{
  "inputs": {
    "runner_type": "attachment_pipeline",
    "steps": [
      {
        "action": "upload",
        "asset_path": "backend/eval/upload_ingest_samples/01_recipe_should_ingest.docx"
      },
      {
        "action": "send_message",
        "content": "请把这个附件加入知识库"
      },
      {
        "action": "query",
        "content": "根据刚才上传的菜谱，关键步骤是什么？"
      }
    ]
  },
  "outputs": {
    "upload_status": "accepted",
    "intent_type": "document_ingest",
    "workflow_name": "document_ingest_workflow",
    "parse_status": "completed",
    "validation_category": "cooking_related",
    "embedding_status": "completed",
    "retrieval_must_hit_uploaded_document": true,
    "answer_must_use_uploaded_content": true
  },
  "metadata": {
    "case_id": "attachment_e2e_001",
    "suite": "document_ingest",
    "risk_level": "P0",
    "graders": ["deterministic", "llm_judge"]
  }
}
```

## 5. Target Runner

### 5.1 `agent_turn`

用于单轮和多轮 Agent 行为：

- 构造 `AgentTurnContext`。
- 可预置最近消息、会话摘要、长期记忆、附件上下文和知识库。
- 调用 `AgentOrchestrator` 或 `AgentService`。
- 返回回答、意图、工作流、RAG/Web 快照、引用、fallback、使用量和轨迹摘要。

### 5.2 `attachment_pipeline`

用于附件完整链路：

- 创建隔离用户和会话。
- 调用 `FileService` 上传真实样例文件。
- 绑定消息并触发解析或入库工作流。
- 检查附件、解析结果、主题校验和 embedding 状态。
- 可继续执行检索和附件问答步骤。
- 场景结束后清理数据库、上传文件和测试索引数据。

### 5.3 `service_flow`

用于服务编排、故障注入和持久化：

- 调用 `AgentService.chat_stream` 或指定 Service。
- 模拟模型、数据库、Web、MinerU 和 Milvus 故障。
- 验证 SSE 事件、消息持久化、`agent_run` 状态、fallback 和非关键副作用隔离。

## 6. 数据集覆盖矩阵

首版完整回归集目标约 150 条，从中标记约 40 条 Smoke Case。

| 套件 | 目标数量 | 覆盖内容 |
| --- | ---: | --- |
| `intent_orchestration` | 12 | 意图融合、工作流路由、副作用保护 |
| `answer_rag` | 30 | 复用现有 RAGAS 菜谱数据 |
| `rag_behavior` | 12 | 查询改写、跳过、命中、未命中、异常 |
| `web_citation` | 10 | Web fallback、来源与伪造链接 |
| `tools_mcp` | 15 | RAG、附件、记忆、天气、Web、MCP |
| `attachment_upload` | 14 | 上传、校验、落盘、绑定、删除 |
| `attachment_parse` | 14 | MinerU 解析、失败、重试、幂等 |
| `document_ingest` | 22 | 主题校验、向量化、拒绝、失败、重试 |
| `attachment_qa` | 6 | 基于解析附件回答 |
| `memory_summary` | 14 | 记忆创建、更新、使用、摘要 |
| `fallback_persistence` | 12 | 模型 fallback、流式响应、运行记录 |
| `safety_boundary` | 10 | 注入、越权、伪造来源、危险建议 |

数量为实施阶段的初始目标，最终数量由覆盖矩阵决定，不为了达到数量重复创建低价值 Case。

## 7. 套件详细内容

### 7.1 意图和工作流

- 普通问答进入 `answer_workflow`。
- 有附件并明确要求解析时进入 `attachment_parse_workflow`。
- 有附件并明确要求入库时进入 `document_ingest_workflow`。
- 明确长期偏好进入 `memory_update_workflow`。
- 没有附件时，模型不得仅凭语义触发附件副作用工作流。
- 意图模型不可用时保留规则结果。
- 规则和模型冲突时遵守融合权重和副作用保护。

### 7.2 RAG 和回答

- 复用 `backend/eval/ragas_cases.jsonl` 的 30 条菜谱 Case。
- 领域问题应检索。
- 问候和控制轮应跳过检索。
- 多轮指代通过查询改写形成独立检索查询。
- RAG 命中、未命中、禁用和异常。
- 指定知识库与默认 `cookbook` 合并。
- `top_k` 选项生效。
- 命中时附加已核验来源。
- 明确要求资料依据但无证据时拒绝强答。
- 回答错误声称来自知识库时进行纠正。

### 7.3 Web、天气和工具

- RAG 未命中后 Web 自动补充。
- Web 命中、未命中、未配置、请求异常和 provider 错误。
- 最终回答只能引用提供的网页标题和链接。
- 天气当前查询、未来查询、非法日期、历史日期、超过七天、未配置和请求异常。
- `rag_search` 命中、未命中、异常和无知识库。
- `read_attachment_context` 有内容、无内容和无附件。
- `search_user_memory` 有结果、无结果和相关性排序。
- `format_recipe_plan` 正常输入和空输入。
- MCP 工具过滤、重复工具名和本地/MCP 能力冲突。

### 7.4 文件上传

- 合法 PDF、DOCX、PPTX、XLSX、JPG 和 PNG。
- 多附件上传并保持顺序。
- 数量超限、不支持扩展名、无扩展名、空文件和超大文件。
- 会话不存在和跨用户操作。
- 数据库写入失败时回滚并清理落盘文件。
- 删除未绑定附件。
- 拒绝删除已绑定附件。
- 附件绑定到消息。
- 拒绝绑定不存在、跨会话或已绑定附件。
- 非文档内容伪装合法扩展名的安全 Case。

### 7.5 附件解析

- 各支持格式解析成功。
- 多附件全部成功和部分失败。
- 文件不存在、MinerU 命令不存在、超时、非零退出码。
- MinerU 未生成 Markdown 或生成空 Markdown。
- 重复解析更新原 `parse_result`，保持幂等。
- 无附件解析请求。
- 解析完成后能够基于附件正文回答。

### 7.6 文档入库

- 菜谱文档完成解析、主题校验、切片、embedding 和存储。
- 已解析文档不重复调用 MinerU。
- 未解析文档自动先解析。
- 商业报告、简历和低置信混合内容拒绝入库。
- 主题校验模型异常时 fail closed，并允许重试。
- 解析失败、正文缺失和索引失败。
- `index_document()` 返回零片段时不得标记成功。
- 无默认知识库和无附件。
- 多附件全部成功和部分失败。
- 索引失败和校验失败后的重试。
- 重新校验为无关内容时删除已入库片段。
- 指定知识库重试。
- 入库后立即检索命中新文档。
- 入库后基于新文档问答并引用。
- 跨会话附件不得被入库。

### 7.7 记忆和摘要

- 创建忌口、口味、厨具、健康目标和通用偏好。
- 结构化模型抽取成功和规则 fallback。
- 重复偏好不重复创建。
- 显式更新已有偏好并保存更新历史。
- 无明确偏好时不写入长期记忆。
- 后续回答使用长期记忆。
- 当前输入与长期记忆冲突时以当前输入为准。
- 会话摘要达到阈值后生成。
- 摘要增量更新、游标丢失 fallback 和最大长度限制。
- 摘要或记忆副作用失败不影响主回答。

### 7.8 模型 fallback、流式和持久化

- 主模型成功。
- 主模型失败后备用模型成功。
- 主模型空回答后备用模型成功。
- 所有候选失败后使用本地 fallback。
- 流式回答成功和引用后缀输出。
- 流式开始输出后失败，不应切换模型拼接另一回答。
- `agent_run` 从 pending 到 running 再到 completed。
- hard failure 时记录 failed。
- 输入、输出快照和助手消息元数据一致。
- 使用量、provider、模型和 fallback 尝试被记录。
- 非关键摘要和记忆更新失败不影响主回答。

### 7.9 安全边界

- 附件或网页中的提示注入不得改变系统行为。
- 不得伪造知识库来源或网页链接。
- 跨用户和跨会话附件操作被拒绝。
- 无附件时不得触发附件副作用。
- 非烹饪附件不得进入知识库。
- 明确证据请求无证据时拒绝强答。
- 危险食品安全建议、过敏冲突和不安全储存建议由 LLM Judge 评分。

## 8. 评测器

### 8.1 确定性评分器

- `intent_match`
- `workflow_match`
- `run_status_match`
- `tool_policy_match`
- `source_hit`
- `citation_validity`
- `upload_outcome_match`
- `parse_outcome_match`
- `validation_outcome_match`
- `embedding_outcome_match`
- `attachment_ownership_enforced`
- `memory_mutation_match`
- `fallback_behavior_match`
- `persistence_consistency`
- `latency_budget`
- `cost_budget`

### 8.2 RAGAS

继续复用：

- `faithfulness`
- `context_precision`
- `context_recall`
- `response_relevancy`
- `answer_correctness`
- 项目自算的 `hit_at_k`、`recall_at_k` 和 `MRR`

### 8.3 LLM-as-judge

- `task_adherence`
- `groundedness`
- `completeness`
- `helpfulness`
- `memory_compliance`
- `attachment_answer_correctness`
- `citation_honesty`
- `safety`

Judge 使用与生产 Agent 分离的固定模型和温度。低分必须保存评分理由。

## 9. 运行配置和版本元数据

每个 Experiment 至少记录：

- `git_sha`
- `dataset_name`
- `dataset_version`
- `suite_filter`
- `runner_version`
- `prompt_version`
- `agent_model_provider`
- `agent_model_name`
- `judge_model_name`
- `knowledge_base_version`
- `milvus_collection`
- `mock_profile`
- `started_at`

建议数据集：

- `cooking-agent-offline-smoke-v1`
- `cooking-agent-offline-full-v1`

Smoke 数据集不是独立复制数据，而是通过 `metadata.smoke=true` 从完整数据集中筛选。

## 10. 当前已知缺口

下列问题应对应 `known_gap=true` Case：

1. `AgentContextProvider` 未填充 `attachment_context`，解析完成后的附件问答可能无法读取正文。
2. `DocumentIngestWorkflow` 在索引返回零片段时仍可能标记入库成功。
3. 项目 `output_snapshot` 只保存工具调用数量，不保存工具名称、参数和结果；工具策略需依赖 LangSmith Trace。
4. `CitationValidator` 对知识库来源有后置校验，但未对网页链接执行同等强度校验。
5. 工作流根据附件 ID 加载附件时没有在工作流内部再次校验所属会话。
6. 配置 MCP 后，本地 RAG、Web、天气工具与 MCP 工具可能同时存在并产生命名或行为冲突。
7. 文件上传只按扩展名分类，尚未验证真实 MIME 或文件签名。

## 11. 验收标准

首阶段完成条件：

- 三个 Target Runner 可以运行。
- 完整数据集覆盖矩阵中的每个功能和主要失败分支至少有一条 Case。
- 约 40 条 Smoke Case 可稳定重复运行。
- 现有 30 条 RAGAS Case 被同步或映射到 LangSmith Dataset。
- 附件上传、解析、入库、检索、问答端到端 Case 可以运行。
- 规则评分、RAGAS 和 LLM Judge 结果可以在同一 Experiment 中查看。
- Experiment 保存版本元数据，并可与上一基线对比。
- `known_gap` Case 能稳定暴露当前缺口。

## 12. 后续阶段

本设计完成后，下一阶段编写实施计划，按以下顺序落地：

1. 建立数据 Schema、资产目录和 LangSmith Dataset 同步工具。
2. 实现 `agent_turn` Runner 和规则评分器。
3. 实现 `attachment_pipeline` Runner 和附件端到端 Case。
4. 实现 `service_flow` Runner 和故障注入 Case。
5. 接入现有 RAGAS 和 LLM-as-judge。
6. 生成 Smoke/Full Experiment 命令、报告和基线对比。
