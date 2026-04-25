# 智能体设计方案

## 1. 目标

当前阶段先实现一个**最小可用智能体（MVP Agent）**，目标不是做复杂推理，而是先让用户在发送消息后，系统能够稳定返回一条助手回复。

第一阶段重点解决的是：

- 用户发送一条消息后，后端能生成一条 `assistant` 角色消息
- 回复链路完整可跑通
- 运行过程能记录到 `agent_runs`
- 后续可以平滑扩展成真正的 LLM Agent、工具调用 Agent、多模态 Agent

也就是说，第一阶段先做“**可用**”，后续再做“**智能**”。

---

## 2. MVP 范围

本轮智能体只做以下事情：

- 接收用户文本消息
- 读取当前会话最近几条上下文
- 根据简单规则生成一条文本回复
- 将回复保存为一条 `assistant` 消息
- 记录一次 `agent_run`

本轮**暂不实现**：

- 大模型调用
- 工具调用
- 文件理解
- 图片理解
- 多意图识别
- 复杂工作流编排
- 流式输出

---

## 3. 设计原则

### 3.1 先跑通主链路

先让“用户发消息 -> 系统回消息”这条链路闭环，再逐步替换内部实现。

### 3.2 接口稳定，内部可替换

对外尽量统一成一个 `agent chat` 入口；
内部先用简单规则引擎，后续再替换为大模型推理，不影响前端调用方式。

### 3.3 记录运行痕迹

即使第一版很简单，也要把：

- 输入内容
- 回复内容
- 运行状态
- 错误信息

记录到 `agent_runs`，方便后续调试和演进。

### 3.4 与现有数据模型对齐

当前仓库已经有：

- `messages` 表：保存用户消息和助手消息
- `agent_runs` 表：保存一次智能体执行记录

所以第一版智能体设计应直接复用这两张表，而不是重新造一套记录机制。

---

## 4. 总体架构

建议第一版智能体采用下面这层结构：

```text
API Endpoint
    ->
AgentService
    ->
AgentOrchestrator
    ->
SimpleChatAgent
    ->
Assistant Message + AgentRun
```

各层职责如下：

### 4.1 API Endpoint

负责：

- 接收前端请求
- 校验参数
- 调用 `AgentService`
- 返回最终响应

建议新增接口：

`POST /api/v1/agent/chat`

### 4.2 AgentService

负责：

- 创建用户消息
- 触发智能体执行
- 保存助手消息
- 统一组织返回结构

它是“业务编排层”，不直接做回复生成。

### 4.3 AgentOrchestrator

负责：

- 加载会话上下文
- 识别当前走哪个工作流
- 调用具体 Agent
- 组织 `agent_run` 的生命周期

第一版只接一个 `SimpleChatAgent`；
后续可以扩展成：

- `RecipeAgent`
- `DocumentQaAgent`
- `ImageQaAgent`

### 4.4 SimpleChatAgent

负责：

- 输入：用户消息 + 最近上下文
- 输出：一条助手回复文本

第一版先不追求复杂智能，可以采用“规则模板回复”方式。

---

## 5. 目录设计

建议把 `backend/agent` 目录整理成下面这样：

```text
backend/agent/
  agent.md
  base_agent.py
  orchestrator.py
  context_builder.py
  simple_chat_agent.py
  prompts.py
```

### 各文件职责

#### `base_agent.py`

定义统一的 Agent 抽象基类，例如：

- `name`
- `intent_type`
- `run(context) -> AgentResult`

#### `orchestrator.py`

负责路由和调用具体 Agent。

#### `context_builder.py`

负责从数据库中读取最近几条消息，构建给 Agent 的上下文对象。

#### `simple_chat_agent.py`

第一版真正执行回复逻辑的 Agent。

#### `prompts.py`

后续如果接大模型，这里可以放系统提示词。
第一版可以先保留空文件或简单常量。

---

## 6. 第一版智能体行为设计

第一版 `SimpleChatAgent` 不依赖大模型，采用简单规则生成回复。

### 6.1 输入

- 当前用户消息
- 最近 N 条历史消息
- 会话 ID
- 用户 ID

### 6.2 输出

- 一条助手文本消息
- 一个简单结构化结果 `AgentResult`

建议结果对象包含：

```json
{
  "reply_text": "你好，我已经收到你的问题。接下来我可以继续帮你分析做法、食材或文档内容。",
  "intent_type": "simple_chat",
  "workflow_name": "simple_chat_workflow",
  "model_name": null,
  "output_snapshot": {
    "reply_type": "text"
  }
}
```

