"""天枢互通桥 CLI 测试：请求路径、身份头、信封与错误处理。"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest
import tianshu_bridge


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    calls: list[urllib.request.Request] = []

    def fake(request: urllib.request.Request, timeout: int) -> _Response:
        calls.append(request)
        return _Response({"system": "tianshu", "external_id": "issue/1", "documents": []})

    monkeypatch.setattr(tianshu_bridge, "urlopen", fake)
    return calls


def test_context_sends_actor_and_query(monkeypatch, capsys) -> None:
    calls = _capture(monkeypatch)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--actor",
        "usr_1",
        "context",
        "--external-id",
        "https://github.com/o/r/issues/1",
    ])
    assert code == 0
    assert len(calls) == 1
    request = calls[0]
    assert request.get_method() == "GET"
    assert "external_id=https%3A%2F%2Fgithub.com%2Fo%2Fr%2Fissues%2F1" in request.full_url
    assert request.headers["X-actor"] == "usr_1"
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"]["external_id"] == "issue/1"


def test_publish_posts_requirement_and_tickets(monkeypatch, capsys) -> None:
    calls = _capture(monkeypatch)
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--actor",
        "usr_1",
        "publish",
        "--external-id",
        "https://github.com/o/r/issues/1",
        "--request-id",
        "req-1",
        "--title",
        "需求",
        "--outcome",
        "目标",
        "--scope",
        "范围",
        "--acceptance",
        "验收",
        "--ticket",
        "任务甲",
        "--ticket",
        "任务乙",
    ])
    assert code == 0
    request = calls[0]
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/api/v1/requirements/from-external")
    body = json.loads(request.data.decode("utf-8"))
    assert body["external_id"] == "https://github.com/o/r/issues/1"
    assert [ticket["title"] for ticket in body["tickets"]] == ["任务甲", "任务乙"]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_error_is_reported_and_result_written(monkeypatch, tmp_path, capsys) -> None:
    def failing(request: urllib.request.Request, timeout: int) -> _Response:
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"actor is required"}'),
        )

    monkeypatch.setattr(tianshu_bridge, "urlopen", failing)
    result = tmp_path / "result.json"
    code = tianshu_bridge.main([
        "--api",
        "http://api.example",
        "--result",
        str(result),
        "context",
        "--external-id",
        "issue/1",
    ])
    assert code == 1
    envelope = json.loads(result.read_text(encoding="utf-8"))
    assert envelope["ok"] is False
    assert "403" in envelope["error"]
    assert json.loads(capsys.readouterr().out)["ok"] is False
