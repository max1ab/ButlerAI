from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ButlerResponse:
    status: int
    json: dict[str, Any]


class ButlerClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def post(self, path: str, body: dict[str, Any]) -> ButlerResponse:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = Request(
            url,
            data=data,
            headers={"content-type": "application/json", "content-length": str(len(data))},
            method="POST",
        )
        try:
            with urlopen(req, timeout=5) as resp:
                payload = resp.read().decode("utf-8")
                return ButlerResponse(status=resp.status, json=json.loads(payload) if payload else {})
        except HTTPError as e:
            payload = e.read().decode("utf-8") if e.fp else ""
            try:
                obj = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                obj = {"error": "http_error", "detail": payload}
            return ButlerResponse(status=e.code, json=obj)

    def get(self, path: str) -> ButlerResponse:
        url = f"{self.base_url}{path}"
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=5) as resp:
                payload = resp.read().decode("utf-8")
                return ButlerResponse(status=resp.status, json=json.loads(payload) if payload else {})
        except HTTPError as e:
            payload = e.read().decode("utf-8") if e.fp else ""
            try:
                obj = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                obj = {"error": "http_error", "detail": payload}
            return ButlerResponse(status=e.code, json=obj)

