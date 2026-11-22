"""Real authenticated issue confirmation, dispatch and physical process receipts."""

import json

import pytest
import test_native_workflow
from api import create_app
from fastapi.testclient import TestClient
from native_workflow import NativeWorkflow
from tianxuan_core import Tianxuan

fixture = test_native_workflow.fixture


def install_stage_probe(workflow, initial, folder, *, stage):
    """Install a local fixture plan. All process output stays in the test directory."""
    probe = folder / "stage_probe.py"
    probe.write_text(
        "import json, os, pathlib\n"
        "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
        "grant = json.loads(context.read_text(encoding='utf-8'))['stage_authorization']\n"
        "with open(os.environ['PROBE_CALLS'], 'a', encoding='utf-8') as log:\n"
        "    print(json.dumps(dict(execution=context.parent.name, grant=grant)), file=log)\n"
        "pathlib.Path('a/output').write_text('fixture output', encoding='utf-8')\n",
        encoding="utf-8",
    )
    calls = folder / "stage_calls.jsonl"
    profile = workflow.worker.profiles["local"]
    profile["argv"] = [profile["argv"][0], str(probe)]
    profile["env"]["PROBE_CALLS"] = str(calls)
    plan = dict(
        selected={"a": initial["a"]},
        writes={"a": ["output"]},
        dependencies={},
        profile="local",
        product="fixture",
        checks=["check"],
        mandate="installed-test-plan",
        stage=stage,
    )
    workflow.installed_plan = lambda actor, issue: dict(plan)
    return calls, plan


