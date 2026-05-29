# RAG TODO List

本文件记录当前 RAG 链路相对完整优化图谱的实现状态。后续每完成一项优化，需要同步更新状态、实现文件和测试结果。

## 状态说明

- 已完成：代码已有稳定实现，并已有相关测试或可验证路径。
- 部分实现：已有基础能力，但距离优化目标仍有关键缺口。
- 未完成：当前代码尚未实现该优化能力。
- 待完成：建议后续按优先级推进的具体动作。

## P0：优先保证回答质量和正确性

| 环节 | 状态 | 当前实现 | 待完成实现 |
| --- | --- | --- | --- |
| 排序 rerank | 已完成 | `RerankClient` 支持本地 FlagEmbedding 和 API rerank；`RagRetriever` 在向量召回后按 rerank 分数重排，并保留 `vector_score`、`rerank_score`。 | 增加 rerank 前后 Top-K 命中率对比评估。 |
| Query 改写 | 已完成 | `QueryRewriter` 结合最近对话，把当前问题改写成独立检索查询；失败时回退原问题。 | 增加改写质量测试集，覆盖多轮省略、指代、约束条件保留。 |
| 上下文引用 | 已完成 | `render_retrieved_chunks` 输出文档、块号、分数、来源路径、章节路径、文件格式；snapshot 也保留这些字段。 | 前端展示引用时可进一步显示章节路径和来源文件。 |
| 生成约束 | 已完成 | system prompt 约束回答来源；`CitationValidator` 在 RAG hit 后附加由真实 chunk 生成的核验来源清单。 | 继续优化引用在前端的结构化展示。 |
| 幻觉控制 | 部分实现 | `CitationValidator` 对明确要求依据资料但无命中的请求直接拒答，并修正无命中情况下的虚假知识库来源声明。 | 增加答案与 retrieved chunk 的语义一致性检查。 |
| 检索 hybrid search | 已完成 | 向量召回之外新增 BM25 关键词召回，`RagRetriever` 使用 RRF 融合双路排名后继续执行 rerank。 | 用 Recall@K/MRR 报告调优融合参数；数据规模增大后替换扫描式关键词通道为专用倒排索引。 |
| 评估 Recall/MRR | 已完成 | `evaluate_rag_with_ragas.py` 读取样例期望来源，基于实际 chunk 排名计算 Hit@K、Recall@K、MRR，并输出独立检索报告。 | 扩充评测集并建立质量阈值。 |

## P1：提升召回覆盖和上下文质量

| 环节 | 状态 | 当前实现 | 待完成实现 |
| --- | --- | --- | --- |
| 数据多格式接入 | 已完成 | `document_loader` 支持 `.md`、`.markdown`、`.txt`、`.json`、`.jsonl`、`.csv`，结构化菜谱会渲染成统一 Markdown 文本。 | 支持更多真实来源，如网页导出、Excel 菜谱表、解析后的 PDF 结构化字段。 |
| 数据元数据 | 已完成 | 入库保留 `source_path`、`category`、`file_name`、`document_format`、`source_record_index` 等元数据。 | 规范菜系、难度、耗时、厨具、忌口等字段，形成可过滤 schema。 |
| 数据清洗 | 部分实现 | `TextChunker` 已做换行、空白、超长段落处理；结构化 loader 会过滤空记录。 | 增加文档去重、低质量内容过滤、乱码检测、图片占位和无效表格清理。 |
| 切分策略 | 已完成 | 支持 `target_size`、`max_size`、`overlap_size`，按段落、中文标点和硬切分组合处理。 | 针对表格、配料表、步骤列表增加专门切分策略，避免配料和步骤被拆散。 |
| 章节结构保留 | 已完成 | 切分时追踪 Markdown 标题栈，chunk metadata 写入 `section_title`、`heading_path`、`heading_paths`。 | 对 JSON/CSV 原始字段保留字段级 section 来源。 |
| 召回过滤 | 部分实现 | Milvus 检索支持 `knowledge_base_public_id` 过滤和 `min_score` 阈值。 | 增加分类、格式、时间、用户权限、附件归属等 metadata filter。 |
| 上下文去重 | 已完成 | `RagRetriever._dedupe_candidates` 在 rerank 前按 chunk id、文档 chunk 或内容 hash 去重，并保留高分候选。 | 增加跨文档近重复检测，避免同一道菜多个版本占满上下文。 |
| 上下文压缩 | 未完成 | 当前只用 final top-k 控制数量。 | 增加长 chunk 摘要压缩、句子级裁剪、按问题相关片段抽取。 |
| 多查询扩展 | 未完成 | 当前只有单次 query rewrite。 | 增加多查询生成，例如菜名、食材、做法、替代方案分别召回后融合。 |

