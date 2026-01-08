from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .models import Policy


_DEFAULT_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\b", "Potentially destructive remove: rm -rf"),
    (r"\bmkfs(\.\w+)?\b", "Filesystem formatting detected: mkfs"),
    (r"\bdd\s+if=", "Raw disk write detected: dd if="),
    (r"\bshutdown\b", "System shutdown detected"),
    (r"\breboot\b", "System reboot detected"),
]


def assess_task_policy(task_inputs: dict[str, Any], base: Policy) -> tuple[Policy, list[str]]:
    """
    MVP policy engine: mark as requires_confirmation when obvious dangerous patterns are detected.
    Returns (effective_policy, reasons).
    """
    reasons: list[str] = []
    effective = base

    cmd = str(task_inputs.get("command") or "")
    for pattern, reason in _DEFAULT_DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            reasons.append(reason)

    if reasons and not base.requires_confirmation:
        effective = replace(base, requires_confirmation=True, risk_level="high")

    return effective, reasons

