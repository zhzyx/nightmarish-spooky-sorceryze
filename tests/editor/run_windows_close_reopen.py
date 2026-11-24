"""Verify the Windows editor's normal exit and same-project recovery on one signed task."""

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def exercise(root, source, executable):
    # Import the server, fixtures and observers from the editor's candidate.
    sys.path.insert(0, str(source / "tests/editor"))
    import run_macos_registered_worker_close as close
    import run_workbench_project_reopen as reopen

    if os.name != "nt" or executable.name.endswith(".console.exe"):
        raise ValueError("Supply the GUI executable directly on Windows to identify the actual editor PID")
    checks = reopen.checks
    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Q04 Windows recovery"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    probe = project / "probe.gd"
    shutil.copyfile(source / "tests/editor/workbench_startup_judgments.gd", probe)
    layout = project / ".godot/editor/editor_layout.cfg"
    engine = reopen.copy_editor(executable, root / "engine")
    response, visible = root / "response", root / "queue-visible"

    with ExitStack() as stack:
        fixture = stack.enter_context(contextmanager(checks.fixture.__wrapped__)(root))
        workflow, actor, tenant, _, initial, _ = fixture
        h = stack.enter_context(contextmanager(checks.host.__wrapped__)(fixture))
        stack.enter_context(
            patch.dict(
                os.environ,
                TIANXUAN_AUTH_MODE="accounts",
                TIANXUAN_TENANT_ID=tenant,
                TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
            )
        )
        token = workflow.domain.issue_session(actor)
        url, requests = stack.enter_context(reopen.receiver(h, token, response))
        # On an assertion failure unblock only fixture workers before stopping
        # their loopback service. These callbacks run after all observations.
        stack.callback((root / "release").touch)
        stack.callback(visible.touch)
        issue = checks.install(h)
        profile = workflow.worker.profiles["local"]
        profile.update(restart_checkpoint="immutable-inputs", timeout=100)
        profile["env"]["Q05_SYNC"] = str(root)
        script = Path(profile["argv"][1])
        text = script.read_text(encoding="utf-8")
        insertion = "pathlib.Path('a/preview.svg')"
        assert text.count(insertion) == 1
        # Only the retry can write this witness. Keep it active while the editor
        # observes the focused row so elapsed time cannot masquerade as ordering.
        retry = """
else:
    (sync / "retry-started").write_text(str(os.getpid()))
    while not (sync / "queue-visible").exists():
        time.sleep(.025)
"""
        script.write_text(text.replace(insertion, close.PRODUCER + retry + insertion), encoding="utf-8")
        receive = stack.enter_context(
            patch.object(workflow.worker.intake, "receive", wraps=workflow.worker.intake.receive)
        )
        key = checks.stage.signed(h, issue)
        before = checks.snapshot(h, key)
        assert before["state"] == "ready"
        confirmed = h.detail(issue)["task_confirmation"]

        def editor_view(**options):
            return reopen.editor(
                engine,
                project,
                url,
                token,
                {"R08_FIXTURE": json.dumps(dict(actor=actor, **options))},
                result_prefixes=("R08_NATIVE=",),
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(editor_view, phase="save", response=str(root / "close"), supplied=False)
            try:
                close.wait((root / "started").exists, "producer and child start")
                leader, child = json.loads((root / "started").read_text())
                assert not close.dead(leader) and not close.dead(child)
                challenge = secrets.token_hex(16)
                (root / "challenge").write_text(challenge)
                close.wait(
                    lambda: (root / "answer").is_file() and (root / "answer").read_text() == challenge,
                    "challenge before window close",
                )
                during = checks.snapshot(h, key)
                assert during["state"] == "running" and during["authorization"] == before["authorization"]
            finally:
                (root / "close").touch()
            closed = first.result()
        assert closed["exit"] == 0 and closed["pid"] == closed["result"]["pid"]
        assert closed["result"]["selected"] == "AI Chat" and not closed["result"]["sidebar_visible"]
        post_exit = secrets.token_hex(16)
        (root / "challenge").write_text(post_exit)
        close.wait(
            lambda: all(close.dead(pid) for pid in (leader, child)), "physical exit of the registered worker tree", 8
        )
        close.wait(lambda: checks.snapshot(h, key)["state"] == "editor-interrupted", "durable interruption", 8)
        assert (root / "answer").read_text() != post_exit
        stopped = checks.snapshot(h, key)
        assert stopped["candidate"] is None and receive.call_count == 0
        status = h.api("status", key=key).raise_for_status().json()
        (event,) = [e for e in status["progress"]["events"] if e["step"] == "process.interrupted"]
        archive = workflow.worker.root / event["details"]["archive"]
        assert (archive / "work/a/abandoned").read_text() == "uncollected partial output"
        saved = sha(layout)

        # A different issue in the same project needs this actor's judgment; the
        # interrupted branch is already authorized on module a and can proceed.
        judgment = h.issues[1]
        assert judgment["id"] != issue["id"]
        revision = workflow.worker.store.submit(
            tenant,
            actor,
            "review-sketch",
            [dict(module="b", base=initial["b"], reads=None, edits={"sketch.svg": checks.stage.PREVIEW.encode()})],
        )["revisions"]["b"]
        h.client.post(
            f"/api/v1/issues/{judgment['id']}/work/submit_asset",
            params={"project": "studio"},
            json=dict(
                expected_version=0, kind="concept", module="b", revision=revision, path="sketch.svg", call_id="submit"
            ),
        ).raise_for_status()

        def my_pending():
            payload = h.client.get("/api/v1/work/my-judgments", params={"project": "studio"}).raise_for_status().json()
            (item,) = payload["items"]
            return item

        pending = my_pending()
        assert pending["issue_id"] == judgment["id"] and pending["revision"] == revision
        response.unlink(missing_ok=True)
        (root / "release").touch()
        start = len(requests)
        reopened = editor_view(
            revision=revision,
            layout_sha256=saved,
            saved_main_screen="AI Chat",
            hold_first_scan=True,
            response=str(response),
            worker_started=str(root / "retry-started"),
            queue_visible=str(visible),
        )
        routes = requests[start:].copy()
        view = reopened["result"]
        assert reopened["exit"] == 0 and reopened["pid"] == view["pid"] != closed["pid"]
        assert (
            view["bound_before_layout"]
            and view["worker_started_while_focused"]
            and view["still_focused_after_recovery"]
        )
        assert view["row"].splitlines()[0] == f"#{pending['number']} {pending['title']} · {pending['path']}"
        after = checks.snapshot(h, key)
        for field in ("task", "target", "input_revisions", "authorization"):
            assert before[field] == stopped[field] == after[field]
        receipt = after["stage_receipt"]
        assert after["state"] == receipt["state"] == "stage-reached"
        assert (receipt["authorization"], receipt["candidate"], receipt["modules"]) == (
            before["authorization"]["stage"],
            after["candidate"],
            after["artifact_revisions"],
        )
        assert receipt["checks"]["check"]["outcome"] == "passed"
        preview = workflow.worker.store.read(tenant, "a", receipt["modules"]["a"], "preview.svg")
        assert preview.decode() == checks.stage.PREVIEW
        assert after["pending_decision"] == dict(task=key, kind="stage-confirmation")
        counts = checks.count_processes(h)
        assert counts["workers"] == [leader, int((root / "retry-started").read_text())]
        assert len(set(counts["workers"])) == 2 and len(counts["checkers"]) == 1
        assert all(close.dead(pid) for pid in counts["workers"] + counts["checkers"])
        assert all(row["execution"] == key and row["grant"] == receipt["authorization"] for row in h.observations())
        assert receive.call_count == 1 and receive.call_args.args[2] == "worker-" + key

        # Reopen once more through the actual editor entry and bound account.
        probe.write_text(reopen.OBSERVER, encoding="utf-8")
        response.unlink()
        start = len(requests)
        repeated = reopen.editor(engine, project, url, token, {"R07_OBSERVED": str(response)})
        replay_routes = requests[start:].copy()
        assert repeated["pid"] == repeated["result"]["pid"] and repeated["result"]["identity"]["id"] == actor
        assert repeated["pid"] not in (closed["pid"], reopened["pid"]) and repeated["exit"] == 0
        for batch in (routes, replay_routes):
            assert [(r["path"], r["status"]) for r in batch if r["method"] != "GET"] == [
                ("/api/v1/native/workflow/recover-occupancy", 200),
                ("/api/v1/native/workflow/recover-project", 200),
            ]
        assert checks.snapshot(h, key) == after and checks.count_processes(h) == counts
        assert my_pending() == pending and h.detail(issue)["task_confirmation"] == confirmed
        with workflow.worker.store._connection() as db:
            keys = [
                r[0] for r in db.execute("SELECT request_key FROM native_candidate_receipts WHERE tenant=?", (tenant,))
            ]
        assert keys == ["worker-" + key] and receive.call_count == 1
        return dict(
            platform=platform.platform(),
            python=sys.version.split()[0],
            editor_sha256=sha(engine),
            actor=actor,
            project="studio",
            scope="Windows GUI executable with headless display and normal window close",
            before=before,
            running=during,
            interrupted=stopped,
            interruption=event["details"],
            finished=after,
            service_pid=os.getpid(),
            closed_editor=closed,
            closed_worker_pids=[leader, child],
            answered_before_exit=True,
            answered_after_exit=False,
            layout_sha256=saved,
            pending=pending,
            reopened_editor=reopened,
            repeated_editor_pid=repeated["pid"],
            repeated_editor_exit=repeated["exit"],
            first_reopen_http=routes,
            repeat_reopen_http=replay_routes,
            processes=counts,
            candidate_receipts=keys,
            candidate_intake_calls=receive.call_count,
            duplicate_submissions=receive.call_count - len(keys),
            preview_sha256=hashlib.sha256(preview).hexdigest(),
            passed=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="q04-close-") as temp:
        with patch.dict(os.environ, GONGGONG_WORKSPACE=""):
            result = exercise(Path(temp), args.source.resolve(strict=True), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
