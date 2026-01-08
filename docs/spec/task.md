# Task Spec（任务模型 / 状态机 / 执行语义）

## 1. Task 的定位

Task 是 Butler 与 Runner 之间的**执行契约**：描述“要做什么、以什么约束做、如何回传结果”。

原则：

- **结构化优先**：inputs/result 尽量 JSON 化，便于复用与自动化
- **可追踪**：状态机 + 事件时间线
- **可控**：policy 驱动的确认闸与禁止规则

## 2. Intent（输入侧，供 Butler 使用）

Intent 用于从自然语言稳定生成计划与 Task：

- `id`
- `raw_text`
- `type`：`file_ops|dev_ops|code_agent|info_summarize|...`
- `entities`：路径、仓库、分支、关键词、目标环境等
- `constraints`：风险等级、是否需要确认、输出格式等
- `confidence`：0-1
- `clarification_questions`：不确定时给出需要澄清的问题

## 3. Task 字段（概念模型）

最低建议字段：

- `id`
- `title`
- `intent_id`
- `description`
- `inputs`：JSON
- `required_capabilities`：如 `shell`, `git`, `docker`, `http`, `agent:code`
- `policy`：
  - `risk_level`: `low|medium|high`
  - `requires_confirmation`: boolean（或由规则推导）
  - `deny_patterns` / `allow_patterns`（可选）
- `priority`：`low|normal|high`
- `timeout_ms`
- `retries`：次数 + 退避策略
- `state`
- `assigned_runner_id`
- `artifacts`
- `result`：JSON + 摘要

## 4. Task 状态机

建议状态：

- `created`：已创建，未调度
- `queued`：等待调度/资源
- `assigned`：已分配 Runner
- `running`：执行中
- `waiting_confirmation`：需要用户确认
- `succeeded`：成功
- `failed`：失败
- `cancelled`：取消

状态流规则（要点）：

- `waiting_confirmation` 只能由 policy 触发
- 用户拒绝确认 → `cancelled`
- 可重试失败 → Butler 可将 Task 回退到 `queued` 并递增 attempt

## 5. 重试与幂等性

- Runner 对失败应分类：`retryable` / `non_retryable` / `needs_confirmation`
- Butler 依据策略重试：
  - 网络/临时错误可自动重试
  - 破坏性操作默认不自动重试
- Task inputs 尽量包含幂等键（例如目标路径、预期状态），避免重复执行造成破坏

## 6. 事件与日志（Execution Event）

事件最小字段：

- `timestamp`
- `task_id`
- `runner_id`
- `level`: `info|warn|error`
- `message`
- `data`: JSON（命令、退出码、耗时、token 使用等）

要求：

- Runner 执行过程持续回传事件
- Butler 负责聚合并形成“任务时间线”

## 7. 产物（Artifacts）与结果（Result）

- **artifacts**：文件路径/链接/摘要（由 Runner 产生或 Butler 生成）
- **result**：结构化 JSON（便于后续自动化）+ 人类可读摘要（便于 UI 展示）

## 8. 最小接口语义（与 Butler/Runner 对齐）

- Runner 拉取任务：`POST /runners/{runner_id}/tasks/pull`
- 事件回传：`POST /tasks/{task_id}/events`
- 完成回传：`POST /tasks/{task_id}/complete`
- 确认：`POST /tasks/{task_id}/confirm`

## 9. Task 示例（概念）

### 9.1 Shell 执行类

- `required_capabilities: ["shell"]`
- `inputs`: `{ "cwd": "...", "command": "...", "env": {...} }`

### 9.2 Agent 子任务类

- `required_capabilities: ["agent:generic"]`
- `inputs`: `{ "prompt": "...", "context_refs": [...] }`

