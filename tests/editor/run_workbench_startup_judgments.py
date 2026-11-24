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


def exercise(root, executable, display_driver="headless", judgments_first=False, saved_layout=None):
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
            projects = {}
            for who, credential in [(actor, token), (peer, domain.issue_session(peer))]:
                project = root / who
                project.mkdir()
                (project / "project.godot").write_text(
                    'config_version=5\n[application]\nconfig/name="Design Batch Fixture"\n'
                    '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
                )
                shutil.copyfile(Path(__file__).with_name("workbench_startup_judgments.gd"), project / "probe.gd")
                layout = project / ".godot/editor/editor_layout.cfg"
                if saved_layout:
                    layout.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(saved_layout, layout)
                marker.unlink(missing_ok=True)
                closed = editor(
                    engine,
                    project,
                    origin,
                    credential,
                    {
                        "R08_FIXTURE": json.dumps(
                            dict(phase="save", actor=who, response=str(marker), supplied=bool(saved_layout))
                        )
                    },
                    result_prefixes=("R08_NATIVE=",),
                    display_driver=display_driver,
                )
                initial_view = closed["result"]
                assert closed["pid"] == initial_view["pid"] and initial_view["display_driver"].lower() == display_driver
                assert not initial_view["sidebar_visible"], initial_view
                if not saved_layout:
                    assert initial_view["selected"] == "AI Chat", initial_view
                saved = hashlib.sha256(layout.read_bytes()).hexdigest()
                if saved_layout:
                    # Replay the original bytes even if the candidate normalized them during close.
                    shutil.copyfile(saved_layout, layout)
                projects[who] = (project, credential, closed, saved)

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
            for who, expected in [(actor, revision), (peer, "")]:
                project, credential, closed, saved = projects[who]
                replay_digest = hashlib.sha256((project / ".godot/editor/editor_layout.cfg").read_bytes()).hexdigest()
                expected_digest = hashlib.sha256(saved_layout.read_bytes()).hexdigest() if saved_layout else saved
                assert replay_digest == expected_digest
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
                                    layout_sha256=replay_digest,
                                    saved_main_screen=closed["result"]["selected"],
                                    hold_first_scan=judgments_first and bool(expected),
                                    response=str(marker),
                                    worker_started=str(h.calls),
                                    queue_visible=str(visible),
                                )
                            )
                        },
                        result_prefixes=("R08_NATIVE=",),
                        display_driver=display_driver,
                    )
                except RuntimeError as exc:
                    exc.add_note(f"Startup routes: {requests[start:]}")
                    exc.add_note(f"Recovered checkpoint: {checks.snapshot(h, key)}")
                    raise
                assert run["pid"] == run["result"]["pid"] and run["result"]["display_driver"].lower() == display_driver
                if expected and judgments_first:
                    assert run["result"]["bound_before_layout"]
                routes = requests[start:]
                assert {r["status"] for r in routes if r["path"] == "/api/v1/work/my-judgments"} == {200}
                writes = [r["path"] for r in routes if r["method"] != "GET"]
                assert writes == [
                    "/api/v1/native/workflow/recover-occupancy",
                    "/api/v1/native/workflow/recover-project",
                ]
                runs["owner" if expected else "peer"] = dict(
                    **run,
                    http=routes,
                    initial_close=closed,
                    closed_layout_sha256=saved,
                    reopened_layout_sha256=replay_digest,
                )
            received = checks.verify_received(h, key, before)
            pending = h.client.get("/api/v1/work/my-judgments", params={"project": "studio"}).raise_for_status().json()
            (item,) = pending["items"]
            assert (
                runs["owner"]["result"]["row"].splitlines()[0] == f"#{item['number']} {item['title']} · {item['path']}"
            )
            assert item["revision"] == revision and item["issue_id"] == judgment["id"] != issue["id"]
    with executable.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        passed=True,
        editor_sha256=digest,
        layout_source="supplied" if saved_layout else "normal AI Chat window close",
        reopen_navigation="none",
        editors=runs,
        still_pending=item,
        **received,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--display-driver", choices=("headless", "macos"), default="headless")
    parser.add_argument(
        "--judgments-first", action="store_true", help="Deliver the owner's queue before layout restoration"
    )
    parser.add_argument("--saved-layout", type=Path, help="Replay a normally closed Q05 project's editor_layout.cfg")
    args = parser.parse_args()
    with (
        tempfile.TemporaryDirectory(prefix="r08-startup-judgments-") as folder,
        patch.dict(os.environ, GONGGONG_WORKSPACE=""),
    ):
        report = exercise(
            Path(folder), args.godot.resolve(strict=True), args.display_driver, args.judgments_first, args.saved_layout
        )
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
