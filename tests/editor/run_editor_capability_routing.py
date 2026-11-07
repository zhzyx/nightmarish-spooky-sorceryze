"""Real editor UI + loopback/CLI acceptance; no model service is contacted."""

import argparse
import http.client
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

from editor_test_isolation import macos_editor


def await_file(path, process, timeout=20):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise AssertionError("Fixture stopped/timed out: " + str(path))
        time.sleep(0.03)
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("editor_client", root / "tools/editor_control_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="godot-capability-") as folder:
        project = Path(folder)
        isolated_editor = macos_editor(args.godot, project / "isolated-editor")
        if sys.platform == "darwin":
            (isolated_editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
                '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
                "ai_chat/editor_control_bridge_enabled = true\n",
                encoding="utf-8",
            )
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Capability fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        shutil.copyfile(Path(__file__).with_name("editor_capability_routing.gd"), project / "test.gd")
        env = {
            **os.environ,
            "APPDATA": str(project / "appdata"),
            "LOCALAPPDATA": str(project / "localappdata"),
            "GODOT_AI_API_KEY": "",
        }
        with (project / "editor.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [str(isolated_editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                cwd=project,
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                ready = await_file(project / "ready.json", process)
                ids = ready["ids"]
                assert all(ids.values()), ids
                assert not ready["password_targets"] and not ready["protected_targets"]
                client = module.EditorClient(project)
                daqian = client.capabilities(ready["daqian_title"])
                assert daqian["targets"], (
                    "New mainline Dock did not register automatically",
                    ascii(ready["daqian_title"]),
                    daqian["registry"],
                )
                sequence = 0

                def command(action="snapshot", **values):
                    nonlocal sequence
                    sequence += 1
                    pending_command = project / "command.pending"
                    pending_command.write_text(
                        json.dumps({"action": action, "id": sequence, **values}), encoding="utf-8"
                    )
                    pending_command.replace(project / "command.json")
                    return await_file(project / f"ack-{sequence}.json", process)

                def route(action, label="FixtureInput", value=None, request_id=None):
                    nonlocal sequence
                    sequence += 1
                    message = {
                        "intent": "engine_operation",
                        "request_id": request_id or f"fixture-{sequence}",
                        "source": "acceptance",
                        "operation": {"action": action, "target": ids.get(label, label)},
                    }
                    if value is not None:
                        message["operation"]["value"] = value
                    return message, client.route(message)

                def settle(message, decision="approve"):
                    state = command(decision)
                    return state, client.status(message["request_id"], "acceptance")

                assert "set_text" in client.capabilities("FixtureInput")["targets"][0]["actions"]
                assert route("set_text", value="hidden")[1]["error"] == "target_not_visible"
                assert route("open_target", "FixturePage")[1]["ok"]
                assert route("focus")[1]["ok"]
                assert route("highlight")[1]["ok"]
                assert route("set_text", "FixtureDisabled", "bad")[1]["error"] == "unsupported_target_action"
                assert route("press", "FixtureDisabled")[1]["error"] == "unsupported_target_action"
                message, result = route("set_text", value="中文 input")
                assert result["routing_status"] == "awaiting_confirmation" and not result["ok"]
                assert command()["text"] == "original"
                assert client.route(message)["idempotent"]
                assert route("press", "FixturePress")[1]["error"] == "editor_busy"
                state, result = settle(message)
                assert result["ok"] and state["text"] == "中文 input" and state["stop_disabled"]
                assert client.route(message)["idempotent"]
                changed = json.loads(json.dumps(message))
                changed["operation"]["value"] = "different"
                assert client.route(changed)["error"] == "request_id_conflict"

                for action, label, value, field in [
                    ("set_text", "FixtureMultiline", "a\nb", "multiline"),
                    ("set_value", "FixtureNumber", 42, "number"),
                    ("select_option", "First", 1, "selected"),
                ]:
                    message, pending = route(action, label, value)
                    assert pending["confirmation_required"], pending
                    state, result = settle(message)
                    assert result["ok"] and state[field] == value, (state, result)
                message, pending = route("press", "FixturePress")
                assert pending["confirmation_required"]
                assert settle(message)[1]["ok"]
                assert client.route(message)["idempotent"] and command()["presses"] == 1

                message, _ = route("set_text", value="rejected")
                state, result = settle(message, "reject")
                assert result["routing_status"] == "cancelled" and state["text"] == "中文 input"
                message, _ = route("set_text", value="cancelled")
                assert settle(message, "stop")[1]["error"] == "user_cancelled"
                message, _ = route("set_text", value="stale-value")
                command("edit")
                assert settle(message)[1]["error"] == "target_changed_since_confirmation"
                message, _ = route("set_text", value="stale-object")
                replaced = command("replace")
                replacement_result = settle(message)[1]
                assert replacement_result.get("error") == "target_changed_since_confirmation", replacement_result
                assert replaced["current_input"] == ids["FixtureInput"], replaced
                command("secret", value=True)
                assert not client.capabilities("FixtureInput")["targets"]
                assert route("set_text", value="secret")[1]["error"] == "target_unavailable"
                command("secret", value=False)
                command("reparent")
                assert client.capabilities("FixturePress")["targets"][0]["id"] == ids["FixturePress"]
                command("later")
                assert client.capabilities("FixtureLaterInput")["targets"]
                command("duplicate_alias")
                assert not client.capabilities("editor.fixture_duplicate")["targets"]
                assert route("set_text", "editor.fixture_duplicate", "ambiguous")[1]["error"] == "target_unavailable"

                unrelated = client.route({"intent": "chat", "request_id": "chat", "source": "acceptance"})
                assert unrelated["routing_status"] == "not_applicable" and not unrelated["routed"]
                planning = client.route({
                    "intent": "engine_operation",
                    "request_id": "plan",
                    "source": "acceptance",
                    "request": "打开界面",
                })
                assert planning["routing_status"] == "planning_required" and planning["next"]
                command("permission", value=False)
                assert not client.capabilities()["ok"]
                assert route("focus")[1]["error"] == "permission_denied"
                command("permission", value=True)
                command("consultation", value=True)
                assert route("focus")[1]["error"] == "permission_denied"
                command("consultation", value=False)
                message, _ = route("set_text", value="permission-changed")
                command("permission", value=False)
                command("approve")
                command("permission", value=True)
                assert client.status(message["request_id"], "acceptance")["error"] == "permission_denied"

                def raw(headers=None, body=None):
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", urllib.parse.urlsplit(client.info["url"]).port, timeout=7
                    )
                    connection.request(
                        "POST" if body is not None else "GET",
                        "/v1/messages" if body is not None else "/v1/capabilities",
                        body,
                        {
                            "Authorization": "Bearer " + client.info["token"],
                            "X-Godot-Session": client.info["session"],
                            "Content-Type": "application/json",
                            **(headers or {}),
                        },
                    )
                    response = connection.getresponse()
                    result = (response.status, json.loads(response.read()))
                    connection.close()
                    return result

                assert raw({"Authorization": "Bearer invalid"})[0] == 401
                assert raw({"X-Godot-Session": "old-session"})[0] == 401
                assert raw({"Origin": "http://example.invalid"})[0] == 403
                try:
                    assert raw(body=b"x" * 32769)[0] == 413
                except ConnectionResetError:
                    # Rejecting before reading an oversized body may reset TCP on Windows.
                    pass
                assert client.capabilities("FixtureInput")["ok"], "Oversized request broke the next connection"

                cli = [sys.executable, str(root / "tools/editor_control_client.py"), "--project", str(project)]
                discovery = subprocess.run(
                    [*cli, "capabilities", "--query", "FixtureInput"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                )
                assert json.loads(discovery.stdout)["targets"]
                command("auto", value=True)
                sent = subprocess.run(
                    [
                        *cli,
                        "route",
                        "--source",
                        "cli",
                        "--request-id",
                        "cli-input",
                        "--operation",
                        json.dumps({"action": "set_text", "target": ids["FixtureInput"], "value": "CLI input"}),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                )
                assert json.loads(sent.stdout)["ok"] and command()["text"] == "CLI input"
                recovered = subprocess.run(
                    [*cli, "status", "cli-input", "--source", "cli"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                )
                assert json.loads(recovered.stdout)["ok"]
                assert client.info["token"] not in discovery.stdout + sent.stdout + recovered.stdout
                descriptor = project / ".godot/editor/ai_control" / f"{client.info['pid']}.json"
                command("auto", value=False)
                assert route("set_text", value="unapproved-on-exit")[1]["confirmation_required"]
                (project / "finish").touch()
                process.wait(timeout=20)
                assert process.returncode == 0 and not descriptor.exists()
                assert json.loads((project / "final.json").read_text(encoding="utf-8"))["text"] == "CLI input"
                print("EDITOR_CAPABILITY_ROUTING_HTTP_CLI_OK")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                log.flush()
                print((project / "editor.log").read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    main()
