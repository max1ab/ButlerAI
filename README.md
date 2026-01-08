# ButlerAI

面向技术爱好者的 AI 管家系统：识别用户意图，拆解并派发任务，由可扩展的 Runner 执行并回传结果。

## 文档

- `docs/spec.md`：Spec 总览（索引）
  - `docs/spec/butler.md`：Butler 规格
  - `docs/spec/runner.md`：Runner 规格
  - `docs/spec/task.md`：Task 规格

## 开发（第一版 / 标准库实现）

> 当前环境可能无法联网安装依赖，所以 0.1.x 版本以 **Python 标准库**为主实现与测试。
> 你在本机可使用 `uv` 来创建虚拟环境、安装依赖并运行命令。

### 运行 Butler（HTTP server）

```bash
python3 -m butlerai.butler --host 127.0.0.1 --port 8000
```

### 运行 Runner（拉取任务并执行 shell）

```bash
python3 -m butlerai.runner --butler-url http://127.0.0.1:8000 --once
```

### 运行测试

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
