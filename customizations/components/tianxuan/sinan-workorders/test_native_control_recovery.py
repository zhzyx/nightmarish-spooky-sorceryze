"""A lost execute reply must preserve the user's pause across a fresh dispatcher."""

import json

import pytest
from starlette.responses import JSONResponse
from test_native_run_controls import command
from test_native_stage_admission import host  # noqa: F401
from test_native_stage_stop import drive, install_preview, signed
from test_native_workflow import fixture  # noqa: F401
from tianxuan_core import PermissionDenied


@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_run_receipt_is_stable_while_actions_follow_owner(host, role, record_property):  # noqa: F811
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    assert h.reserve(key).raise_for_status().json() is True
    domain = h.workflow.domain
    invite = domain.create_invite(h.actor, f"{role}@example.invalid", role)
    other = domain.accept_invite(invite["code"], "password")["user_id"]
    owner_view = h.detail(issue)
    other_view = h.workflow.issue_detail(other, "studio", issue["number"])
    assert owner_view["execution_control_actions"] == ["pause", "cancel"]
    assert other_view["execution_control_actions"] == []
    assert other_view["execution_progress"] == owner_view["execution_progress"]
    assert h.workflow.status(other, key) == h.workflow.status(h.actor, key)
    with pytest.raises(PermissionDenied):
        command(h.workflow, other, issue, key, "pause")
    assert not h.observations()
    record_property(
        "observation",
        json.dumps({
            "execution": key,
            "reader_role": role,
            "owner_actions": owner_view["execution_control_actions"],
            "reader_actions": other_view["execution_control_actions"],
        }),
    )


def test_lost_paused_reply_preserves_original_output(host, monkeypatch, record_property):  # noqa: F811
    h = host
    issue = install_preview(h)
    key = signed(h, issue)
    run = h.workflow.worker.run
    app = h.client.app
    operations = []

    def pause_after_tool(contract, execution):
        output = run(contract, execution)
        decision, _ = command(h.workflow, h.actor, issue, key, "pause")
        assert decision["control"]["state"] == "pausing"
        return output

    async def lose_execute_reply(scope, receive, send):
        operation = scope.get("path", "").rsplit("/", 1)[-1]
        operations.append(operation)
        if operation != "execute":
            return await app(scope, receive, send)
        replies = []

        async def withhold(message):
            replies.append(message)

        await app(scope, receive, withhold)
        assert replies[0]["status"] == 200
        await JSONResponse({"detail": "reply unavailable"}, status_code=503)(scope, receive, send)

    monkeypatch.setattr(h.workflow.worker, "run", pause_after_tool)
    monkeypatch.setattr(h.client, "app", lose_execute_reply)
    first = drive(h)["result"]
    assert not first["errors"] and not first.get("stages") and not first["deliveries"]
    (item,) = first["results"]
    assert item["state"] == item["receipt"]["controlState"] == "paused"
    (recovery,) = first["recoveries"]
    assert recovery["id"] == key and recovery["known_effects"]["exit_code"] == 0
    candidate = recovery["known_effects"]["candidate"]
    assert candidate and operations[operations.index("execute") + 1] == "execution-readback"

    command(h.workflow, h.actor, issue, key, "resume")
    second = drive(h)
    assert second["calls"].count("execute") == 0 and second["calls"].count("verify-stage") == 1
    assert second["result"]["stages"][0]["candidate"] == candidate
    assert operations.count("execute") == 1
    assert [item["execution"] for item in h.observations()] == [key]
    record_property("observation", json.dumps({"execution": key, "candidate": candidate, "starts": h.observations()}))
