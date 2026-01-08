from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from butlerai.common.policy import assess_task_policy
from butlerai.common.models import Policy, TaskEvent

from .client import ButlerClient
from .shell_exec import run_shell


@dataclass
class RunnerConfig:
    name: str = "runner"
    type: str = "local"
    capabilities: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.capabilities is None:
            self.capabilities = ["shell"]


class Runner:
    def __init__(self, *, butler_url: str, config: RunnerConfig) -> None:
        self.client = ButlerClient(butler_url)
        self.config = config
        self.runner_id: str | None = None

    def register(self) -> str:
        resp = self.client.post(
            "/runners/register",
            {"name": self.config.name, "type": self.config.type, "capabilities": self.config.capabilities},
        )
        if resp.status != 200:
            raise RuntimeError(f"register_failed: {resp.status} {resp.json}")
        self.runner_id = str(resp.json["runner_id"])
        return self.runner_id

    def heartbeat(self, status: str = "online") -> None:
        assert self.runner_id is not None
        _ = self.client.post("/runners/heartbeat", {"runner_id": self.runner_id, "status": status, "metrics": {}})

    def run_once(self, *, max_tasks: int = 1) -> int:
        if self.runner_id is None:
            self.register()
        self.heartbeat("online")

        assert self.runner_id is not None
        resp = self.client.post(f"/runners/{self.runner_id}/tasks/pull", {"max_tasks": max_tasks})
        if resp.status != 200:
            return 0
        tasks = resp.json.get("tasks") or []
        if not isinstance(tasks, list):
            return 0

        executed = 0
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "")
            if not task_id:
                continue
            self._execute_task(task)
            executed += 1
        return executed

    def _execute_task(self, task: dict[str, Any]) -> None:
        assert self.runner_id is not None
        task_id = str(task["id"])

        # Runner-side policy re-check (defense in depth)
        policy_dict = task.get("policy") or {}
        base_policy = Policy(
            risk_level=policy_dict.get("risk_level", "low"),
            requires_confirmation=bool(policy_dict.get("requires_confirmation", False)),
            allow_patterns=list(policy_dict.get("allow_patterns") or []),
            deny_patterns=list(policy_dict.get("deny_patterns") or []),
        )
        inputs = dict(task.get("inputs") or {})
        effective_policy, reasons = assess_task_policy(inputs, base_policy)
        if effective_policy.requires_confirmation:
            self._post_events(
                task_id,
                [
                    TaskEvent.make(
                        task_id=task_id,
                        runner_id=self.runner_id,
                        level="warn",
                        message="Runner refused to execute: confirmation required",
                        data={"reasons": reasons or ["requires_confirmation"]},
                    ).to_dict()
                ],
            )
            self.client.post(
                f"/tasks/{task_id}/complete",
                {
                    "runner_id": self.runner_id,
                    "status": "failed",
                    "result": {"error": "needs_confirmation", "reasons": reasons},
                    "artifacts": [],
                },
            )
            return

        # MVP: only support shell tasks (by capability + presence of inputs.command)
        command = str(inputs.get("command") or "")
        cwd = inputs.get("cwd")
        env = inputs.get("env")
        timeout_ms = int(task.get("timeout_ms") or 60_000)
        if not command:
            self.client.post(
                f"/tasks/{task_id}/complete",
                {"runner_id": self.runner_id, "status": "failed", "result": {"error": "missing_command"}, "artifacts": []},
            )
            return

        self._post_events(
            task_id,
            [
                TaskEvent.make(
                    task_id=task_id, runner_id=self.runner_id, level="info", message="Task running"
                ).to_dict()
            ],
        )

        res = run_shell(command=command, cwd=str(cwd) if cwd else None, env=env if isinstance(env, dict) else None, timeout_ms=timeout_ms)
        self._post_events(
            task_id,
            [
                TaskEvent.make(
                    task_id=task_id,
                    runner_id=self.runner_id,
                    level="info",
                    message="Shell finished",
                    data={"exit_code": res.exit_code, "timed_out": res.timed_out},
                ).to_dict(),
                TaskEvent.make(
                    task_id=task_id,
                    runner_id=self.runner_id,
                    level="info",
                    message="stdout",
                    data={"stdout": res.stdout},
                ).to_dict(),
                TaskEvent.make(
                    task_id=task_id,
                    runner_id=self.runner_id,
                    level="info" if res.exit_code == 0 else "error",
                    message="stderr",
                    data={"stderr": res.stderr},
                ).to_dict(),
            ],
        )

        status = "succeeded" if res.exit_code == 0 and not res.timed_out else "failed"
        self.client.post(
            f"/tasks/{task_id}/complete",
            {
                "runner_id": self.runner_id,
                "status": status,
                "result": {
                    "exit_code": res.exit_code,
                    "timed_out": res.timed_out,
                },
                "artifacts": [],
            },
        )

    def _post_events(self, task_id: str, events: list[dict[str, Any]]) -> None:
        assert self.runner_id is not None
        self.client.post(
            f"/tasks/{task_id}/events",
            {"runner_id": self.runner_id, "events": events},
        )

