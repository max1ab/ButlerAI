from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from typing import Any

from .models import Policy, Runner, Task, TaskEvent, TaskState, utc_now_iso
from .policy import assess_task_policy


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.runners: dict[str, Runner] = {}
        self.tasks: dict[str, Task] = {}
        self.task_events: dict[str, list[TaskEvent]] = {}
        self.task_confirmation_reasons: dict[str, list[str]] = {}

    def register_runner(
        self, *, name: str, type: str, capabilities: list[str], metadata: dict[str, Any] | None
    ) -> Runner:
        with self._lock:
            runner_id = str(uuid.uuid4())
            r = Runner(
                id=runner_id,
                name=name,
                type=type,
                capabilities=list(capabilities),
                metadata=metadata or {},
            )
            self.runners[runner_id] = r
            return r

    def heartbeat_runner(
        self, *, runner_id: str, status: str | None, metrics: dict[str, Any] | None
    ) -> Runner:
        with self._lock:
            if runner_id not in self.runners:
                raise KeyError("runner_not_found")
            r = self.runners[runner_id]
            if status:
                r.status = status  # type: ignore[assignment]
            r.last_heartbeat_at = utc_now_iso()
            # metrics currently unused (MVP placeholder)
            self.runners[runner_id] = r
            return r

    def submit_task(self, *, task: dict[str, Any]) -> Task:
        with self._lock:
            task_id = str(uuid.uuid4())

            policy_dict = task.get("policy") or {}
            base_policy = Policy(
                risk_level=policy_dict.get("risk_level", "low"),
                requires_confirmation=bool(policy_dict.get("requires_confirmation", False)),
                allow_patterns=list(policy_dict.get("allow_patterns") or []),
                deny_patterns=list(policy_dict.get("deny_patterns") or []),
            )

            inputs = dict(task.get("inputs") or {})
            effective_policy, reasons = assess_task_policy(inputs, base_policy)

            t = Task(
                id=task_id,
                title=str(task.get("title") or "Untitled Task"),
                description=str(task.get("description") or ""),
                intent_id=task.get("intent_id"),
                inputs=inputs,
                required_capabilities=list(task.get("required_capabilities") or []),
                policy=effective_policy,
                priority=task.get("priority", "normal"),
                timeout_ms=int(task.get("timeout_ms") or 60_000),
                retries=int(task.get("retries") or 0),
                state=TaskState.created,
            )

            # state transition: created -> queued / waiting_confirmation
            if t.policy.requires_confirmation:
                t.state = TaskState.waiting_confirmation
                self.task_confirmation_reasons[task_id] = reasons or ["Policy requires confirmation"]
                self._append_event(
                    TaskEvent.make(
                        task_id=task_id,
                        runner_id=None,
                        level="warn",
                        message="Task requires confirmation before execution",
                        data={"reasons": self.task_confirmation_reasons[task_id]},
                    )
                )
            else:
                t.state = TaskState.queued
                self._append_event(
                    TaskEvent.make(
                        task_id=task_id,
                        runner_id=None,
                        level="info",
                        message="Task queued",
                    )
                )

            t.updated_at = utc_now_iso()
            self.tasks[task_id] = t
            return t

    def confirm_task(self, *, task_id: str, approved: bool, notes: str | None = None) -> Task:
        with self._lock:
            t = self._get_task(task_id)
            if t.state != TaskState.waiting_confirmation:
                return t

            if approved:
                t = replace(t, state=TaskState.queued, updated_at=utc_now_iso())
                self.tasks[task_id] = t
                self._append_event(
                    TaskEvent.make(
                        task_id=task_id,
                        runner_id=None,
                        level="info",
                        message="Task confirmation approved",
                        data={"notes": notes or ""},
                    )
                )
            else:
                t = replace(t, state=TaskState.cancelled, updated_at=utc_now_iso())
                self.tasks[task_id] = t
                self._append_event(
                    TaskEvent.make(
                        task_id=task_id,
                        runner_id=None,
                        level="warn",
                        message="Task confirmation rejected; task cancelled",
                        data={"notes": notes or ""},
                    )
                )
            return t

    def pull_tasks(self, *, runner_id: str, max_tasks: int) -> list[Task]:
        with self._lock:
            if runner_id not in self.runners:
                raise KeyError("runner_not_found")
            runner = self.runners[runner_id]
            if runner.status != "online":
                return []

            result: list[Task] = []
            for t in self.tasks.values():
                if len(result) >= max_tasks:
                    break
                if t.state != TaskState.queued:
                    continue
                if not self._capabilities_satisfy(runner.capabilities, t.required_capabilities):
                    continue
                # assign
                t.assigned_runner_id = runner_id
                t.state = TaskState.assigned
                t.updated_at = utc_now_iso()
                self.tasks[t.id] = t
                self._append_event(
                    TaskEvent.make(
                        task_id=t.id,
                        runner_id=runner_id,
                        level="info",
                        message="Task assigned",
                    )
                )
                result.append(t)
            return result

    def append_events(self, *, task_id: str, runner_id: str | None, events: list[dict[str, Any]]) -> None:
        with self._lock:
            _ = self._get_task(task_id)
            for e in events:
                self._append_event(
                    TaskEvent(
                        timestamp=str(e.get("timestamp") or utc_now_iso()),
                        task_id=task_id,
                        runner_id=runner_id,
                        level=e.get("level", "info"),
                        message=str(e.get("message") or ""),
                        data=dict(e.get("data") or {}),
                    )
                )

    def complete_task(
        self,
        *,
        task_id: str,
        runner_id: str | None,
        status: str,
        result: dict[str, Any] | None,
        artifacts: list[dict[str, Any]] | None,
    ) -> Task:
        with self._lock:
            t = self._get_task(task_id)
            new_state = {
                "succeeded": TaskState.succeeded,
                "failed": TaskState.failed,
                "cancelled": TaskState.cancelled,
            }.get(status, TaskState.failed)
            t.state = new_state
            t.result = result
            t.artifacts = artifacts or []
            t.updated_at = utc_now_iso()
            self.tasks[task_id] = t
            self._append_event(
                TaskEvent.make(
                    task_id=task_id,
                    runner_id=runner_id,
                    level="info" if new_state == TaskState.succeeded else "error",
                    message=f"Task completed: {new_state.value}",
                    data={"status": status},
                )
            )
            return t

    def get_task(self, task_id: str) -> Task:
        with self._lock:
            return self._get_task(task_id)

    def list_events(self, task_id: str) -> list[TaskEvent]:
        with self._lock:
            return list(self.task_events.get(task_id, []))

    def _get_task(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise KeyError("task_not_found")
        return self.tasks[task_id]

    def _append_event(self, ev: TaskEvent) -> None:
        self.task_events.setdefault(ev.task_id, []).append(ev)

    @staticmethod
    def _capabilities_satisfy(have: list[str], need: list[str]) -> bool:
        have_set = set(have)
        return all(cap in have_set for cap in need)

