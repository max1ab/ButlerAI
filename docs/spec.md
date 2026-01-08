# ButlerAI 规格说明（Spec）

本文件作为 **Spec 总览与索引**。分层细节被拆分到以下三个文件中：

- `docs/spec/butler.md`：Butler（控制面 / Orchestrator）规格
- `docs/spec/runner.md`：Runner（数据面 / 执行器）规格
- `docs/spec/task.md`：Task（任务模型 / 状态机 / 回传语义）规格

## 背景与目标

ButlerAI 面向**技术爱好者**：识别用户意图，规划任务，并派发给 Runner 执行后回传结果。

核心目标：

- **意图识别准确**：NL → Intent → Task/Plan
- **任务可控可追踪**：状态机、日志、审计、重试策略
- **Runner 可扩展**：capabilities 契约驱动的可插拔执行端
- **安全可控**：默认对破坏性操作启用确认闸与策略

非目标（初期）：

- 企业级多租户计费与复杂权限治理
- 默认“无确认”的敏感操作全自动执行

## 目标用户与典型场景（MVP优先）

- **本机任务**：文件整理/批量重命名/脚手架/脚本执行
- **开发协作**：issue/PR 草稿、测试汇总、CI 失败归因
- **信息整理**：摘要、TODO、可复制命令清单
- **Agent 执行**：将子任务交给专用 agent 并汇总

## 术语

- **Intent（意图）**：用户请求的结构化表示（含实体/约束/置信度）
- **Task（任务）**：可执行工作单元（输入/策略/状态/输出）
- **Runner**：执行 Task 的实体（本地/远程/容器/Agent）
- **Capability**：Runner 能力声明（工具、权限、资源）
- **Policy**：安全与执行策略（确认闸、禁止规则等）

## 里程碑（Spec → 实现）

- M0：确定本文档与三份子 spec
- M1：最小 Butler（队列、状态机、Runner注册/心跳、派发）
- M2：最小 Runner（拉取任务、shell 执行、日志回传、失败分类）
- M3：意图识别与规划增强（规则→LLM 可插拔）
- M4：策略/权限/沙箱与可观测性增强

## 待决策项

- 运行形态：单机优先 vs client/server
- 存储：内存 + 可选 SQLite/文件/Redis
- LLM Provider：可插拔（本地/云）
- Task DSL：JSON schema vs YAML

