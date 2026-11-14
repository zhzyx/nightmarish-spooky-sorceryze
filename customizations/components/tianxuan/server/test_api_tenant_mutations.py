"""ASGI coverage of domain scope rejection and unchanged HTTP error mappings."""

from __future__ import annotations

import pytest
from api import create_app
from fastapi.testclient import TestClient
from test_tenant_mutations import scenario as scenario


def requests(s):
    _, _, _, members, doc, req, issue, comment = s
    base = "/api/v1"
    return {
        "update": ("PATCH", f"{base}/docs/{doc['id']}", {"body_md": "changed", "expected_version": 1}),
        "patch": (
            "POST",
            f"{base}/docs/{doc['id']}/patch",
            {"expected_version": 1, "patches": [{"find": "original", "replace": "changed"}]},
        ),
        "merge": (
            "POST",
            f"{base}/docs/{doc['id']}/merge",
            {"expected_version": 1, "base_md": "original", "local_md": "changed"},
        ),
        "visibility": ("PATCH", f"{base}/docs/{doc['id']}/visibility", {"visibility": "private"}),
        "share": ("POST", f"{base}/docs/{doc['id']}/shares", {"user_id": members["a_viewer"], "permission": "write"}),
        "unshare": ("DELETE", f"{base}/docs/{doc['id']}/shares/{members['a_viewer']}", None),
        "comment": ("POST", f"{base}/docs/{doc['id']}/comments", {"body": "changed"}),
        "resolve": ("PATCH", f"{base}/comments/{comment['id']}", {"resolved": True}),
        "plan": ("POST", f"{base}/requirements/{req['id']}/tickets", {"tickets": [{"title": "child"}]}),
        "transition": ("PATCH", f"{base}/issues/{issue['id']}", {"to_status": "in-progress"}),
        "issue_comment": ("POST", f"{base}/issues/{issue['id']}/comments", {"body": "changed"}),
        "role": ("PATCH", f"{base}/users/{members['a_viewer']}/role", {"role": "editor"}),
    }


@pytest.mark.parametrize(
    "name",
    [
        "update",
        "patch",
        "merge",
        "visibility",
        "share",
        "unshare",
        "comment",
        "resolve",
        "plan",
        "transition",
        "issue_comment",
        "role",
    ],
)
@pytest.mark.parametrize("identity,expected", [("foreign", 404), ("missing", 404), ("absent", 400), ("owner", 200)])
def test_http_scope_mutations(scenario, name, identity, expected):
    tx, a, b, *_ = scenario
    headers = {"X-Actor": {"foreign": b["user_id"], "missing": "missing", "owner": a["user_id"]}.get(identity, "")}
    method, path, payload = requests(scenario)[name]
    before = list(tx.db.iterdump())
    with TestClient(create_app(tx)) as client:
        response = client.request(method, path, headers=headers, json=payload)
    assert response.status_code == expected, response.text
    if expected != 200:
        assert list(tx.db.iterdump()) == before
        assert not tx.db.in_transaction


def test_read_boundary_unchanged(scenario):
    tx, _, _, _, doc, *_ = scenario
    # Low-level public reads keep the explicitly supported prototype boundary.
    assert tx.get_doc(doc["id"])["body_md"] == "original"


def test_foreign_websocket_update_rejected(scenario):
    tx, _, b, _, doc, *_ = scenario
    before = list(tx.db.iterdump())
    with TestClient(create_app(tx)) as client:
        with client.websocket_connect(f"/api/v1/ws/docs/{doc['id']}?actor={b['user_id']}") as ws:
            assert ws.receive_json()["type"] == "snapshot"
            assert ws.receive_json()["type"] == "presence"
            ws.send_json({"type": "update", "body_md": "changed", "expected_version": 1})
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["code"] == "NotFound"
    assert list(tx.db.iterdump()) == before