### 6.3 回复策略

建议先做 3 类规则：

#### 规则 1：问候类

如果用户消息包含：

- 你好
- hi
- hello
- 在吗

返回问候模板。

#### 规则 2：空泛需求类

如果用户消息较短、信息不足，例如：

- 帮我做菜
- 推荐一下
- 怎么办

返回引导模板，让用户补充：

- 食材
- 人数
- 时间
- 口味

#### 规则 3：默认兜底类

如果不命中规则，则返回通用确认模板：

- 已收到你的问题
- 当前系统已具备基础回复能力
- 后续会补充更强的分析与生成能力

这样即使没有 LLM，系统也能始终给用户一个稳定答复。

---

## 7. 请求处理流程

建议第一版完整流程如下：

1. 前端调用 `POST /api/v1/agent/chat`
2. 后端创建一条用户消息 `role=user`
3. 创建一条 `agent_run`，状态为 `pending`
4. `AgentOrchestrator` 读取最近上下文
5. 路由到 `SimpleChatAgent`
6. `SimpleChatAgent` 生成回复文本
7. 后端写入一条助手消息 `role=assistant`
8. 更新 `agent_run` 为 `completed`
9. 返回用户消息和助手消息

---

## 8. 数据落库设计

### 8.1 用户消息

继续复用现有 `messages` 表：

- `role = user`
- `content = 用户输入文本`

### 8.2 助手消息

也复用现有 `messages` 表：

- `role = assistant`
- `content = Agent 生成的文本回复`

### 8.3 Agent 运行记录

复用现有 `agent_runs` 表，建议写入：

- `intent_type = simple_chat`
- `workflow_name = simple_chat_workflow`
- `run_status = pending/running/completed/failed`
- `input_snapshot = 当前消息 + 上下文摘要`
- `output_snapshot = 回复文本 + 回复类型`
- `model_name = null`

---

## 9. 返回结构建议

第一版接口建议返回：

```json
{
  "message": "智能体回复成功",
  "data": {
    "user_message": {},
    "assistant_message": {},
    "agent_run": {
      "intent_type": "simple_chat",
      "workflow_name": "simple_chat_workflow",
      "run_status": "completed"
    }
  }
}
```

这样前端可以直接把用户消息和助手消息都渲染出来。

---

## 10. 错误处理

如果智能体执行失败：

- 用户消息可以保留
- `agent_run` 标记为 `failed`
- 写入 `error_code` 和 `error_message`
- 助手消息可选：
  - 不写入
  - 或写入一条统一兜底回复

建议第一版直接写入统一兜底回复，保证用户总能看到系统反馈，例如：

`"我已经收到你的消息，但当前处理过程中出现异常，请稍后再试。"`

---

## 11. 后续扩展路线

当第一版跑通后，可以按下面顺序扩展：

### 阶段 2：接入 LLM

将 `SimpleChatAgent` 内部从规则回复替换为：

- 本地模型
- OpenAI-compatible 模型
- 其他聊天模型

### 阶段 3：加入意图识别

在 `AgentOrchestrator` 中增加：

- `simple_chat`
- `recipe_generation`
- `document_qa`
- `image_qa`

### 阶段 4：加入工具调用

例如：

- 文件解析器
- OCR
- 食谱格式化器
- 检索服务

### 阶段 5：加入流式输出

让助手回复支持 SSE 或 WebSocket 流式返回。

---

## 12. 推荐的第一步实现顺序

建议按下面顺序开发：

1. 完善 `base_agent.py`
2. 新增 `simple_chat_agent.py`
3. 新增 `orchestrator.py`
4. 新增 `context_builder.py`
5. 新增 `agent_service.py`
6. 新增 `api/v1/endpoints/agent.py`
7. 跑通“创建用户消息 -> 生成助手消息 -> 写入 agent_run”

---

## 13. 当前建议结论

当前最合适的方案是：

- **第一版智能体先不用大模型**
- **先用规则模板方式保证系统可回复**
- **统一走 `agent/chat` 入口**
- **所有回复都落到 `messages` 表**
- **所有执行过程都记录到 `agent_runs` 表**

这样做的好处是：

- 实现成本低
- 调试简单
- 很快能让前端看到系统回复
- 后续替换成真正的 AI Agent 时改动成本也小

---

## 14. 下一步

基于本方案，下一步可以开始实现：

- `base_agent.py`
- `simple_chat_agent.py`
- `orchestrator.py`
- `agent_service.py`
- `api/v1/endpoints/agent.py`

先把最小回复链路做通。
