# ButlerAI 开发 TODO（按 Spec 顺序）

> 说明：本文件用于追踪实现进度；实现以 `docs/spec/*.md` 为准。

## M0：工程与规范

- [x] 初始化 Python 项目骨架（`pyproject.toml`、`src/`、`tests/`）
- [x] 约定运行方式（Butler/Runner CLI）
- [x] 基础测试框架可运行（unittest/pytest 二选一）

## M1：Butler（控制面）

- [x] Runner 注册：`POST /runners/register`
- [x] Runner 心跳：`POST /runners/heartbeat`
- [x] Task 提交入队：`POST /tasks/submit`
- [x] Runner 拉取任务：`POST /runners/{runner_id}/tasks/pull`
- [x] Task 事件回传：`POST /tasks/{task_id}/events`
- [x] Task 完成回传：`POST /tasks/{task_id}/complete`
- [x] 用户确认闸：`POST /tasks/{task_id}/confirm`（命中策略进入 `waiting_confirmation`）
- [x] Butler 的主流程测试：注册→提交→派发→完成
- [x] 确认闸测试：提交高风险任务→等待确认→确认后派发

## M2：Runner（数据面）

- [x] Runner client：注册/心跳/拉取/回传
- [x] `shell` 执行：超时、退出码、stdout/stderr 截断
- [x] policy 二次校验（拒绝或请求确认）
- [x] Runner 单元测试：shell 执行成功/失败/超时
- [x] 端到端测试：Runner 拉取 Butler 的任务并执行回传

