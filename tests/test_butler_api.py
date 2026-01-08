import json
import os
import sys
import time
import unittest
from http.client import HTTPConnection

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from butlerai.butler.server import ButlerHTTPServer


def http_json(method: str, host: str, port: int, path: str, body: dict | None = None) -> tuple[int, dict]:
    conn = HTTPConnection(host, port, timeout=2)
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


class TestButlerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ButlerHTTPServer(host="127.0.0.1", port=0)
        cls.server.start_in_background()
        # wait for server to bind
        for _ in range(50):
            if cls.server._server and cls.server._server.server_address[1] != 0:
                break
            time.sleep(0.01)
        assert cls.server._server is not None
        cls.host, cls.port = cls.server._server.server_address

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_register_submit_pull_complete_happy_path(self) -> None:
        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            "/runners/register",
            {"name": "r1", "type": "local", "capabilities": ["shell"]},
        )
        self.assertEqual(st, 200)
        runner_id = obj["runner_id"]

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            "/tasks/submit",
            {
                "task": {
                    "title": "echo",
                    "required_capabilities": ["shell"],
                    "inputs": {"command": "echo hi"},
                }
            },
        )
        self.assertEqual(st, 200)
        task_id = obj["task_id"]
        self.assertEqual(obj["state"], "queued")

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            f"/runners/{runner_id}/tasks/pull",
            {"max_tasks": 1},
        )
        self.assertEqual(st, 200)
        self.assertEqual(len(obj["tasks"]), 1)
        self.assertEqual(obj["tasks"][0]["id"], task_id)

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            f"/tasks/{task_id}/complete",
            {"runner_id": runner_id, "status": "succeeded", "result": {"ok": True}, "artifacts": []},
        )
        self.assertEqual(st, 200)
        self.assertEqual(obj["state"], "succeeded")

        st, obj = http_json("GET", self.host, self.port, f"/tasks/{task_id}")
        self.assertEqual(st, 200)
        self.assertEqual(obj["task"]["state"], "succeeded")

    def test_confirmation_gate(self) -> None:
        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            "/runners/register",
            {"name": "r2", "type": "local", "capabilities": ["shell"]},
        )
        runner_id = obj["runner_id"]

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            "/tasks/submit",
            {
                "task": {
                    "title": "danger",
                    "required_capabilities": ["shell"],
                    "inputs": {"command": "rm -rf /tmp/something"},
                }
            },
        )
        self.assertEqual(st, 200)
        task_id = obj["task_id"]
        self.assertEqual(obj["state"], "waiting_confirmation")

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            f"/runners/{runner_id}/tasks/pull",
            {"max_tasks": 10},
        )
        self.assertEqual(st, 200)
        # should not be dispatched until confirmed
        self.assertEqual(obj["tasks"], [])

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            f"/tasks/{task_id}/confirm",
            {"approved": True, "notes": "ok"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(obj["state"], "queued")

        st, obj = http_json(
            "POST",
            self.host,
            self.port,
            f"/runners/{runner_id}/tasks/pull",
            {"max_tasks": 1},
        )
        self.assertEqual(st, 200)
        self.assertEqual(len(obj["tasks"]), 1)
        self.assertEqual(obj["tasks"][0]["id"], task_id)


if __name__ == "__main__":
    unittest.main()

