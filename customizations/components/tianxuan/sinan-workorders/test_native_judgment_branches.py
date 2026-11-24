"""Run the actual Sinan receiver while the animation drafts await a human signature."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import test_native_stage_admission
from api import create_app
from native_execution_host import WorkflowService

fixture = test_native_stage_admission.fixture
host = test_native_stage_admission.host
EDITOR_TESTS = Path(__file__).resolve().parents[4] / "tests/editor"
sys.path.insert(0, str(EDITOR_TESTS))


def wait_until(check, receiver):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if check():
            return
        if receiver.poll() is not None:
            raise AssertionError(receiver.communicate())
        time.sleep(0.04)
    raise AssertionError("Missing receiver or physical worker observation")


def native_approve(root, binary, url, token, revision):
    from editor_test_isolation import copy_editor
    from run_unified_settings_native import sanitized_environment

    project = root / "editor-project"
    project.mkdir()
    engine = copy_editor(binary, root / "editor")
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="H06"\n')
    for script in ("workbench_issue_detail.gd", "workbench_judgment_branches.gd"):
        shutil.copyfile(EDITOR_TESTS / script, project / script)
    env = sanitized_environment(root) | dict(
        TIANXUAN_API=url, TIANXUAN_TOKEN=token, TIANXUAN_PROJECT="studio", H06_REVISION=revision
    )
    run = subprocess.run(
        [engine, "--headless", "--editor", "--path", project, "--script", "res://workbench_judgment_branches.gd"],
        cwd=project,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=40,
    )
    output = run.stdout + run.stderr
    assert token not in output
    assert run.returncode == 0 and "SCRIPT ERROR" not in output, output[-4500:]
    (receipt,) = [
        line.removeprefix("H06_DECISION=") for line in output.splitlines() if line.startswith("H06_DECISION=")
    ]
    assert revision in receipt
    executable = binary.with_name(binary.name.replace(".console.exe", ".exe"))
    with executable.open("rb") as stream:
        return {"editor_sha256": hashlib.file_digest(stream, "sha256").hexdigest(), "receipt": receipt, "exit": 0}


def test_program_runs_during_choice_and_only_selected_animation_starts(host, fixture, monkeypatch, record_property):
    from run_workbench_offline_document import serve

    h = host
    w, actor, tenant, _, initial, root = fixture
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", tenant)
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://fixture.invalid")
    monkeypatch.setenv("GONGGONG_WORKSPACE", "")
    h.doc = w.domain.create_doc(actor, "Bridge", "Program\n\nAnimation A\n\nAnimation B")["id"]
    w.domain.design_signoff(actor, h.doc, 1, "Choose the animation")
    titles = ["Program", "Animation A", "Animation B"]
    program, first, second = w.domain.split_design(
        actor,
        h.doc,
        1,
        "studio",
        [dict(paragraph=i, module_id="default", title=t, acceptance="visible") for i, t in enumerate(titles, 1)],
        "split-branches",
    )
    source = w.domain.create_issue(actor, "Decide animation", project="studio")["id"]
    h.plan["stage_criteria"] = "use the selected draft if present"
    profile = w.worker.profiles["local"]
    Path(profile["argv"][1]).write_text(
        "import hashlib, json, os, pathlib\n"
        "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
        "asset = pathlib.Path('b/draft'); data = asset.read_bytes() if asset.is_file() else b'program'\n"
        "pathlib.Path('a/output').write_bytes(data)\n"
        "with open(os.environ['PROBE_CALLS'], 'a') as log:\n"
        "    print(json.dumps(dict(execution=context.parent.name, pid=os.getpid(),"
        " sha256=hashlib.sha256(data).hexdigest())), file=log)\n",
        encoding="utf-8",
    )
    spec = w.runner._registry["check"]
    spec["argv"] = [
        spec["argv"][0],
        "-c",
        "import os,pathlib; p=pathlib.Path(os.environ['DUOBAO_INPUT']); "
        "asset=p/'b/draft'; assert (p/'a/output').read_bytes()==(asset.read_bytes() if asset.is_file() else b'program')",
    ]
    work = f"/api/v1/issues/{source}/work"
    revisions = []
    prior = initial["b"]
    for index, data in enumerate([b"keyframes A", b"keyframes B"]):
        revision = w.worker.store.submit(
            tenant,
            actor,
            f"draft-{index}",
            [
                dict(module="b", base=prior, reads=None, edits={"draft": data}),
            ],
        )["revisions"]["b"]
        prior = revision
        revisions.append(revision)
        h.client.post(
            work + "/submit_asset",
            json=dict(
                kind="concept",
                module="b",
                path="draft",
                revision=revision,
                expected_version=index,
                call_id=f"submit-{index}",
            ),
        ).raise_for_status()

    for version, issue in enumerate((first, second), 1):
        path = f"/api/v1/issues/{issue['id']}/work/flow/dependencies"
        edge = dict(
            dependencies=[source], submission_versions={source: version}, expected_version=0, call_id=f"link-{version}"
        )
        saved = h.client.post(path, json=edge).raise_for_status().json()
        assert saved["dependencies"][0]["judgment"]["revision"] == revisions[version - 1]
        # Existing I04 clients editing only issue IDs retain exact creative bindings.
        old_client = dict(dependencies=[source], expected_version=1, call_id=f"i04-{version}")
        assert h.client.post(path, json=old_client).raise_for_status().json()["dependencies"] == saved["dependencies"]
    for issue in (program, first, second):
        h.target(issue, criteria=h.plan["stage_criteria"])
        h.confirm(issue).raise_for_status()
    for issue in (first, second):
        assert h.api("authorize", issue=issue["id"]).status_code == 409
    program_key = h.api("authorize", issue=program["id"]).raise_for_status().json()
    scoped = WorkflowService(w, actor, lambda: None, [second["id"]])
    assert [b["issue"] for b in scoped.call("inspect", {})["judgment_branches"]] == [second["id"]]
    before = h.api("inspect").raise_for_status().json()["judgment_branches"]
    assert {b["issue"] for b in before} == {first["id"], second["id"]}

    def decision(index, verdict, version):
        return dict(
            kind="concept",
            module="b",
            path="draft",
            revision=revisions[index],
            submission_version=index + 1,
            expected_version=version,
            decision=verdict,
            call_id=verdict,
        )

    native = None
    token = w.domain.issue_session(actor)
    app = create_app(w.domain, native_store=w.worker.store, native_workflow=w)
    with serve(app, 0) as port:
        url = f"http://127.0.0.1:{port}"
        driver = [shutil.which("node"), str(Path(__file__).with_name("native_dispatch.mjs"))]
        env = {k: v for k, v in os.environ.items() if k.upper() in {"WINDIR", "SYSTEMROOT"}}
        env.update(NATIVE_SERVICE_TOKEN=token, NATIVE_SERVICE_URL=url)
        with subprocess.Popen(driver, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as receiver:
            try:
                wait_until(lambda: h.detail(program)["execution_progress"]["state"] == "stage-reached", receiver)
                assert [item["execution"] for item in h.observations()] == [program_key]
                assert not h.detail(first)["execution_progress"] and not h.detail(second)["execution_progress"]
                if binary := os.environ.get("H06_TEST_EDITOR"):
                    native = native_approve(root, Path(binary), url, token, revisions[0])
                else:
                    h.client.post(work + "/decide", json=decision(0, "approved", 2)).raise_for_status()
                # No additional dispatch request between the signature and process closure.
                wait_until(
                    lambda: (h.detail(first)["execution_progress"] or {}).get("state") == "stage-reached", receiver
                )
                assert len(h.observations()) == 2 and not h.detail(second)["execution_progress"]
                with w.domain._connection_lock:
                    signed = w.domain.db.execute(
                        "SELECT call_id,payload_json FROM tool_receipts WHERE tool='work.decide' AND actor_id=? AND "
                        "json_extract(payload_json,'$.issue_id')=?",
                        (actor, source),
                    ).fetchone()
                replay = json.loads(signed["payload_json"])
                del replay["issue_id"]
                replay["call_id"] = signed["call_id"]
                h.client.post(work + "/decide", json=replay).raise_for_status()
                h.client.post(work + "/decide", json=decision(1, "changes_requested", 3)).raise_for_status()
                output, errors = receiver.communicate(timeout=15)
                assert receiver.returncode == 0 and not errors
            finally:
                if receiver.poll() is None:
                    receiver.kill()
                    # Release fixture observers even if an assertion interrupted the driver.
                    for version in (1, 2):
                        w.judgment_changed(source, version)
        result = json.loads(output)
        assert not result["errors"], result
        after = json.loads(subprocess.check_output(driver, env=env, text=True, timeout=15))
        assert not after["results"] and not after["errors"]
    key = h.detail(first)["execution_progress"]["id"]
    status = w.status(actor, key)
    contract = json.loads(status["task"])
    receipt = contract["judgment_inputs"][source]
    assert receipt["submission_version"] == 1 and receipt["actor"] == actor and receipt["decision"] == "approved"
    assert contract["selected"]["b"] == receipt["revision"] == revisions[0]
    calls = h.observations()
    assert [r["execution"] for r in calls] == [program_key, key] and calls[1]["sha256"] == receipt["digest"]
    assert not h.detail(second)["execution_progress"]
    with w.worker.store._connection() as db:
        exits = {
            r["execution"]: json.loads(r["payload"])["exit_code"]
            for r in db.execute("SELECT execution,payload FROM native_worker_process_closures")
        }
    assert exits == {program_key: 0, key: 0}
    record_property(
        "h06",
        json.dumps(
            dict(
                program=program_key,
                successor=key,
                decision=receipt,
                drafts=revisions,
                worker_starts=calls,
                physical_exits=exits,
                candidate=json.loads(status["terminal"])["candidate"],
                stage=status["stage_result"],
                native=native,
                replay_starts=0,
                unselected_starts=0,
            ),
            ensure_ascii=False,
        ),
    )


def test_receiver_reopens_approved_branch_and_rejects_obsolete_binding(host, fixture):
    h = host
    w, actor, tenant, _, initial, _ = fixture
    successor = h.issues[0]
    source = w.domain.create_issue(actor, "Review a pose", project="studio")["id"]
    flow = f"/api/v1/issues/{successor['id']}/work/flow/dependencies"
    work = f"/api/v1/issues/{source}/work"
    asset = dict(kind="model", module="b", revision=initial["b"], path="output")
    for version in range(2):
        h.client.post(
            work + "/submit_asset", json={**asset, "expected_version": version, "call_id": f"submit-{version}"}
        ).raise_for_status()
    edge = dict(dependencies=[source], submission_versions={source: 1}, expected_version=0, call_id="first")
    h.client.post(flow, json=edge).raise_for_status()
    h.target(successor)
    h.confirm(successor).raise_for_status()
    (old,) = h.api("inspect").raise_for_status().json()["judgment_branches"]
    new_edge = {**edge, "submission_versions": {source: 2}, "expected_version": 1, "call_id": "rebind"}
    h.client.post(flow, json=new_edge).raise_for_status()
    decision = {
        **asset,
        "submission_version": 1,
        "decision": "approved",
        "expected_version": 2,
        "call_id": "choose-first",
    }
    h.client.post(work + "/decide", json=decision).raise_for_status()
    assert h.api("admit-judgment", issue=successor["id"], binding=old["binding"]).status_code == 409
    (pending,) = h.api("inspect").raise_for_status().json()["judgment_branches"]
    assert pending["pending"] == [[source, 2]] and pending["binding"] != old["binding"]
    h.client.post(
        work + "/decide", json={**decision, "submission_version": 2, "expected_version": 3, "call_id": "choose-second"}
    ).raise_for_status()
    # Even identical native bytes cannot rebind an older event to the newly selected submission.
    assert h.api("admit-judgment", issue=successor["id"], binding=old["binding"]).status_code == 409
    (ready,) = h.api("inspect").raise_for_status().json()["judgment_branches"]
    assert ready["binding"] == pending["binding"] and not ready["pending"]
    for _ in range(2):
        key = h.api("admit-judgment", issue=successor["id"], binding=ready["binding"]).raise_for_status().json()
        assert json.loads(w.status(actor, key)["task"])["judgment_inputs"][source]["submission_version"] == 2
    assert not h.api("inspect").raise_for_status().json()["judgment_branches"]
    assert h.observations() == []