class StageHost:
    def detail(self, issue):
        return (
            self.client
            .get(f"/api/v1/issues/by-number/{issue['number']}/detail", params={"project": "studio"})
            .raise_for_status()
            .json()
        )

    def target(self, issue, stage="preview", criteria="preview visible", revision=0):
        return (
            self.client
            .put(
                f"/api/v1/issues/{issue['id']}/task-target",
                params={"project": "studio"},
                json=dict(document_id=self.doc, version=1, expected_revision=revision, stage=stage, criteria=criteria),
            )
            .raise_for_status()
            .json()
        )

    def confirm(self, issue, status="confirmed", **overrides):
        detail = self.detail(issue)
        return self.client.put(
            f"/api/v1/issues/{issue['id']}/task-confirmation",
            params={"project": "studio"},
            json=dict(
                document_id=self.doc,
                version=1,
                target_revision=detail["task_target"]["revision"],
                issue_revision=detail["revision"],
                expected_revision=detail["task_confirmation"]["revision"],
                status=status,
            )
            | overrides,
        )

    def api(self, operation, **payload):
        return self.client.post("/api/v1/native/workflow/" + operation, json=payload)

    def reserve(self, key):
        row = self.api("status", key=key).raise_for_status().json()
        revision = json.loads(row["task"])["source"]["revision"]
        return self.api(
            "reserve",
            event="stage-test",
            assignment=dict(ticket=key, sourceSnapshot={"source": key, "revision": revision}, model={"id": "local"}),
        )

    def observations(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def host(fixture):
    w, actor, _, _, initial, folder = fixture
    h = StageHost()
    h.workflow, h.actor = w, actor
    h.calls, h.plan = install_stage_probe(w, initial, folder, stage="preview")
    h.doc = w.domain.create_doc(actor, "Stage design", "Program\n\nAnimate")["id"]
    w.domain.design_signoff(actor, h.doc, 1, "Independent visible previews")
    h.issues = w.domain.split_design(
        actor,
        h.doc,
        1,
        "studio",
        [
            dict(paragraph=i, title=title, module_id="default", acceptance="visible")
            for i, title in enumerate(("Program", "Animate"), 1)
        ],
        "split",
    )
    headers = {"Authorization": "Bearer " + w.domain.issue_session(actor)}
    with TestClient(create_app(w.domain, native_store=w.worker.store, native_workflow=w), headers=headers) as client:
        h.client = client
        yield h


def test_signed_item_reaches_one_local_process(host, record_property):
    h = host
    first, second = h.issues
    assert h.api("authorize", issue=first["id"]).status_code == 409
    h.target(first)
    h.target(second, stage="delivery", criteria="delivery visible")
    # The signed v1 remains the task source after an independent v2 draft.
    h.workflow.domain.update_doc(h.actor, h.doc, "Later draft", 1)
    assert h.confirm(first, version=2).status_code == 409
    assert h.api("authorize", issue=first["id"]).status_code == 409
    confirmation = h.confirm(first).raise_for_status().json()
    assert h.detail(second)["task_confirmation"]["status"] == "pending"
    assert h.api("authorize", issue=second["id"]).status_code == 409
    for stage in (None, "delivery"):
        h.plan["stage"] = stage
        assert h.api("authorize", issue=first["id"]).status_code == 409
    h.plan["stage"] = "preview"
    assert h.observations() == []
    key = h.api("authorize", issue=first["id"]).raise_for_status().json()
    assert h.api("authorize", issue=first["id"]).json() == key
    assert h.api("inspect").json()["snapshot"]["ready"] == [key]
    assert h.reserve(key).raise_for_status().json() is True
    assert h.api("execute", key=key).raise_for_status().json()["state"] == "produced"
    assert h.api("execute", key=key).json()["state"] == "produced"
    assert h.api("revise", issue=first["id"], expected=key).json() == key
    h.plan["mandate"] = "another-installed-plan"
    assert h.api("revise", issue=first["id"], expected=key).status_code == 409
    row = h.api("status", key=key).raise_for_status().json()
    task = json.loads(row["task"])
    grant = task["source"]["definition"]["stage_authorization"]
    assert grant == {
        **{
            k: confirmation[k]
            for k in (
                "issue_id",
                "issue_revision",
                "document_id",
                "version",
                "target_revision",
                "stage",
                "responsible_user",
                "confirmed_by",
            )
        },
        "confirmation_revision": confirmation["revision"],
        "criteria": "preview visible",
    }
    assert h.observations() == [dict(execution=key, grant=grant)]
    with h.workflow.worker.store._connection() as db:
        closures = db.execute("SELECT execution,payload FROM native_worker_process_closures").fetchall()
        assert len(closures) == 1 and closures[0]["execution"] == key
        closed = json.loads(closures[0]["payload"])
        assert closed["exit_code"] == 0 and not closed["reasons"]
    record_property(
        "observation",
        json.dumps(
            dict(
                grant=grant,
                execution=key,
                profile=task["profile"],
                installation=task["installation"],
                candidate=json.loads(row["terminal"])["candidate"],
                physical_closure=closed,
                calls=len(h.observations()),
                sibling_calls=0,
            )
        ),
    )


@pytest.mark.parametrize("change", ["revoked", "reconfirmed", "target", "definition", "reassigned"])
def test_stale_reserved_ticket_never_launches(host, change, record_property):
    h = host
    issue = h.issues[0]
    h.target(issue)
    h.confirm(issue).raise_for_status()
    key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
    assert h.reserve(key).json() is True
    if change in {"revoked", "reconfirmed"}:
        h.confirm(issue, "revoked").raise_for_status()
        if change == "reconfirmed":
            h.confirm(issue).raise_for_status()
    elif change == "target":
        h.target(issue, revision=1, criteria="revised preview")
    elif change == "definition":
        current = h.detail(issue)
        h.workflow.domain.set_issue_classification(h.actor, issue["id"], "studio", "changed", [], current["type"], [])
    else:
        new = h.workflow.domain.add_member(h.actor, "other@example.invalid", "fixture-pass")["user_id"]
        h.workflow.domain.set_issue_assignee(h.actor, issue["id"], "studio", new, None)
        assert h.confirm(issue).status_code == 403
    confirmation = h.detail(issue)["task_confirmation"]
    if change != "reconfirmed":
        assert confirmation["status"] in {"pending", "revoked"}
    assert h.api("execute", key=key).status_code == 409
    assert h.api("status", key=key).json()["state"] == "stopped"
    assert h.api("inspect").json()["environment"]["active"] == []
    assert h.observations() == []
    assert not (h.workflow.worker.root / key).exists()
    with h.workflow.worker.store._connection() as db:
        closures = db.execute("SELECT count(*) FROM native_worker_process_closures").fetchone()[0]
        assert closures == 0
    record_property(
        "observation",
        json.dumps(
            dict(change=change, execution=key, status=confirmation["status"], calls=0, physical_closures=closures)
        ),
    )


def test_private_origin_cannot_fall_back_to_ordinary_issue(host):
    h = host
    issue = h.issues[0]
    h.target(issue)
    h.confirm(issue).raise_for_status()
    key = h.api("authorize", issue=issue["id"]).raise_for_status().json()
    h.workflow.domain.set_visibility(h.actor, h.doc, "private")
    member = h.workflow.domain.add_member(h.actor, "second@example.invalid", "fixture-pass")["user_id"]
    h.client.headers["Authorization"] = "Bearer " + h.workflow.domain.issue_session(member)
    assert h.detail(issue)["design_source"] is None
    assert h.api("authorize", issue=issue["id"]).status_code == 403
    assert h.api("status", key=key).status_code == 403
    assert h.observations() == []


def test_reassigned_confirmation_replaces_old_reservation_after_restart(host):
    h = host
    issue = h.issues[0]
    h.target(issue)
    h.confirm(issue).raise_for_status()
    previous = h.api("authorize", issue=issue["id"]).raise_for_status().json()
    assert h.reserve(previous).json() is True
    new = h.workflow.domain.add_member(h.actor, "assignee@example.invalid", "fixture-pass")["user_id"]
    h.workflow.domain.set_issue_assignee(h.actor, issue["id"], "studio", new, None)
    h.client.headers["Authorization"] = "Bearer " + h.workflow.domain.issue_session(new)
    confirmation = h.confirm(issue).raise_for_status().json()
    assert confirmation["confirmed_by"] == new
    # Reopen the persisted issue and task databases in another coordinator.
    w = h.workflow
    domain = Tianxuan(str(h.calls.parent / "domain.sqlite"))
    try:
        restored = NativeWorkflow(
            domain, w.worker, w.runner, w.release, w.authorize, catalog=w.catalog, installed_plan=w.installed_plan
        )
        headers = {"Authorization": "Bearer " + domain.issue_session(h.actor)}
        with TestClient(
            create_app(domain, native_store=w.worker.store, native_workflow=restored), headers=headers
        ) as client:
            h.client = client
            assert h.detail(issue)["task_confirmation"] == confirmation
            key = h.api("revise", issue=issue["id"], expected=previous).raise_for_status().json()
            assert key != previous
            assert h.api("execute", key=previous).json()["state"] == "superseded"
            assert h.observations() == []
            assert h.reserve(key).json() is True
            assert h.api("execute", key=key).raise_for_status().json()["state"] == "produced"
            (observation,) = h.observations()
            assert observation["execution"] == key and observation["grant"]["confirmed_by"] == new
    finally:
        domain.db.close()
