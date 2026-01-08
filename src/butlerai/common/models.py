from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskState(str, Enum):
    created = "created"
    queued = "queued"
    assigned = "assigned"
    running = "running"
    waiting_confirmation = "waiting_confirmation"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


RunnerStatus = Literal["online", "offline", "degraded"]
TaskPriority = Literal["low", "normal", "high"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Policy:
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
    allow_patterns: list[str] = field(default_factory=list)
    deny_patterns: list[str] = field(default_factory=list)


@dataclass
class Runner:
    id: str
    name: str
    type: str
    capabilities: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    status: RunnerStatus = "online"
    last_heartbeat_at: str = field(default_factory=utc_now_iso)


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    intent_id: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    required_capabilities: list[str] = field(default_factory=list)
    policy: Policy = field(default_factory=Policy)
    priority: TaskPriority = "normal"
    timeout_ms: int = 60_000
    retries: int = 0
    state: TaskState = TaskState.created
    assigned_runner_id: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d


@dataclass(frozen=True)
class TaskEvent:
    timestamp: str
    task_id: str
    runner_id: str | None
    level: Literal["info", "warn", "error"]
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make(
        *,
        task_id: str,
        runner_id: str | None,
        level: Literal["info", "warn", "error"],
        message: str,
        data: dict[str, Any] | None = None,
    ) -> "TaskEvent":
        return TaskEvent(
            timestamp=utc_now_iso(),
            task_id=task_id,
            runner_id=runner_id,
            level=level,
            message=message,
            data=data or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

