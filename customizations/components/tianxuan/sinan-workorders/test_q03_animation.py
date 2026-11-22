"""One real local Tianxuan animation issue, from manual edit to a signed preview stop."""

import base64
import json
import os
import sys
import time
from pathlib import Path

import pytest
import test_native_stage_admission
from api import create_app
from test_native_judgment_branches import EDITOR_TESTS, native_approve

CRITERIA = "Preview only. At 24 fps retime the approach before frame 12, keep frames 12–24 including the manual landing (250,96)."
fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host
RETIME = {"action": "halve_approach", "protected_frame": 12, "candidate_clip": "Landing"}


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def choose_retime(binding):
    # For the first receipt the active Codex operator chooses from the real signed
    # input. Further runs replay the same command on a newly authorized fixture.
    handoff = os.environ.get("Q03_LIVE_HANDOFF")
    if not handoff:
        return binding | RETIME, "recorded command replay"
    folder = Path(handoff)
    write_json(folder / "input.json", binding)
    deadline = time.monotonic() + 180
    while not (folder / "decision.json").exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    decision = json.loads((folder / "decision.json").read_text(encoding="utf-8-sig"))
    assert decision == binding | RETIME, "Command or signed input changed"
    return decision, "active Codex operator on the signed revision"


@pytest.mark.skipif(not os.environ.get("Q03_TEST_EDITOR"), reason="requires an isolated native Godot editor")
def test_q03_manual_animation_continuation(host, fixture, monkeypatch, tmp_path):
    from editor_test_isolation import copy_editor
    from run_q03_animation import digest, export_comparison, probe
    from run_workbench_offline_document import serve

    h = host
    w, actor, tenant, _, initial, _ = fixture
    binary = Path(os.environ["Q03_TEST_EDITOR"]).resolve(strict=True)
    monkeypatch.delenv("GONGGONG_WORKSPACE", raising=False)
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", tenant)
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://fixture.invalid")
    editor = copy_editor(binary, tmp_path / "animation-editor")
    baseline, _ = probe(editor, tmp_path, "initial")
    manual, edit = probe(editor, tmp_path, "manual", baseline)
    assert manual != baseline

    # The original requirement and the signed stage share a real issue in this
    # private service. A developer's machine and production account are never used.
    h.doc = w.domain.create_doc(actor, "Q03 · Landing", CRITERIA)["id"]
    w.domain.design_signoff(actor, h.doc, 1, "Frame 24 was edited by the sample operator")
    (issue,) = w.domain.split_design(
        actor,
        h.doc,
        1,
        "studio",
        [dict(paragraph=1, module_id="default", title="Q03 · Animate the landing", acceptance=CRITERIA)],
        "q03-split",
    )
    issue_id = issue["id"]
    url = f"/api/v1/issues/{issue_id}/work"
    asset = dict(kind="concept", module="a", path="motion.tscn")

    def save_revision(base, content, request):
        change = dict(module="a", base=base, reads=None, edits={"motion.tscn": base64.b64encode(content).decode()})
        return (
            h.client
            .post("/api/v1/native/batches", json=dict(request_key=request, changes=[change]))
            .raise_for_status()
            .json()["revisions"]["a"]
        )

    def submit(revision, expected):
        snapshot = (
            h.client
            .post(
                url + "/submit_asset",
                json=asset | dict(revision=revision, expected_version=expected, call_id=f"asset-{expected}"),
            )
            .raise_for_status()
            .json()
        )
        return snapshot["assets"]["concept"]

    original = save_revision(initial["a"], baseline, "q03-original")
    hand_revision = save_revision(original, manual, "q03-manual-save")
    assert submit(hand_revision, 0)["digest"] == digest(manual)
    helper = EDITOR_TESTS / "run_q03_animation.py"
    command = [sys.executable, str(helper)]
    args = [str(editor), str(tmp_path), digest(manual)]
    plan_file = tmp_path / "approved-action.json"
    producer = w.worker.profiles["local"]
    producer.update(argv=command + ["produce"] + args, timeout=60)
    producer["env"]["Q03_DECISION_FILE"] = str(plan_file)
    checker = w.runner._registry["check"]
    checker.update(argv=command + ["check"] + args, timeout=60, toolchain=digest(helper.read_bytes()))
    h.plan.update(selected={"a": hand_revision}, writes={"a": ["motion.tscn"]}, stage_criteria=CRITERIA)
    h.target(issue, criteria=CRITERIA)
    assert h.api("authorize", issue=issue_id).status_code == 409
    h.confirm(issue).raise_for_status()
    key = h.api("authorize", issue=issue_id).raise_for_status().json()
    task = json.loads(h.api("status", key=key).raise_for_status().json()["task"])
    signed = task["source"]["definition"]["stage_authorization"]
    assert task["selected"]["a"] == hand_revision
    binding = dict(
        issue=issue_id,
        execution=key,
        source_revision=hand_revision,
        source_sha256=digest(manual),
        criteria=signed["criteria"],
        stage=signed["stage"],
        manual_edit=edit,
    )
    action, command_source = choose_retime(binding)
    write_json(plan_file, action)
    assert h.reserve(key).raise_for_status().json() is True
    terminal = h.api("execute", key=key).raise_for_status().json()
    assert terminal["state"] == "produced", terminal
    ai_revision = terminal["modules"]["a"]
    assert terminal["exit_code"] == 0 and ai_revision != hand_revision
    submitted = submit(ai_revision, 1)
    target = f"/api/v1/issues/by-number/{issue['number']}/artifacts"
    downloads = h.client.get(target, params={"project": "studio"}).raise_for_status().json()["artifacts"]
    assert [r["revision"] for r in downloads] == [ai_revision, hand_revision]

    def download(version):
        return h.client.get(f"{target}/{version}", params={"project": "studio"}).raise_for_status().content

    candidate = download(2)
    assert download(1) == manual and digest(candidate) == submitted["digest"]
    replayed, replay = probe(editor, tmp_path, "replay", candidate)
    assert replayed == candidate
    for source_track, candidate_track in zip(replay["keys"]["Walk"], replay["keys"]["Landing"], strict=True):
        assert [k[0] for k in source_track] == [0, 6, 12, 24]
        assert [k[0] for k in candidate_track] == [0, 3, 12, 24]
        assert [k[1:] for k in source_track] == [k[1:] for k in candidate_track]
    account_app = create_app(w.domain, native_store=w.worker.store, native_workflow=w)
    with serve(account_app, 0) as port:
        # Test-account selection exercises the real editor judgment surface.
        approval = native_approve(
            tmp_path, binary, f"http://127.0.0.1:{port}", w.domain.issue_session(actor), ai_revision
        )
    state = h.client.get(url).raise_for_status().json()
    selected = next(row for row in state["creative_judgments"] if row["revision"] == ai_revision)
    assert selected["decision"] == "approved" and selected["digest"] == digest(candidate)
    stage = h.api("verify-stage", key=key).raise_for_status().json()
    assert stage["state"] == "stage-reached", stage
    assert stage["modules"]["a"] == ai_revision and stage["candidate"] == terminal["candidate"]
    assert stage["authorization"]["stage"] == "preview" and stage["checks"]["check"]["outcome"] == "passed"
    assert h.detail(issue)["execution_progress"]["state"] == "stage-reached"
    denied = h.api("publish", key=key, channel="stable", expected=None)
    assert denied.status_code == 409 and "limited to its authorized stage" in denied.json()["detail"]
    approved_bytes = (
        h.client.get(url + "/approved-asset", params=asset | dict(revision=ai_revision)).raise_for_status().content
    )
    assert approved_bytes == candidate

    if output := os.environ.get("Q03_SAMPLE_DIR"):
        dest = Path(output)
        dest.mkdir(parents=True, exist_ok=True)
        for name, data in [("original", baseline), ("manual", manual), ("candidate", candidate)]:
            (dest / (name + ".tscn")).write_bytes(data)
        export_comparison(replay["frames"], dest)
        engine = binary.with_name(binary.name.replace(".console.exe", ".exe"))
        write_json(
            dest / "run.json",
            dict(
                issue=issue_id,
                project="studio",
                number=issue["number"],
                command_source=command_source,
                action=action,
                original=dict(revision=original, sha256=digest(baseline)),
                manual=dict(revision=hand_revision, **edit),
                candidate=dict(revision=ai_revision, sha256=digest(candidate)),
                editor_sha256=digest(engine.read_bytes()),
                editor_launcher_sha256=digest(binary.read_bytes()),
                replay=replay,
                artifact_readback=downloads,
                example_fixture_account_decision=selected,
                editor_decision=approval,
                stage=stage,
                checked_candidate=terminal["candidate"],
                exit_code=terminal["exit_code"],
                publish_guard=denied.json()["detail"],
                comparison_gif_sha256=digest((dest / "comparison.gif").read_bytes()),
            ),
        )


