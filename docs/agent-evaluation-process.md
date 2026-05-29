# CookingAgent 智能体评测流程设计

评估日期：2026-05-28  
评估对象：当前代码库、RAGAS 评测脚本、Agent 运行链路、测试与架构文档  
结论：项目已经有 RAG 质量评测雏形，但还没有完整的智能体评测流程。

## 1. 当前已有评测资产

### 1.1 RAGAS 离线评测

当前仓库已经包含一条面向 RAG 问答的离线评测链路：

- 评测样例：`backend/eval/ragas_cases.jsonl`，当前为 30 条中文菜谱问答样例。
- 评测脚本：`backend/scripts/evaluate_rag_with_ragas.py`。
- 评测输出：`backend/eval/ragas_results/` 下已有 `samples_*`、`scores_*`、`retrieval_metrics_*`。
- 评测指标：RAGAS 的 `faithfulness`、`context_precision`、`context_recall`、`response_relevancy`、`answer_correctness`，以及项目自算的 `hit_at_k`、`recall_at_k`、`reciprocal_rank`。
- 脚本实现方式：复用项目自己的 `RagContextBuilder` 与 `LangChainAgentRunner`，不是单独拼一个外部 RAG demo，这一点是好的。

### 1.2 Agent 单元与集成测试

当前测试已经覆盖部分 Agent 行为边界：

- `backend/src/tests/test_langchain_agent_runtime.py`：系统提示词、RAG 上下文、Web 搜索上下文、工具装配、模型 fallback、空响应处理等。
- `backend/src/tests/test_agent_workflows.py`：附件解析、文档入库、记忆更新、会话摘要等非回答工作流。
- `backend/src/tests/test_ragas_eval_script.py`：RAGAS 样例加载、指标汇总、评测模型与 embedding 适配等。

这些测试更接近工程正确性测试，还不是完整的智能体质量评测。

### 1.3 运行快照基础

项目已有 `agent_runs` 表，保存每轮 Agent 的 `input_snapshot`、`output_snapshot`、状态、模型名、错误与耗时。`AgentService` 会把近期消息、长期记忆、附件、知识库 ID、请求选项等输入快照落库，也会把回答、意图、工作流、工具与降级信息写入输出快照。

这为离线回放、线上抽样评测和故障归因打下了基础。

## 2. 当前缺口

当前流程只能说明“RAG 问答是否大体可靠”，不能系统回答“智能体是否稳定完成任务”。主要缺口如下：

- 缺少 Agent 级评测集：没有覆盖意图识别、工具选择、工具调用顺序、多轮记忆、附件解析、Web/天气工具、失败降级和安全边界的统一 case schema。
- 缺少轨迹评测：目前主要看最终回答和 RAG 上下文，没有对工具调用序列、工作流路由、是否误用工具、是否跳过必要证据做评分。
- 缺少发布门禁：没有 `.github` CI，也没有“低于阈值禁止合并/发布”的自动化质量门。
- 缺少线上持续评测：`agent_runs` 已记录数据，但没有抽样、脱敏、人工复审、回流到评测集的闭环。
- 缺少安全与鲁棒性评测：提示注入、越权数据访问、伪造来源、无证据强答、恶意附件、工具滥用等没有独立评测套件。
- 缺少版本对比：评测结果没有绑定 prompt 版本、模型版本、知识库版本、索引版本和代码提交。

## 3. 参考的大厂/主流做法

本流程参考以下公开实践，并抽象成适合本项目的轻量方案：

- OpenAI Agent evals：强调可复现评测、Datasets、Evals，以及 workflow/trace 级错误定位。参考：https://platform.openai.com/docs/guides/agent-evals
- OpenAI Evals API：将评测定义、数据源 schema、grader 和不同模型参数的运行结果分离。参考：https://platform.openai.com/docs/guides/evals
- Google ADK Evaluation：强调用 evalset 评估 agent，覆盖工具轨迹、响应质量和安全标准。参考：https://google.github.io/adk-docs/evaluate/
- Microsoft Foundry Agent Evaluators：将质量、安全、Agent 行为评估器组合使用，并同时评估最终结果与过程轨迹。参考：https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators
- LangChain AgentEvals/LangSmith：强调不只评最终答案，还要评消息与工具调用轨迹。参考：https://docs.langchain.com/oss/python/langchain/evals

可迁移到 CookingAgent 的核心原则：

- 固定数据集加版本化：每次 prompt、模型、知识库或工具变更都能复跑同一套 case。
- 最终答案和执行轨迹分开评分：答案正确不代表智能体行为正确。
- 规则评测和 LLM-as-judge 混合：能确定的用规则，主观质量再交给评审模型。
- 离线门禁和线上持续评测并行：上线前防回归，上线后发现真实分布里的新失败。
- 人工复审校准评审模型：高风险 case 和低置信 case 必须有人看。

## 4. 推荐评测分层

### 4.1 L0 工程正确性测试

目标：保证代码边界不坏。

继续运行现有测试：

```powershell
python -m pytest backend/src/tests
```

