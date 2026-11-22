"""Check registered page fields through the native sidebar, model receiver and editor approval router."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

import editor_test_isolation
from editor_control_client import EditorClient
from run_unified_settings_native import sanitized_environment
from run_workbench_page_reference import Model

SOURCE = Path(__file__).parent.resolve()
ROOT = SOURCE.parents[1]


def wait_file(path, process, log):
    deadline = time.monotonic() + 40
    while not path.exists() or not path.stat().st_size:
        if process.poll() is not None or time.monotonic() >= deadline:
            raise AssertionError(f"Missing {path.name}: " + log.read_text(encoding="utf-8", errors="replace")[-8000:])
        time.sleep(0.04)
    return path.read_text(encoding="utf-8")


def prepare_project(project):
    shutil.copytree(ROOT / "samples/gonggong-workbench", project)
    shutil.copyfile(SOURCE / "workbench_page_field.gd", project / "test.gd")
    shutil.copyfile(SOURCE / "ai_chat_tab_order.gd", project / "order.gd")


def prepare_editor(editor, root, endpoint):
    binary = editor_test_isolation.copy_editor(editor, root / "editor")
    (binary.parent / "editor_data/editor_settings-4.8.tres").write_text(
        '[gd_resource type="EditorSettings" format=3]\n[resource]\n'
        f'ai_chat/editor_control_bridge_enabled = true\nai_chat/endpoint = "{endpoint}"\n'
        'ai_chat/model = "fixture"\nai_chat/backend = 0\n'
    )
    return binary


def package_round_trip(root, editor, endpoint, server):
    project = root / "project"
    prepare_project(project)
    binary = prepare_editor(editor, root, endpoint)
    plugin = project / "addons/project_brief/plugin.gd"
    original = plugin.read_bytes()
    updated = original.replace(b'"Brief/Summary": "replace_text"', b'"Brief/Summary": "read"')
    assert updated != original
    env = sanitized_environment(root)
    env.update(PAGE_TEST_ENDPOINT=endpoint, U16_PACKAGE_PROBE="1")
    observations = []
    for data, actions in [(original, ["replace_page_field"]), (updated, []), (original, ["replace_page_field"])]:
        plugin.write_bytes(data)
        count = len(server.requests)
        result = subprocess.run(
            [binary, "--headless", "--editor", "--path", project, "--script", "res://test.gd"],
            cwd=root,
            env=env,
            capture_output=True,
            timeout=45,
        )
        assert (
            result.returncode == 0 and b"PACKAGE_PROBE_OK" in result.stdout and b"SCRIPT ERROR" not in result.stderr
        ), (result.stdout + result.stderr).decode(errors="replace")
        assert len(server.requests) == count + 1
        snapshot = received(server, "Brief/Summary")
        assert snapshot["page_field"]["actions"] == actions
        observations.append({"plugin_sha256": hashlib.sha256(data).hexdigest(), "received_actions": actions})
    return observations


@contextmanager
def running_project(root, editor, endpoint):
    project = root / "project"
    prepare_project(project)
    binary = prepare_editor(editor, root, endpoint)
    log = root / "editor.log"
    env = sanitized_environment(root)
    env["PAGE_TEST_ENDPOINT"] = endpoint
    with (
        log.open("wb") as output,
        subprocess.Popen(
            [binary, "--headless", "--editor", "--path", project, "--script", "res://test.gd"],
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=root,
        ) as process,
    ):
        seq = 0

        def command(action):
            nonlocal seq
            commands = project / ".godot"
            tmp = commands / "u16-next"
            tmp.write_text(action)
            tmp.replace(commands / f"u16-command-{seq}")
            if action == "exit":
                return
            result = json.loads(wait_file(commands / f"u16-reply-{seq}", process, log))
            assert result["neighbor"] == "LOCAL_ONLY_1793" and result["milestone"] == "Prototype", result
            seq += 1
            return result

        try:
            wait_file(project / ".godot/u16-ready", process, log)
            yield EditorClient(project), command, project
            command("exit")
            assert process.wait(timeout=15) == 0 and "SCRIPT ERROR" not in log.read_text(encoding="utf-8")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)


def received(server, field):
    for request in reversed(server.requests):
        content = [m["content"] for m in request["messages"] if m["role"] == "user"][-1]
        if content.startswith("Read " + field + "\n"):
            snapshot = json.loads(content.split("context_snapshot=", 1)[1])
            assert snapshot["page_name"] == "Project Brief"
            assert snapshot["module_id"] == "res://addons/project_brief/plugin.gd"
            assert snapshot["readable_scope"] == ["page_name", "module_id", field]
            assert snapshot["page_field"]["field"] == field
            assert len(snapshot["references"]) == 1
            return snapshot
    raise AssertionError("Missing receiver snapshot for " + field)


def route(client, request, snapshot, new):
    ref = snapshot["references"][0]
    return client.route({
        "intent": "engine_operation",
        "source": "page-test",
        "request_id": request,
        "operation": {
            "action": "replace_page_field",
            "target": ref["object_id"],
            "revision": ref["revision"],
            "value": new,
        },
    })


def verify(editor):
    with (
        tempfile.TemporaryDirectory(prefix="u16-page-") as temp,
        ThreadingHTTPServer(("127.0.0.1", 0), Model) as server,
    ):
        root = Path(temp)
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        server.requests = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        report = {}
        try:
            with running_project(root / "a", editor, endpoint) as (client, command, project):
                summary = received(server, "Brief/Summary")
                readonly = received(server, "Brief/Milestone")
                assert summary["page_field"]["actions"] == ["replace_page_field"]
                assert summary["page_field"]["required_authorization"] == "confirm_exact_replacement"
                assert readonly["page_field"]["actions"] == []
                assert route(client, "consult", summary, "New")["error"] == "permission_denied"
                command("development")
                assert route(client, "read-only", readonly, "Other")["error"] == "read_only_field"
                assert route(client, "reject", summary, "Rejected")["routing_status"] == "awaiting_confirmation"
                assert command("reject")["summary"] == "First playable"
                assert client.status("reject", "page-test")["error"] == "user_rejected"
                offered = route(client, "edit", summary, "Ready for playtest")
                assert offered["routing_status"] == "awaiting_confirmation" and offered["manual_confirmation_required"]
                pending = command("read")
                assert pending["summary"] == pending["saved"] == "First playable" and pending["dialog"]
                preview = pending["preview"]
                for key in ("target", "field", "revision", "old_value", "new_value"):
                    assert preview[key] == offered[key]
                applied = command("confirm")
                assert applied["summary"] == applied["saved"] == "Ready for playtest" and not applied["dialog"]
                receipt = client.status("edit", "page-test")
                assert receipt["routing_status"] == "completed" and receipt["ok"]
                assert receipt["updated_reference"]["revision"] != offered["revision"]
                assert route(client, "old", summary, "Outdated")["error"] == "stale_field_reference"
                assert route(client, "edit", summary, "Ready for playtest")["idempotent"]
                command("restage")
                revised = received(server, "Brief/Summary")
                assert revised["references"] == [receipt["updated_reference"]]
                assert route(client, "race", revised, "Too late")["confirmation_required"]
                command("change")
                assert command("confirm")["summary"] == "User correction"
                assert client.status("race", "page-test")["error"] == "stale_field_reference"
                validation = command("validate")
                assert validation["summary"] == validation["saved"] == "User correction"
                assert (
                    validation["validation"]["passed"]
                    and validation["validation"]["revision"] in validation["visible_result"]
                )
                command("restage")
                corrected = received(server, "Brief/Summary")
                assert corrected["page_field"]["value"] == validation["saved"]
                assert corrected["page_field"]["validation"] == validation["validation"]
                assert corrected["references"][0]["revision"] == validation["validation"]["revision"]
                report["page_validation"] = dict(page=validation, received=corrected)
                assert route(client, "unregister", corrected, "Too late")["confirmation_required"]
                command("unregister")
                assert command("confirm")["summary"] == "User correction"
                assert client.status("unregister", "page-test")["error"] == "stale_field_reference"
                report.update(
                    receiver=summary,
                    readonly=readonly,
                    preview={k: preview[k] for k in ("field", "old_value", "new_value", "revision", "target")},
                    applied=applied,
                    updated_reference=receipt["updated_reference"],
                    routed=receipt["routing_status"],
                    rejected="user_rejected",
                    changed_during_approval="stale_field_reference",
                    unregistered_during_approval="stale_field_reference",
                )
            history = json.loads((project / ".godot/editor/ai_chat_history.json").read_text(encoding="utf-8"))
            messages = [r for agent in history["agents"] for r in agent["transcript"] if r["role"] == "user"]
            assert [m["editor_references"] for m in messages] == [
                s["references"] for s in (summary, readonly, revised, corrected)
            ]
            with running_project(root / "b", editor, endpoint) as (other, command, project):
                second = received(server, "Brief/Summary")
                assert (
                    second["page_field"]["value"] == "First playable" and second["references"] != summary["references"]
                )
                command("development")
                result = route(other, "foreign", summary, "Project A edit")
                assert result["error"] == "stale_field_reference" and command("read")["summary"] == "First playable"
                assert route(other, "close", second, "Closed")["confirmation_required"]
                command("remove")
                assert command("confirm")["summary"] == "First playable"
                assert other.status("close", "page-test")["error"] == "stale_field_reference"
                report.update(
                    other_project=second["references"][0],
                    foreign_project=result["error"],
                    closed_page="stale_field_reference",
                )
            report["plugin_update_rollback"] = package_round_trip(root / "package", editor, endpoint, server)
            assert len(server.requests) == 9, len(server.requests)
            wire = json.dumps(server.requests)
            assert "LOCAL_ONLY_1793" not in wire and "stale draft" not in wire
            report.update(
                private_neighbor_absent=True,
                rename_blocked=True,
                history_matches_receiver=True,
                requests=len(server.requests),
            )
            return report
        finally:
            server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    report = verify(args.godot.resolve())
    with args.godot.open("rb") as binary:
        digest = hashlib.sha256()
        for chunk in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(chunk)
        report["editor_sha256"] = digest.hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Page field acceptance passed")
