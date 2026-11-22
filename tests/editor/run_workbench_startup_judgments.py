"""Observe the first focused personal judgment while an independent signed worker is running."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from run_workbench_project_reopen import checks, copy_editor, editor, receiver


def exercise(root, executable):
    engine = copy_editor(executable, root / "engine")
    marker, visible = root / "recovered", root / "queue-visible"
    with contextmanager(checks.fixture.__wrapped__)(root) as fixture:
        workflow, actor, tenant, _, initial, _ = fixture
        domain = workflow.domain
        token = domain.issue_session(actor)
        peer = domain.add_member(actor, "peer@example.invalid", secrets.token_urlsafe(), name="Peer")["user_id"]
        with (
            contextmanager(checks.host.__wrapped__)(fixture) as h,
            patch.dict(
                os.environ,
                TIANXUAN_AUTH_MODE="accounts",
                TIANXUAN_TENANT_ID=tenant,
                TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
            ),
            receiver(h, token, marker) as (origin, requests),
        ):
            issue = checks.install(h)
            profile = workflow.worker.profiles["local"]
            probe = Path(profile["argv"][1])
            profile["timeout"] = 35
            profile["env"]["QUEUE_VISIBLE"] = str(visible)
            with probe.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\nimport time\ndeadline = time.monotonic() + 30\n"
                    "while not pathlib.Path(os.environ['QUEUE_VISIBLE']).exists():\n"
                    "    if time.monotonic() >= deadline: raise TimeoutError('queue visibility')\n"
                    "    time.sleep(0.05)\n"
                )
            key = checks.stage.signed(h, issue)
            before = checks.snapshot(h, key)
            assert before["state"] == "ready" and checks.count_processes(h) == {"workers": [], "checkers": []}
            judgment = h.issues[1]
            revision = workflow.worker.store.submit(
                tenant,
                actor,
                "review-sketch",
                [dict(module="b", base=initial["b"], reads=None, edits={"sketch.svg": checks.stage.PREVIEW.encode()})],
            )["revisions"]["b"]
            work_url = f"/api/v1/issues/{judgment['id']}/work"
            h.client.post(
                work_url + "/submit_asset",
                params={"project": "studio"},
                json=dict(
                    expected_version=0,
                    kind="concept",
                    module="b",
                    revision=revision,
                    path="sketch.svg",
                    call_id="submit",
                ),
            ).raise_for_status()
            runs = {}
            for who, credential, expected in [
                (actor, token, revision),
                (peer, domain.issue_session(peer), ""),
            ]:
                # Fresh layout for each account, without any navigation from the observer.
                project = root / who
                project.mkdir()
                (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="R08"\n')
                shutil.copyfile(Path(__file__).with_name("workbench_startup_judgments.gd"), project / "probe.gd")
                marker.unlink(missing_ok=True)
                start = len(requests)
                try:
                    run = editor(
                        engine,
                        project,
                        origin,
                        credential,
                        {
                            "R08_FIXTURE": json.dumps(
                                dict(
                                    actor=who,
                                    revision=expected,
                                    response=str(marker),
                                    worker_started=str(h.calls),
                                    queue_visible=str(visible),
                                )
                            )
                        },
                        result_prefixes=("R08_NATIVE=",),
                    )
                except RuntimeError as exc:
                    exc.add_note(f"Startup routes: {requests[start:]}")
                    exc.add_note(f"Recovered checkpoint: {checks.snapshot(h, key)}")
                    raise
                assert run["pid"] == run["result"]["pid"]
                routes = requests[start:]
                assert {r["status"] for r in routes if r["path"] == "/api/v1/work/my-judgments"} == {200}
                writes = [r["path"] for r in routes if r["method"] != "GET"]
                assert writes == [
                    "/api/v1/native/workflow/recover-occupancy",
                    "/api/v1/native/workflow/recover-project",
                ]
                runs["owner" if expected else "peer"] = dict(**run, http=routes)
            received = checks.verify_received(h, key, before)
            pending = h.client.get("/api/v1/work/my-judgments", params={"project": "studio"}).raise_for_status().json()
            (item,) = pending["items"]
            assert item["revision"] == revision and item["issue_id"] == judgment["id"] != issue["id"]
    with executable.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(passed=True, editor_sha256=digest, editors=runs, still_pending=item, **received)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with (
        tempfile.TemporaryDirectory(prefix="r08-startup-judgments-") as folder,
        patch.dict(os.environ, GONGGONG_WORKSPACE=""),
    ):
        report = exercise(Path(folder), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