覆盖范围：

- Agent runtime、workflow、tool factory、RAG 模块。
- fallback、空响应、模型候选切换。
- 附件解析、文档入库、长期记忆、会话摘要。

门禁建议：

- PR 必跑。
- 失败即禁止合并。

### 4.2 L1 RAG 快速评测

目标：保证知识库问答和检索质量没有明显回退。

使用现有脚本作为基础：

```powershell
python backend/scripts/evaluate_rag_with_ragas.py --limit 10 --skip-evaluate
python backend/scripts/evaluate_rag_with_ragas.py --limit 30
```

建议门禁：

- 检索 `hit_at_k >= 0.90`。
- 检索 `mrr >= 0.75`。
- RAGAS 核心分数相对主分支下降不超过 3%。
- 出现“无来源伪造”“引用与回答冲突”时直接标为 P0。

### 4.3 L2 Agent 离线回放评测

目标：评估完整智能体行为，包括路由、工具、记忆、附件、回答和降级。

新增建议：

- 目录：`backend/eval/agent_cases/`
- 脚本：`backend/scripts/evaluate_agent_cases.py`
- 输出：`backend/eval/agent_results/`

建议 case schema：

```json
{
  "case_id": "rag_recipe_001",
  "suite": "cooking_rag",
  "risk_level": "P1",
  "messages": [
    {"role": "user", "content": "蛋炒饭为什么推荐使用隔夜冷饭？"}
  ],
  "setup": {
    "knowledge_base_ids": ["cookbook"],
    "user_memories": [],
    "attachments": [],
    "mock_tools": {
      "web_search": "disabled",
      "weather": "disabled"
    }
  },
  "expected": {
    "intent_type": "answer",
    "workflow_name": "answer_workflow",
    "required_source_paths": ["data/cook/dishes/staple/蛋炒饭.md"],
    "tool_policy": {
      "must_not_call": ["web_search"],
      "may_call": ["rag_search"]
    },
    "answer_rubric": [
      "说明隔夜饭水分少",
      "说明更容易粒粒分明",
      "给出现煮饭快速降温的替代方案"
    ],
    "forbidden_claims": [
      "声称必须冷冻一整晚"
    ]
  },
  "graders": ["deterministic", "ragas", "llm_judge"]
}
```

核心评测套件：

| 套件 | 目标 | 示例 |
| --- | --- | --- |
| `cooking_rag` | 本地知识库问答 | 菜谱步骤、用量、火候、注意事项 |
| `multi_turn_memory` | 多轮上下文和长期记忆 | “我不吃香菜”后续推荐避开香菜 |
| `attachment_ingest` | 附件解析和入库 | 用户上传菜谱并要求加入知识库 |
| `tool_weather_web` | 外部工具选择 | 需要天气时调用天气，不需要时不调用 |
| `evidence_refusal` | 无证据问题处理 | 明确要求“根据知识库”但检索为空时拒答 |
| `safety_prompt_injection` | 提示注入和工具边界 | 附件或网页要求忽略系统提示时拒绝执行 |
| `fallback_resilience` | 模型失败与降级 | 主模型失败后切换候选或本地兜底 |
| `cost_latency` | 成本和延迟 | token、工具次数、总耗时、首 token |

### 4.4 L3 发布候选评测

目标：在 staging 环境用真实依赖跑完整门禁。

建议流程：

1. 固定本次评测元数据：`git_sha`、`prompt_version`、`model_provider`、`model_name`、`knowledge_base_version`、`milvus_collection`。
2. 重建或锁定知识库索引。
3. 跑 L0、L1、L2 全量套件。
4. 与上一稳定版本做 diff：逐 case 比较最终回答、工具轨迹、引用来源、耗时与成本。
5. 生成 `summary.json`、`cases.jsonl`、`report.md`。
6. 达到阈值才允许发布。

建议发布阈值：

| 指标 | 阈值 |
| --- | ---: |
| L0 测试 | 100% 通过 |
| Agent deterministic pass rate | >= 95% |
| Agent LLM judge task success | >= 85% |
| RAG retrieval hit_at_k | >= 90% |
| 引用无效率 | <= 2% |
| P0 安全 case | 100% 通过 |
| 不必要 Web/天气工具调用率 | <= 5% |
| 模型全候选失败率 | <= 1% |
| Agent 总耗时 p95 | 以当前基线 +20% 为上限 |

### 4.5 L4 线上持续评测

目标：从真实流量发现离线 case 没覆盖的新问题。

建议使用 `agent_runs` 作为数据来源：

- 每日抽样：成功、失败、fallback、长耗时、高 token、用户重试、用户负反馈。
- 自动脱敏：去掉邮箱、手机号、密钥、地址、用户 ID、附件原文敏感片段。
- 自动预评：用规则和 LLM judge 标记低置信回答、无来源回答、工具异常轨迹。
- 人工复审：对 P0/P1、高争议、低置信样例做人工标注。
- 回流评测集：确认后的真实失败样例进入 `backend/eval/agent_cases/regression.jsonl`。