## P2：提升性能、成本和可运维性

| 环节 | 状态 | 当前实现 | 待完成实现 |
| --- | --- | --- | --- |
| 检索缓存 | 已完成 | `RagRetriever` 使用 Redis JSON 缓存检索结果；缓存键包含 query、知识库、top-k、阈值、collection、embedding/rerank 配置。 | 增加缓存命中率日志和管理接口。 |
| 文档 embedding 批处理 | 已完成 | `EmbeddingClient.embed_documents` 支持批量生成文档 chunk embedding。 | 增加批大小配置，避免大批量索引时内存峰值过高。 |
| embedding 缓存 | 未完成 | 当前每次重建会重新 embedding。 | 按 chunk 内容 hash 缓存 embedding，内容未变时复用。 |
| 异步索引 | 未完成 | 当前索引脚本同步执行。 | 引入后台任务或 worker，支持索引进度、失败重试、取消和任务日志。 |
| 成本路由 | 部分实现 | 支持本地 embedding/rerank，评估脚本支持低并发和 batch size。 | 明确小模型负责 query rewrite/分类，大模型负责最终生成；记录每轮 token 和模型成本。 |
| 可观测性 | 部分实现 | RAG context snapshot 记录状态、query、rewritten_query、chunk_count、chunk metadata。 | 增加检索耗时、embedding 耗时、rerank 耗时、miss 率、top-k 分布指标。 |

## P3：中长期增强

| 环节 | 状态 | 当前实现 | 待完成实现 |
| --- | --- | --- | --- |
| 领域 embedding 微调 | 未完成 | 当前通过配置切换 embedding 模型。 | 准备菜谱问答/正负样本，评估是否需要微调或蒸馏 embedding。 |
| 图谱或结构化检索 | 未完成 | 当前以 chunk 为基本检索单位。 | 构建菜名、食材、厨具、做法、替代关系图，用于复杂组合查询。 |
| 索引版本治理 | 未完成 | 当前支持 rebuild collection。 | 增加 collection version、回滚、灰度重建、索引元信息记录。 |
| 自动评测门禁 | 部分实现 | 已有 RAGAS 脚本和样例集。 | 在 CI 或发布流程中加入评测阈值，低于阈值阻止合并或发布。 |

## 建议执行顺序

1. P0：增加答案与 retrieved chunk 的语义一致性检查。
2. P1：补充 metadata filter，先覆盖分类、格式、用户/附件归属。
3. P1：实现上下文压缩和多查询扩展。
4. P2：增加 embedding 缓存和异步索引任务。
5. P2：补充 RAG 可观测指标和成本统计。

## 最近验证基线

- 2026-05-25：检索评估增加 Hit@K、Recall@K、MRR 及独立报告输出。
- 2026-05-25：检索链路增加 BM25 关键词召回和 RRF 混合融合。
- 2026-05-25：回答工作流增加已核验引用附加和显式无证据拒答。
- `conda run -n cook-agent python -m pytest backend/src/tests/test_rag_module.py -q`：16 通过 / 0 失败。
- `conda run -n cook-agent python -m pytest backend/src/tests/test_ragas_eval_script.py -q`：12 通过 / 0 失败。
- `conda run -n cook-agent python -m pytest backend/src/tests/test_langchain_agent_runtime.py -q`：36 通过 / 0 失败。
- `conda run -n cook-agent python -m pytest backend/src/tests/test_rag_module.py backend/src/tests/test_ragas_eval_script.py backend/src/tests/test_langchain_agent_runtime.py -q`：64 通过 / 0 失败。
- `conda run -n cook-agent python -m pytest backend/src/tests -q`：79 通过 / 0 失败。
