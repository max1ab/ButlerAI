# Butler Spec（控制面 / Orchestrator）

## 1. 职责边界

Butler 负责“理解与编排”，不负责“具体执行”。

- **对接用户**：对话/CLI/HTTP（实现形态可变，接口语义不变）
- **意图识别**：NL → Intent（含实体抽取、约束、置信度、澄清问题）
- **规划与拆解**：Intent → Plan（Task 序列或 DAG）
- **Runner 管理**：注册、能力发现、心跳、健康状态
- **调度派发**：为 Task 选择合适 Runner；控制优先级、并发、超时回收
- **状态与审计**：任务状态机驱动的事件流，聚合日志与产物
- **安全决策**：按 Policy 决定需要确认/拒绝/降级执行

不在 Butler 做的事：

- 直接调用系统命令/工具（交给 Runner）
- 具体 Agent 的 prompt 工程与工具调用细节（Runner 可封装）

## 2. 核心组件（概念）

- **User Interface Adapter**：把用户输入统一为 `raw_text + context`
- **Intent Resolver**：输出 `Intent`
- **Planner**：输出 `Plan`（Task 列表或 DAG）
- **Policy Engine**：对 Plan/Task 做风险评估与拦截（确认闸）
- **Scheduler**：Task → Runner 匹配与队列管理
- **Task Store**：任务、事件、产物的存储抽象（MVP 可内存）
- **Runner Registry**：Runner 注册信息与在线状态

## 3. Runner 管理

### 3.1 Runner 注册

最小字段：

- `name`
- `type`：`local|remote|container|agent`
- `capabilities`：如 `shell`, `git`, `docker`, `http`, `agent:code`
- `metadata`：OS、CPU、工作目录、安全级别等

### 3.2 心跳与健康

- Runner 定期上报：`status`、队列长度、并发占用、错误率等
- Butler 将 Runner 标记为：`online|offline|degraded`
- 调度时对 degraded Runner 降权或剔除

## 4. 调度（Task → Runner）

匹配维度：

- **capability 匹配**：满足 `task.required_capabilities`
- **安全等级匹配**：Runner 权限/沙箱满足 `task.policy`
- **负载与并发**：选择最低负载或最短队列
- **亲和性**：同项目/目录尽量在同 Runner（减少上下文切换）
- **失败回避**：近期失败率高的 Runner 降权

MVP 策略：

- capability 过滤 + 最低负载优先 + 超时回收

## 5. 任务状态与事件驱动

Butler 必须以 Task 状态机为中心管理生命周期：

- 创建、入队、分配、执行中、等待确认、完成/失败/取消
- 所有状态变更与关键执行信息都以 **Event** 写入任务时间线

对外（面向用户）展示：

- Task timeline（状态变更 + 关键事件）
- 日志聚合（结构化 + 可读摘要）

## 6. 安全与确认闸（Policy）

默认建议：

- 破坏性操作（删除、覆盖、`rm -rf`、系统配置修改）触发 `waiting_confirmation`
- 支持命令白/黑名单（可配置）
- 默认最小权限：不同 Runner 可声明读写/网络权限

Butler 侧输出：

- `request_confirmation(reason, proposed_actions)` 事件
- 用户确认/拒绝后，继续执行或取消

## 7. 接口契约（建议 HTTP/JSON 语义）

建议 MVP 采用 Runner **拉取模式**（pull），降低网络复杂度。

- `POST /runners/register`
- `POST /runners/heartbeat`
- `POST /runners/{runner_id}/tasks/pull`
- `POST /tasks/{task_id}/events`
- `POST /tasks/{task_id}/complete`
- `POST /tasks/{task_id}/confirm`

## 8. MVP 交付清单（Butler）

- Runner 注册/心跳 + Registry
- Task 队列 + Scheduler（pull 分发）
- Task 状态机 + 事件时间线
- Policy 确认闸（命中策略进入 waiting_confirmation）
- 最小 UI（CLI 或 HTTP）用于提交请求与查看任务