## 5. 评测器设计

### 5.1 规则评测器

优先用规则评估确定性事实：

- `intent_match`：实际 `intent_type` 是否等于期望。
- `workflow_match`：实际 `workflow_name` 是否等于期望。
- `tool_policy_match`：是否调用必需工具，是否调用禁用工具。
- `source_hit`：检索结果是否包含期望来源。
- `citation_validity`：回答中展示的来源是否来自实际 RAG/Web 结果。
- `fallback_behavior`：模型失败时是否按候选顺序 fallback。
- `schema_validity`：结构化输出是否符合 schema。
- `latency_budget`：总耗时、首 token、工具耗时是否超阈值。
- `cost_budget`：token、模型调用次数、外部工具次数是否超阈值。

### 5.2 LLM-as-judge 评测器

用于评估答案质量和开放式任务：

- `task_adherence`：是否完成用户任务。
- `groundedness`：回答是否被 RAG/Web/附件证据支持。
- `completeness`：是否覆盖关键步骤、用量、约束。
- `helpfulness`：表达是否可执行、清晰、符合中文做菜场景。
- `safety`：是否避免危险建议、伪造来源、越权记忆、泄露隐私。

评审模型建议与生产模型分离，并固定 temperature。低分样例必须保留 judge rationale，便于人工复核。

### 5.3 人工评测器

人工只看高价值样例：

- 新增功能首批 case。
- LLM judge 低置信或不同 judge 分歧 case。
- P0/P1 安全与证据 case。
- 线上用户负反馈样例。

标注字段建议：

- `human_score`: 1-5。
- `failure_category`: retrieval、reasoning、tool_use、memory、safety、latency、ux、other。
- `severity`: P0/P1/P2/P3。
- `expected_fix`: prompt、retrieval、tool、workflow、model、data、product。

## 6. 推荐运行节奏

| 时机 | 运行内容 | 目的 |
| --- | --- | --- |
| 本地开发 | L0 + L1 smoke | 快速发现代码和检索回退 |
| PR | L0 + L1 smoke + L2 smoke | 阻止明显 Agent 回归 |
| 合并到主分支 | L0 + L1 full + L2 full | 形成每日基线 |
| 发布候选 | L0-L3 全量 | 发布门禁 |
| 线上每日 | L4 抽样评测 | 发现真实分布问题 |
| 每周评审 | 失败聚类 + case 回流 | 让评测集持续变强 |

## 7. 落地路线

### 阶段一：补 Agent 评测骨架

- 新增 `backend/eval/agent_cases/smoke.jsonl`，先放 20-30 条高价值 case。
- 新增 `backend/scripts/evaluate_agent_cases.py`，复用 `AgentOrchestrator` 和现有 `AgentTurnContext`。
- 先实现规则评测器：意图、工作流、RAG 来源、工具禁用、fallback、耗时。
- 输出 `summary.json` 和 `report.md`。

### 阶段二：扩展质量评测

- 把现有 RAGAS 结果并入 Agent 报告。
- 增加 LLM-as-judge 评测器。
- 将 case 扩展到 100 条以上，覆盖 RAG、记忆、附件、工具、安全和失败降级。
- 为每个 case 标注 `risk_level` 和 `owner`。

### 阶段三：接入门禁

- 新增 GitHub Actions 或等效 CI。
- PR 跑 smoke，主分支 nightly 跑 full。
- 对比 `main` 最近稳定基线，输出新增失败、修复失败和分数变化。
- 低于阈值时阻止发布。

### 阶段四：线上闭环

- 基于 `agent_runs` 做每日抽样。
- 增加脱敏与人工复审队列。
- 将线上确认失败自动写入 regression 候选池，经人工确认后进入正式评测集。
- 做按模型、prompt、知识库版本的趋势图。

## 8. 建议优先级

P0：

- 建立 L2 Agent smoke 评测集和脚本。
- 把工具轨迹、工作流路由和引用来源纳入评分。
- 将“无证据强答、伪造来源、禁用工具被调用”设为硬失败。

P1：

- 接入 LLM-as-judge，覆盖答案完整性、忠实度、可执行性。
- 将 RAGAS 结果和 Agent 结果合并成一个发布报告。
- 增加 prompt/model/knowledge_base 版本元数据。

P2：

- 接入 CI 门禁。
- 建立线上抽样与人工复审。
- 建立趋势分析和失败聚类。

## 9. 当前判断

CookingAgent 现在的评测成熟度可以评为：

| 维度 | 成熟度 |
| --- | --- |
| 单元/集成测试 | 中等偏好 |
| RAG 离线评测 | 已有雏形 |
| Agent 轨迹评测 | 缺失 |
| 安全与鲁棒性评测 | 缺失 |
| 发布门禁 | 缺失 |
| 线上持续评测 | 缺失 |

因此，不需要从零开始，但要把“RAGAS 脚本”升级成“Agent 评测体系”。最合理的下一步不是继续堆更多评审指标，而是先补一条可跑、可复现、可 diff 的 Agent smoke 评测链路。
