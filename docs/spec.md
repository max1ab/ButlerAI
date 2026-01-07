# ButlerAI 规格说明（Spec）

## 1. 背景与目标

ButlerAI 是一个面向**技术爱好者**的 AI 管家系统，用于**识别用户意图**、**规划任务**、并将任务**派发给可执行单元**完成。系统架构分为两层：

- **Butler 层**：对接用户，理解需求，生成/拆解/编排任务，管理 Runner，追踪执行状态，呈现结果。
- **Runner 层**：对接系统能力或外部 Agent（本地工具、远程服务、LLM Agent、脚本等），执行 Butler 分配的 Task，并回传日志与结果。

核心目标：

- **意图识别准确**：将自然语言请求稳定映射为可执行任务或可澄清的问题。
- **任务可控可追踪**：每个 Task 有明确状态、输入输出、审计日志、错误与重试策略。
- **Runner 可扩展**：可插拔的执行后端，适配不同系统/Agent。
- **面向技术用户体验**：支持命令式、对话式、批处理；提供可观测性（日志/事件/trace）与可配置性。

非目标（初期不做）：

- 复杂的多租户 SaaS 计费系统
- 大规模企业级权限治理（先做单用户/小团队可用的最小安全边界）
- 全自动“无确认”执行敏感操作（默认需要确认/策略）

## 2. 目标用户与典型场景

目标用户：技术爱好者、开发者、DevOps、AI 工具玩家。

典型场景（MVP优先）：

- **本机任务**：整理下载目录、批量重命名、生成项目脚手架、执行脚本、管理 docker/进程。
- **开发协作**：根据描述创建 issue/PR 草稿，生成 release note，跑测试并汇总失败原因（对接 CI）。
- **信息整理**：将对话或日志摘要为 TODO、生成执行计划、输出可复制命令。
- **Agent 执行**：把子任务交给专用 agent（如代码审查 agent、文档 agent、搜索 agent）并汇总结果。

## 3. 术语定义

- **Intent（意图）**：用户请求的目标与约束的结构化表示。
- **Task（任务）**：可执行的工作单元，包含输入、步骤/计划、执行策略、状态与输出。
- **Runner**：执行 Task 的实体（本地/远程/容器/Agent），提供标准接口。
- **Capability**：Runner 能力声明（支持的工具、权限范围、资源限制）。
- **Policy**：执行策略与安全约束（需要确认的操作、禁止的操作等）。

## 4. 系统分层与职责边界

### 4.1 Butler（控制面 / Orchestrator）

职责：

- 用户交互：对话/CLI/HTTP（先定义抽象接口）
- 意图识别：NL → Intent（含实体抽取与约束）
- 规划与拆解：Intent → Plan（Task DAG 或序列）
- Runner 管理：注册/心跳/能力发现/健康检查
- 调度：把 Task 分派给合适 Runner；控制并发与优先级
- 状态与审计：任务状态机、日志聚合、结果归档
- 安全决策：按 Policy 进行“需要确认/拒绝/降级”

不做（放在 Runner）：

- 直接执行系统命令/工具调用
- 具体 agent prompt 工程（Butler只定义任务与接口，Runner可实现）

### 4.2 Runner（数据面 / 执行器）

职责：

- 接收 Task，解析为可执行动作（命令、API 调用、agent 任务、脚本等）
- 执行与回传：stdout/stderr、结构化日志、产物、错误
- 资源隔离：超时、并发、沙箱（可按 Runner 类型实现）
- 能力声明：可执行的工具集合、权限范围、平台信息

不做（放在 Butler）：

- 全局任务编排与跨 Runner 协调
- 用户对话与澄清策略

## 5. 关键对象与数据模型（概念）

### 5.1 Intent（结构化）

- **id**
- **raw_text**：原始用户请求
- **type**：如 `file_ops` / `dev_ops` / `code_agent` / `info_summarize`
- **entities**：路径、仓库、分支、关键词、目标环境等
- **constraints**：时间、风险等级、是否需要确认、输出格式
- **confidence**：0-1
- **clarification_questions**：如有不确定，列出需要问的点

### 5.2 Task

- **id**
- **title**
- **intent_id**
- **description**
- **inputs**：结构化输入（JSON）
- **steps**：可选（Butler生成的计划步骤）
- **required_capabilities**：如 `shell`, `git`, `docker`, `http`, `agent:code`
- **policy**：风险等级、是否需要确认、允许/禁止的命令模式等
- **priority**：`low|normal|high`
- **timeout_ms**
- **retries**：次数与退避策略
- **state**：见 6.1
- **assigned_runner_id**
- **artifacts**：输出文件/链接/摘要
- **result**：结构化结果（JSON）+ 人类可读摘要

### 5.3 Runner

- **id**
- **name**
- **type**：`local` / `remote` / `container` / `agent`
- **capabilities**：工具与权限声明
- **status**：`online|offline|degraded`
- **last_heartbeat_at**
- **metadata**：OS、CPU、可用内存、工作目录、安全级别等

### 5.4 Execution Log / Event

