"""Gitea webhook API：签名校验、仓库映射与事件落库。"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan

SECRET = "test-webhook-secret"
REPO = {"full_name": "octo/duobao", "html_url": "https://gitea.example/octo/duobao"}


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _setup() -> tuple[TestClient, dict[str, str]]:
    store = Tianxuan(":memory:")
    client = TestClient(create_app(store))
    registered = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Webhook 工坊", "email": "wh@example.com", "password": "secret-pass"},
    ).json()
    headers = {"X-Actor": registered["user_id"]}
    bound = client.post(
        "/api/v1/repo-links",
        headers=headers,
        json={"provider": "gitea", "owner": "octo", "name": "duobao"},
    )
    assert bound.status_code == 200, bound.text
    return client, headers


def _post(
    client: TestClient,
    body: dict[str, Any],
    *,
    event: str = "push",
    signature: str | None = None,
    secret: str = SECRET,
) -> Any:
    raw = json.dumps(body).encode("utf-8")
    return client.post(
        "/api/v1/webhooks/gitea",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Gitea-Event": event,
            "X-Gitea-Delivery": "delivery-1",
            "X-Gitea-Signature": signature if signature is not None else _sign(raw, secret),
        },
    )


def test_push_webhook_records_tenant_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_WEBHOOK_SECRET", SECRET)
    client, headers = _setup()
    body = {
        "ref": "refs/heads/main",
        "before": "a" * 40,
        "after": "b" * 40,
        "repository": REPO,
        "commits": [{"id": "b" * 40}],
        "pusher": {"login": "alice"},
    }

    response = _post(client, body)
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": True, "type": "repo.push"}

    events = client.get("/api/v1/events", headers=headers).json()["events"]
    push = [event for event in events if event["type"] == "repo.push"]
    assert len(push) == 1
    assert push[0]["target"] == "octo/duobao"
    assert push[0]["payload"]["delivery"] == "delivery-1"
    assert push[0]["payload"]["ref"] == "refs/heads/main"
    assert push[0]["payload"]["commits"] == 1


def test_pull_request_webhook_records_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_WEBHOOK_SECRET", SECRET)
    client, headers = _setup()
    body = {
        "action": "opened",
        "repository": REPO,
        "pull_request": {
            "number": 7,
            "title": "feat",
            "state": "open",
            "head": {"ref": "feature", "sha": "c" * 40},
            "base": {"ref": "main", "sha": "d" * 40},
        },
    }

    response = _post(client, body, event="pull_request")
    assert response.status_code == 202
    assert response.json()["type"] == "repo.pull_request"

    events = client.get("/api/v1/events", headers=headers).json()["events"]
    pulls = [event for event in events if event["type"] == "repo.pull_request"]
    assert pulls and pulls[0]["payload"]["number"] == 7


def test_invalid_signature_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_WEBHOOK_SECRET", SECRET)
    client, _ = _setup()
    body = {"repository": REPO, "ref": "refs/heads/main"}

    assert _post(client, body, signature="deadbeef").status_code == 401
    assert _post(client, body, secret="other-secret").status_code == 401


def test_unlinked_repository_and_unsupported_event_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_WEBHOOK_SECRET", SECRET)
    client, _ = _setup()
    unlinked = {"repository": {"full_name": "octo/unknown"}, "ref": "refs/heads/main"}
    ignored = _post(client, unlinked)
    assert ignored.status_code == 202
    assert ignored.json() == {"accepted": False, "reason": "unlinked repository"}

    unsupported = _post(client, {"repository": REPO}, event="issues")
    assert unsupported.status_code == 202
    assert unsupported.json() == {"accepted": False, "reason": "unsupported event"}


def test_webhook_requires_configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANXUAN_GITEA_WEBHOOK_SECRET", raising=False)
    client, _ = _setup()
    assert _post(client, {"repository": REPO}).status_code == 503


def test_webhook_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANXUAN_GITEA_WEBHOOK_SECRET", SECRET)
    client, _ = _setup()
    raw = b"not-json"
    response = client.post(
        "/api/v1/webhooks/gitea",
        content=raw,
        headers={"X-Gitea-Event": "push", "X-Gitea-Signature": _sign(raw)},
    )
    assert response.status_code == 400
