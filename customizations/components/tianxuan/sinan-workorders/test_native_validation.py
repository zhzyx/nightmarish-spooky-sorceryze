"""Exercise object revision validation through authenticated workbench API reads."""

import base64
import json

import pytest
import test_native_stage_stop

fixture = test_native_stage_stop.fixture
host = test_native_stage_stop.host


def save(h, request, revision, content):
    return (
        h.client
        .post(
            "/api/v1/native/batches",
            json={
                "request_key": request,
                "changes": [
                    {
                        "module": "a",
                        "base": revision,
                        "reads": None,
                        "edits": {"preview.svg": base64.b64encode(content.encode()).decode()},
                    }
                ],
            },
        )
        .raise_for_status()
        .json()["revisions"]["a"]
    )


@pytest.mark.parametrize("color,outcome", [("blue", "passed"), ("red", "failed")])
def test_validation_after_edit(host, color, outcome, record_property):
    h = host
    issue = test_native_stage_stop.install_preview(h, color=color)
    content = test_native_stage_stop.PREVIEW.replace("blue", color)
    initial = save(h, "before-check", h.plan["selected"]["a"], content)
    h.plan["selected"] = {"a": initial}
    key = test_native_stage_stop.signed(h, issue)
    url = f"/api/v1/native/workflow/tasks/{key}/validation/a/preview.svg"

    def read():
        return h.client.get(url).raise_for_status().json()

    assert read()["current"]["state"] == "pending"
    assert h.reserve(key).raise_for_status().json()
    assert h.api("execute", key=key).raise_for_status().json()["state"] == "produced"
    validated = h.api("verify-stage", key=key).raise_for_status().json()
    checked = read()
    assert checked["current"]["revision"] == initial and checked["current"]["state"] == outcome
    (receipt,) = checked["receipts"]
    assert receipt["revision"] == initial and receipt["sha256"] == checked["current"]["sha256"]
    assert receipt["candidate"] == validated["candidate"] and receipt["tool"] == "check"
    assert receipt["outcome"] == outcome
    assert receipt["result_location"]["evidence"] == validated["checks"]["check"]["evidence"]
    assert len(receipt["result_location"]["log_sha256"]) == 64
    edited = save(h, "after-check", initial, content.replace("12", "8"))
    after = read()
    assert after["current"]["revision"] == edited and after["current"]["sha256"] != checked["current"]["sha256"]
    assert after["current"]["state"] == "pending" and after["current"]["checks"] == {"check": "pending"}
    assert after["receipts"] == [receipt]
    assert h.client.get(url.replace("preview.svg", "outside.txt")).status_code == 403
    foreign = h.workflow.domain.register("foreign", "foreign@example.invalid", "password")["user_id"]
    token = h.workflow.domain.issue_session(foreign)
    assert h.client.get(url, headers={"Authorization": "Bearer " + token}).status_code in {403, 404}
    record_property("validation", json.dumps({"before_edit": checked, "after_edit": after}, ensure_ascii=False))
