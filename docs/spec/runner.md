# Runner Spec（数据面 / 执行器）

## 1. 职责边界

Runner 负责“执行与回传”，不负责“全局编排与对话”。

- 接收 Task（通常来自 Butler 的队列/派发）
- 将 Task 解析为具体 action（命令、API 调用、agent 子任务等）
- 执行并回传：stdout/stderr、结构化事件、产物、错误分类
- 提供资源隔离：超时、并发上限、沙箱/权限边界（按 Runner 类型）
- 对外声明能力：capabilities + 安全/权限特征

## 2. Runner 类型（概念）

- **local**：在用户机器上执行（shell、文件、git、docker 等）
- **remote**：远程主机/服务执行（SSH/API）
- **container**：在容器中执行（更强隔离）
- **agent**：对接外部 AI Agent（工具调用封装在 Runner 内）

MVP 推荐先实现 `local`（shell）Runner。

## 3. Capabilities（能力契约）

Runner 必须上报：

- **capabilities**：例如
  - `shell`：受控命令执行
  - `git`：git 操作（可选）
  - `docker`：docker 操作（可选）
  - `http`：HTTP 调用（可选）
  - `agent:generic` / `agent:code`：对接特定 agent（可选）
- **metadata**：OS、架构、工作目录、资源上限
- **security**：权限特征（只读/读写/网络访问、是否沙箱等）

capability 是 Butler 调度与安全决策的主要输入。

## 4. 执行模型

### 4.1 拉取模式（MVP）

Runner 主动调用：

- `POST /runners/{runner_id}/tasks/pull { max_tasks }`

拿到任务后：

- 发送 `events`（进度/日志/状态变更）
- 最终 `complete`（成功/失败/取消）

### 4.2 并发与资源限制

Runner 需要支持：

- 每 Runner 最大并发（例如 1~N）
- 每 Task 超时（`task.timeout_ms`）
- 输出大小限制（防止日志爆炸）

## 5. 安全要求（MVP 必备）

Runner 侧必须二次校验 policy（防止 Butler 误判）：

- 若 action 命中禁止规则：拒绝执行并回传可解释错误
- 若需要确认但未确认：暂停执行并回传 `waiting_confirmation` 事件（或拒绝）
- 对 `shell` 执行做最小化防护：
  - 明确工作目录
  - 禁止或强制确认高危命令模式（可配置）
  - 限制环境变量/可访问路径（能力允许时）

## 6. 回传与事件

Runner 需要持续上报：

- `log`：stdout/stderr（可截断）+ 结构化字段（exit code、耗时）
- `progress`：可选（百分比/阶段）
- `error`：分类（可重试/不可重试/需要确认/权限不足等）

最终回传：

- `status`: `succeeded|failed|cancelled`
- `result`: 结构化 JSON + 人类可读摘要
- `artifacts`: 文件路径/链接/摘要（由 Butler 统一展示）

## 7. MVP 交付清单（Runner）

- 注册/心跳
- 拉取任务
- 执行 `shell` action（超时、退出码、stdout/stderr 回传）
- 失败分类与可重试标记
- policy 基础校验（至少对明显危险命令拒绝或请求确认）