@pytest.mark.skipif(not os.environ.get("Q03_TEST_EDITOR"), reason="requires an isolated native Godot editor")
def test_q03_reopen_archived_sample(tmp_path, monkeypatch):
    from editor_test_isolation import copy_editor
    from run_q03_animation import digest, probe

    sample = EDITOR_TESTS.parents[1] / "data-collection/plan1-q03-sample"
    run = json.loads((sample / "run.json").read_text(encoding="utf-8"))
    for name in ("original", "manual", "candidate"):
        assert digest((sample / (name + ".tscn")).read_bytes()) == run[name]["sha256"]
    assert digest((sample / "comparison.gif").read_bytes()) == run["comparison_gif_sha256"]
    monkeypatch.delenv("GONGGONG_WORKSPACE", raising=False)
    editor = copy_editor(Path(os.environ["Q03_TEST_EDITOR"]), tmp_path / "editor")
    content = (sample / "candidate.tscn").read_bytes()
    restored, replay = probe(editor, tmp_path, "replay", content)
    assert restored == content
    for field in ("keys", "frames", "landing", "restored_cursor"):
        assert replay[field] == run["replay"][field]
    for clip in ("Walk", "Landing"):
        assert replay["replay"][clip]["label"] == run["replay"]["replay"][clip]["label"]
