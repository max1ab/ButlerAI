import json
import os
import sys
import time
import unittest
from http.client import HTTPConnection

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from butlerai.butler.server import ButlerHTTPServer
from butlerai.runner.runner import Runner, RunnerConfig


def http_json(method: str, host: str, port: int, path: str, body: dict | None = None) -> tuple[int, dict]:
    conn = HTTPConnection(host, port, timeout=3)
    try:
        data = b""
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers = {"content-type": "application/json", "content-length": str(len(data))}
        conn.request(method, path, body=data if body is not None else None, headers=headers)
        resp = conn.getresponse()
        payload = resp.read()
        obj = json.loads(payload.decode("utf-8")) if payload else {}
        return resp.status, obj
    finally:
        conn.close()


class TestRunnerE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ButlerHTTPServer(host="127.0.0.1", port=0)
        cls.server.start_in_background()
        for _ in range(100):
            if cls.server._server and cls.server._server.server_address[1] != 0:
                break
            time.sleep(0.01)
        assert cls.server._server is not None
        cls.host, cls.port = cls.server._server.server_address
        cls.butler_url = f"http://{cls.host}:{cls.port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_runner_pulls_and_executes_shell_task(self) -> None:
        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            "/tasks/submit",
            {
                "task": {
                    "title": "e2e-echo",
                    "required_capabilities": ["shell"],
                    "inputs": {"command": "echo e2e"},
                    "timeout_ms": 2000,
                }
            },
        )
        self.assertEqual(st, 200)
        task_id = obj["task_id"]
        self.assertEqual(obj["state"], "queued")

        runner = Runner(butler_url=self.butler_url, config=RunnerConfig(name="e2e", type="local", capabilities=["shell"]))
        executed = runner.run_once(max_tasks=1)
        self.assertEqual(executed, 1)

        st, obj = http_json("GET", self.host, self.port, f"/tasks/{task_id}")
        self.assertEqual(st, 200)
        self.assertEqual(obj["task"]["state"], "succeeded")
        self.assertEqual(obj["task"]["result"]["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()

