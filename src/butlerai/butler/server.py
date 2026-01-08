from __future__ import annotations

import json
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from butlerai.common.store import InMemoryStore


JsonDict = dict[str, Any]
HandlerFn = Callable[[BaseHTTPRequestHandler, dict[str, str], JsonDict], None]


def _read_json(handler: BaseHTTPRequestHandler) -> JsonDict:
    length = int(handler.headers.get("content-length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("invalid_json")
    if not isinstance(obj, dict):
        raise ValueError("invalid_json_object")
    return obj


def _write_json(handler: BaseHTTPRequestHandler, status: int, obj: Any) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class ButlerHTTPServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.store = InMemoryStore()
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def serve_forever(self) -> None:
        server = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self._server = server
        server.serve_forever()

    def start_in_background(self) -> None:
        server = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self._server = server
        t = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread = t
        t.start()

    def shutdown(self) -> None:
        if self._server:
            self._server.shutdown()

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        store = self.store

        routes: list[tuple[str, re.Pattern[str], HandlerFn]] = []

        def route(method: str, pattern: str) -> Callable[[HandlerFn], HandlerFn]:
            regex = re.compile(pattern)

            def deco(fn: HandlerFn) -> HandlerFn:
                routes.append((method.upper(), regex, fn))
                return fn

            return deco

        @route("POST", r"^/runners/register$")
        def register_runner(h: BaseHTTPRequestHandler, _params: dict[str, str], body: JsonDict) -> None:
            r = store.register_runner(
                name=str(body.get("name") or "runner"),
                type=str(body.get("type") or "local"),
                capabilities=list(body.get("capabilities") or []),
                metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
            )
            _write_json(h, 200, {"runner_id": r.id, "heartbeat_interval_ms": 5_000})

        @route("POST", r"^/runners/heartbeat$")
        def heartbeat(h: BaseHTTPRequestHandler, _params: dict[str, str], body: JsonDict) -> None:
            try:
                r = store.heartbeat_runner(
                    runner_id=str(body.get("runner_id") or ""),
                    status=body.get("status"),
                    metrics=body.get("metrics") if isinstance(body.get("metrics"), dict) else {},
                )
            except KeyError:
                _write_json(h, 404, {"error": "runner_not_found"})
                return
            _write_json(h, 200, {"ok": True, "runner": {"id": r.id, "status": r.status}})

        @route("POST", r"^/tasks/submit$")
        def submit_task(h: BaseHTTPRequestHandler, _params: dict[str, str], body: JsonDict) -> None:
            task_obj = body.get("task")
            if not isinstance(task_obj, dict):
                _write_json(h, 400, {"error": "invalid_task"})
                return
            t = store.submit_task(task=task_obj)
            _write_json(h, 200, {"task_id": t.id, "state": t.state.value})

        @route("POST", r"^/runners/(?P<runner_id>[^/]+)/tasks/pull$")
        def pull_tasks(h: BaseHTTPRequestHandler, params: dict[str, str], body: JsonDict) -> None:
            runner_id = params["runner_id"]
            max_tasks = int(body.get("max_tasks") or 1)
            try:
                tasks = store.pull_tasks(runner_id=runner_id, max_tasks=max_tasks)
            except KeyError:
                _write_json(h, 404, {"error": "runner_not_found"})
                return
            _write_json(h, 200, {"tasks": [t.to_dict() for t in tasks]})

        @route("POST", r"^/tasks/(?P<task_id>[^/]+)/events$")
        def task_events(h: BaseHTTPRequestHandler, params: dict[str, str], body: JsonDict) -> None:
            task_id = params["task_id"]
            runner_id = body.get("runner_id")
            events = body.get("events")
            if not isinstance(events, list):
                _write_json(h, 400, {"error": "invalid_events"})
                return
            try:
                store.append_events(task_id=task_id, runner_id=str(runner_id) if runner_id else None, events=events)
            except KeyError:
                _write_json(h, 404, {"error": "task_not_found"})
                return
            _write_json(h, 200, {"ok": True})

        @route("POST", r"^/tasks/(?P<task_id>[^/]+)/complete$")
        def task_complete(h: BaseHTTPRequestHandler, params: dict[str, str], body: JsonDict) -> None:
            task_id = params["task_id"]
            runner_id = body.get("runner_id")
            status = str(body.get("status") or "")
            result = body.get("result") if isinstance(body.get("result"), dict) else None
            artifacts = body.get("artifacts") if isinstance(body.get("artifacts"), list) else None
            try:
                t = store.complete_task(
                    task_id=task_id,
                    runner_id=str(runner_id) if runner_id else None,
                    status=status,
                    result=result,
                    artifacts=artifacts,
                )
            except KeyError:
                _write_json(h, 404, {"error": "task_not_found"})
                return
            _write_json(h, 200, {"ok": True, "state": t.state.value})

        @route("POST", r"^/tasks/(?P<task_id>[^/]+)/confirm$")
        def confirm(h: BaseHTTPRequestHandler, params: dict[str, str], body: JsonDict) -> None:
            task_id = params["task_id"]
            approved = bool(body.get("approved"))
            notes = body.get("notes")
            try:
                t = store.confirm_task(task_id=task_id, approved=approved, notes=str(notes) if notes else None)
            except KeyError:
                _write_json(h, 404, {"error": "task_not_found"})
                return
            _write_json(h, 200, {"ok": True, "state": t.state.value})

        @route("GET", r"^/tasks/(?P<task_id>[^/]+)$")
        def get_task(h: BaseHTTPRequestHandler, params: dict[str, str], _body: JsonDict) -> None:
            try:
                t = store.get_task(params["task_id"])
            except KeyError:
                _write_json(h, 404, {"error": "task_not_found"})
                return
            evs = [e.to_dict() for e in store.list_events(t.id)]
            _write_json(h, 200, {"task": t.to_dict(), "events": evs})

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self._handle("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._handle("POST")

            def log_message(self, _format: str, *_args: Any) -> None:
                # quiet by default (tests)
                return

            def _handle(self, method: str) -> None:
                parsed = urlparse(self.path)
                path = parsed.path
                try:
                    body = _read_json(self) if method == "POST" else {}
                except ValueError as e:
                    _write_json(self, 400, {"error": str(e)})
                    return

                for m, regex, fn in routes:
                    if m != method:
                        continue
                    match = regex.match(path)
                    if not match:
                        continue
                    try:
                        fn(self, match.groupdict(), body)
                    except Exception as e:  # pragma: no cover
                        _write_json(self, 500, {"error": "internal_error", "detail": str(e)})
                    return

                _write_json(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

        return Handler