- **timestamp**
- **task_id**
- **runner_id**
- **level**：info/warn/error
- **message**
- **data**：结构化字段（命令、退出码、耗时、token使用等）

## 6. 状态机与执行语义

### 6.1 Task 状态机（建议）

- `created`：已创建，未调度
- `queued`：等待调度/等待资源
- `assigned`：已分配 Runner
- `running`：执行中
- `waiting_confirmation`：需要用户确认（例如危险命令）
- `succeeded`：成功完成
- `failed`：执行失败（可重试或终止）
- `cancelled`：用户取消/策略取消

### 6.2 幂等性与重试

- Task 应尽量可重试：Runner 对“可重试”失败应提供错误码/分类。
- Butler 依据策略重试：网络故障/临时错误可自动重试；破坏性操作默认不自动重试。

## 7. 调度与匹配规则（Butler → Runner）

匹配维度（由 Butler 决策）：

- **capability 匹配**：Runner 必须满足 `required_capabilities`
- **安全等级**：Runner 的权限/沙箱级别要满足 task policy
- **负载与并发**：Runner 当前队列长度、并发上限
- **亲和性**：同一项目/目录的任务尽量在同一 Runner（减少上下文切换）
- **失败回避**：近期失败率高的 Runner 降权

调度策略（MVP）：

- 最小可用：capability 过滤 + 最低负载优先 + 超时回收

## 8. 接口规格（初版，协议可实现为 HTTP/JSON）

### 8.1 Runner 注册与心跳

- `POST /runners/register`
  - req: `{ name, type, capabilities, metadata }`
  - resp: `{ runner_id, heartbeat_interval_ms }`
- `POST /runners/heartbeat`
  - req: `{ runner_id, status, metrics }`
  - resp: `{ ok: true }`

### 8.2 Task 下发与回传

- `POST /tasks/submit`（Butler内部：Intent → Task 后入队）
  - req: `{ task }`
  - resp: `{ task_id }`
- `POST /runners/{runner_id}/tasks/pull`（Runner 拉取模式，MVP更简单）
  - req: `{ max_tasks }`
  - resp: `{ tasks: [...] }`
- `POST /tasks/{task_id}/events`
  - req: `{ runner_id, events: [...] }`
  - resp: `{ ok: true }`
- `POST /tasks/{task_id}/complete`
  - req: `{ runner_id, status, result, artifacts }`
  - resp: `{ ok: true }`

说明：

- MVP 推荐 **Runner 拉取**：避免 Butler 主动推送时的网络拓扑复杂度。
- 未来可扩展 **推送/WebSocket** 以获得更低延迟。

### 8.3 用户确认（安全闸）

- `POST /tasks/{task_id}/request_confirmation`
  - req: `{ reason, proposed_actions }`
- `POST /tasks/{task_id}/confirm`
  - req: `{ approved: true|false, notes }`

## 9. 安全与策略（MVP必备）

默认策略：

- **破坏性操作需要确认**：删除、覆盖、`rm -rf`、磁盘格式化、修改系统配置等。
- **命令白/黑名单（可配置）**：Runner 侧应能拒绝执行不符合 policy 的 action。
- **最小权限 Runner**：不同 Runner 可设置权限范围（只读/读写/网络访问等）。
- **审计日志不可篡改（至少可追溯）**：所有执行都记录事件与结果摘要。

## 10. 可观测性

最低要求：

- **Task timeline**：状态变更、关键事件
- **Runner health**：在线率、延迟、失败率
- **执行日志**：可按 task_id 检索

建议输出：

- OpenTelemetry trace/span（后续）

## 11. 可扩展性设计

- Runner 插件化：`capabilities` 作为契约
- Task schema 可版本化：`task.schema_version`
- 多 Agent：Runner 可实现 `agent:*` capability 并封装 prompt/工具调用

## 12. MVP 范围（建议）

Butler（MVP）：

- 基础对话入口（CLI 或简单 HTTP）
- Intent → Task（先规则/模板 + LLM 可选）
- Runner 注册/心跳
- 任务队列 + 拉取式派发
- Task 状态机 + 日志聚合
- 用户确认闸（至少在策略命中时暂停并请求确认）

Runner（MVP）：

- 拉取任务并执行两类 action：
  - `shell`：受限命令执行（带超时、输出回传）
  - `agent:generic`：把子任务交给外部 agent（先占位实现也可）
- 能力声明与心跳

## 13. 里程碑（从 spec 到实现）

- M0：确定数据模型与接口（本文）+ 仓库结构
- M1：实现最小 Butler（队列、状态机、Runner注册/心跳、task派发）
- M2：实现最小 Runner（shell 执行 + 日志回传 + 失败分类）
- M3：加入意图识别与规划（规则→LLM增强）
- M4：策略/权限增强（白名单、沙箱、secret 管理）

## 14. 待决策项（后续补齐）

- 运行形态：单机优先还是 client/server？
- 存储：SQLite/文件/Redis？（MVP可先内存 + 可选持久化）
- LLM 依赖：本地模型/云API/可插拔 provider？
- 任务 DSL：是 JSON schema、YAML 还是自定义？

