from __future__ import annotations

import argparse
import time

from .runner import Runner, RunnerConfig


def main() -> None:
    parser = argparse.ArgumentParser(prog="butlerai-runner", description="Run ButlerAI Runner (pull + execute)")
    parser.add_argument("--butler-url", default="http://127.0.0.1:8000")
    parser.add_argument("--name", default="runner")
    parser.add_argument("--type", default="local")
    parser.add_argument("--capability", action="append", default=["shell"], help="Repeatable capability flag")
    parser.add_argument("--max-tasks", type=int, default=1)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--once", action="store_true", help="Run one pull/execute cycle then exit")
    args = parser.parse_args()

    r = Runner(
        butler_url=args.butler_url,
        config=RunnerConfig(name=args.name, type=args.type, capabilities=list(args.capability)),
    )

    if args.once:
        r.run_once(max_tasks=args.max_tasks)
        return

    while True:
        r.run_once(max_tasks=args.max_tasks)
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()

