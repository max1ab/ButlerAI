from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ShellResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def _truncate(s: str, max_bytes: int) -> str:
    b = s.encode("utf-8", errors="replace")
    if len(b) <= max_bytes:
        return s
    return b[:max_bytes].decode("utf-8", errors="replace") + "\n...[truncated]..."


def run_shell(
    *,
    command: str,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout_ms: int = 60_000,
    max_output_bytes: int = 64 * 1024,
) -> ShellResult:
    """
    MVP shell execution with timeout + output truncation.
    Uses shell=True because Task input is a command string.
    """
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000.0,
        )
        return ShellResult(
            exit_code=int(completed.returncode),
            stdout=_truncate(completed.stdout or "", max_output_bytes),
            stderr=_truncate(completed.stderr or "", max_output_bytes),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as e:
        stdout = ""
        stderr = ""
        if e.stdout:
            stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="replace")
        if e.stderr:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="replace")
        return ShellResult(
            exit_code=124,
            stdout=_truncate(stdout, max_output_bytes),
            stderr=_truncate(stderr, max_output_bytes),
            timed_out=True,
        )

