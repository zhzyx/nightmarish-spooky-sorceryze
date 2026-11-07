"""Isolated headless command coverage; never drives the user's desktop."""

import argparse
import http.client
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path

from editor_test_isolation import macos_editor


def await_json(path, process):
    deadline = time.monotonic() + 90
    while not path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise AssertionError("Fixture exited or timed out")
        time.sleep(0.03)
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("editor_client", source / "tools/editor_control_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="editor-command-coverage-") as folder:
        project = Path(folder)
        editor = macos_editor(args.godot, project / "private-editor")
        (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\n'
        )
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Command Coverage"\n')
        shutil.copyfile(Path(__file__).with_name("editor_command_coverage.gd"), project / "test.gd")
        log_path = project / "editor.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                env={**os.environ, "GODOT_AI_API_KEY": ""},
                stdout=log,
                stderr=log,
            )
            try:
                ready = await_json(project / "ready.json", process)
                assert not ready["errors"], ready
                client = module.EditorClient(project)
                counter = 0

                def route_action(action, **values):
                    nonlocal counter
                    counter += 1
                    return client.route({
                        "intent": "engine_operation",
                        "source": "coverage",
                        "request_id": f"action-{counter}",
                        "operation": {"action": action, **values},
                    })

                command_counter = 0

                def command(action, **values):
                    nonlocal command_counter
                    command_counter += 1
                    pending_file = project / "command.pending"
                    pending_file.write_text(json.dumps({"id": command_counter, "action": action, **values}))
                    pending_file.replace(project / "command.json")
                    return await_json(project / f"ack-{command_counter}.json", process)

                def approve(message):
                    command("approve")
                    return client.status(message["request_id"], message["source"])

                def manual(action, **values):
                    nonlocal counter
                    counter += 1
                    msg = {
                        "intent": "engine_operation",
                        "source": "coverage",
                        "request_id": f"manual-{counter}",
                        "operation": {"action": action, **values},
                    }
                    return msg, client.route(msg)

                # The fixture can publish ready while the native startup scan is busy.
                # Retry only this read; no writes or approvals are replayed.
                ready_deadline = time.monotonic() + 20
                alias = route_action("describe_target", target="plugin.coverage_alias")
                while alias.get("error") == "editor_busy" and time.monotonic() < ready_deadline:
                    time.sleep(0.05)
                    alias = route_action("describe_target", target="plugin.coverage_alias")
                assert alias["ok"] and alias["available"] and not alias["automatic"], alias
                assert alias["class"] == "LineEdit" and alias["value"] == "original", alias
                assert len(alias["position"]) == 2 and len(alias["size"]) == 2 and alias["window_instance"], alias
                core = route_action("describe_target", target="inspector")
                assert core["ok"] and core["available"] and not core["automatic"], core
                assert core["class"] and core["target_instance"] and len(core["position"]) == 2, core
                command("alias_secret", value=True)
                redacted = route_action("describe_target", target="plugin.coverage_alias")
                assert not redacted["ok"] and not redacted["available"] and "value" not in redacted, redacted
                command("alias_secret", value=False)
                assert route_action("describe_target", target="plugin.coverage_alias")["value"] == "original"
                screens = route_action("list_main_screens")
                assert screens["ok"] and len(screens["main_screens"]) > 5, screens
                switched = 0
                for screen in screens["main_screens"]:
                    if screen["name"] not in ("2D", "3D", "Script", "AssetLib", "AI Chat") and not screen["hidden"]:
                        switched_result = route_action("main_screen", target=screen["name"])
                        assert switched_result["ok"], switched_result
                        switched += 1
                assert switched > 0
                resource_message, resource_preview = manual("open_resource", target="res://fixture-gradient.tres")
                assert resource_preview["confirmation_required"]
                assert approve(resource_message)["ok"]
                assert route_action("open_resource", target="res://../outside.tres")["error"] == "invalid_project_path"
                assert route_action("open_scene", target="res://fixture-scene.tscn")["ok"]
                time.sleep(0.1)
                first = route_action("inspect_scene", limit=20)
                second = route_action("inspect_scene", limit=100, offset=20)
                assert first["total"] == 44 and len(first["nodes"]) == 20 and first["next_offset"] == 20, first
                assert len(second["nodes"]) == 24 and second["next_offset"] is None, second
                assert not route_action("inspect_scene", limit=101)["ok"]
                state = client.state()
                assert state["ok"] and state["scene"] == "res://fixture-scene.tscn", state
                pages = [client.capabilities("CoverageInput", 20, n) for n in (0, 20, 40)]
                assert [len(p["targets"]) for p in pages] == [20, 20, 5], pages
                assert len({item["id"] for p in pages for item in p["targets"]}) == 45
                assert not client.capabilities("", 21)["ok"]
                message = {
                    "intent": "engine_operation",
                    "source": "coverage",
                    "request_id": "cancel-exact",
                    "operation": {"action": "set_text", "target": ready["target"], "value": "must-not-apply"},
                }
                pending = client.route(message)
                assert pending["confirmation_required"], pending
                assert client.cancel("cancel-exact", "other")["error"] == "unknown_request"
                assert client.status("cancel-exact", "coverage")["routing_status"] == "awaiting_confirmation"
                cancelled = client.cancel("cancel-exact", "coverage")
                assert cancelled["routing_status"] == "cancelled" and cancelled["error"] == "request_cancelled", (
                    cancelled
                )
                assert client.route(message)["routing_status"] == "cancelled"
                assert client.cancel("cancel-exact", "coverage")["routing_status"] == "cancelled"
                command("capacity_targets")
                capacity = client.capabilities("CapacityButton", 1)
                assert capacity["registry"]["automatic_targets"] == 8192 and capacity["truncated"], capacity["registry"]
                assert capacity["registry"]["scanned_nodes"] <= 50000 and capacity["registry"]["queued_nodes"] <= 50000
                command("capacity_scan")
                tree_page = route_action("inspect_ui", limit=100)
                assert tree_page["ok"] and tree_page["total_is_lower_bound"] and tree_page["total"] <= 50000, tree_page
                assert len(json.dumps(tree_page, ensure_ascii=False).encode()) <= 16384
                scan = client.capabilities("CapacityNode", 1)["registry"]
                assert scan["queued_nodes"] == 50000 and scan["scanned_nodes"] <= 50000 and scan["truncated"], scan
                command("capacity_clear")
                assert len(client.capabilities("CoverageInput", 20)["targets"]) == 20
                # Original host confirmations drive semantic scene operations against an isolated scene.
                msg, preview = manual("scene_create_node", target=".", type="Node2D", name="Managed")
                assert preview["confirmation_required"], preview
                assert approve(msg)["ok"]
                msg, preview = manual("scene_rename_node", target="Managed", name="Renamed")
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                msg, preview = manual("scene_set_property", target="Renamed", property="position", value=[3, 4])
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                assert command("snapshot")["node_position"] == [3, 4]
                msg, preview = manual("scene_reparent_node", target="Renamed", parent="Child0")
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                assert command("snapshot", path="Child0/Renamed")["node_exists"]
                msg, preview = manual("scene_select_nodes", nodes=["Child0", "Child1"])
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                assert set(client.state()["selected_nodes"]) == {"Child0", "Child1"}
                msg, preview = manual("scene_delete_node", target="Child0/Renamed")
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                assert not command("snapshot", path="Child0/Renamed")["node_exists"]
                command("animation")
                msg, preview = manual("scene_rename_node", target="Animated", name="AnimatedRenamed")
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                assert command("snapshot")["animation_track"] == "AnimatedRenamed:position"
                msg, preview = manual("scene_reparent_node", target="AnimatedRenamed", parent="Child1")
                assert preview["confirmation_required"] and approve(msg)["ok"], preview
                assert command("snapshot")["animation_track"] == "Child1/AnimatedRenamed:position"
                command("undo")
                assert command("snapshot")["animation_track"] == "AnimatedRenamed:position"
                command("undo")
                assert command("snapshot")["animation_track"] == "Animated:position"
                command("run_config")
                run_msg, run_preview = manual("run_scene", target="res://fixture-scene.tscn")
                assert run_preview["confirmation_required"] and run_preview["manual_confirmation_required"], run_preview
                run_result = approve(run_msg)
                assert run_result["ok"] and run_result["run_requested"], run_result
                run_deadline = time.monotonic() + 8
                while not client.state()["running"] and time.monotonic() < run_deadline:
                    time.sleep(0.05)
                assert client.state()["running"], "Headless child scene did not start"
                stop_msg, stop_preview = manual("stop_project")
                assert stop_preview["confirmation_required"] and approve(stop_msg)["ok"], stop_preview
                stopped_deadline = time.monotonic() + 8
                while client.state()["running"] and time.monotonic() < stopped_deadline:
                    time.sleep(0.05)
                assert not client.state()["running"]

                # Field change and popup closure use observed state, not an execution receipt.
                def wait_guidance():
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        observed = route_action("guidance_status")
                        if observed["status"] == "completed":
                            return observed
                        assert observed["status"] != "failed", observed
                        time.sleep(0.12)
                    raise AssertionError("Guidance observation did not complete")

                assert route_action(
                    "start_guidance",
                    steps=[
                        {
                            "target": ready["target"],
                            "message": "Observe field",
                            "observe": {"type": "field_value", "value": "guided"},
                        }
                    ],
                )["ok"]
                assert route_action("guidance_start")["ok"]
                command("line", value="guided")
                assert wait_guidance()["last_observation"]["type"] == "field_value"
                command("line", value="original")
                command("popup")
                popup_target = client.capabilities("CoveragePopupInput")["targets"][0]["id"]
                assert route_action(
                    "start_guidance", steps=[{"target": popup_target, "observe": {"type": "window_closed"}}]
                )["ok"]
                assert route_action("guidance_start")["ok"]
                command("popup_close")
                assert wait_guidance()["last_observation"]["type"] == "window_closed"
                assert route_action(
                    "start_guidance",
                    steps=[
                        {
                            "target": ready["target"],
                            "observe": {
                                "type": "request_completed",
                                "request_id": "completion-proof",
                                "source": "external.coverage",
                            },
                        }
                    ],
                )["ok"]
                assert route_action("guidance_start")["ok"]
                completion = client.route({
                    "intent": "engine_operation",
                    "source": "coverage",
                    "request_id": "completion-proof",
                    "operation": {"action": "clear_highlight"},
                })
                assert completion["ok"]
                assert wait_guidance()["last_observation"]["request_id"] == "completion-proof"

                events = client.events()
                assert events["ok"] and any(e.get("error") == "request_cancelled" for e in events["events"]), events
                assert all("old_value" not in e and "new_value" not in e for e in events["events"])
                command("models")
                msg, preview = manual("chat_select_model", index=125)
                assert preview["confirmation_required"], preview
                command("model_replace")
                assert approve(msg)["error"] == "chat_changed_since_confirmation"
                later_models = route_action("chat_state", offset=100, limit=100)
                assert len(later_models["models"]) == 50 and later_models["models"][25]["id"] == "changed-model"
                model_msg, model_preview = manual("chat_select_model", index=0)
                assert model_preview["confirmation_required"] and approve(model_msg)["ok"]
                old_agent = route_action("chat_state")["active_agent"]
                new_msg, new_preview = manual("chat_new_session")
                assert new_preview["confirmation_required"] and approve(new_msg)["ok"]
                assert route_action("chat_state")["active_agent"] != old_agent
                select_msg, select_preview = manual("chat_select_session", index=0)
                assert select_preview["confirmation_required"] and approve(select_msg)["ok"]
                assert route_action("chat_state")["active_agent"] == old_agent
                endpoint_msg, endpoint_preview = manual("chat_set_endpoint", value="http://127.0.0.1:9/v1")
                assert endpoint_preview["confirmation_required"] and approve(endpoint_msg)["ok"]
                import hashlib

                assert (
                    route_action("chat_state")["endpoint_hash"] == hashlib.sha256(b"http://127.0.0.1:9/v1").hexdigest()
                )
                assert not client.capabilities("APIKey")["targets"]
                stop_state = route_action("chat_state")
                stop_result = route_action(
                    "chat_stop",
                    value={"conversation_id": stop_state["conversation_id"], "generation": stop_state["generation"]},
                )
                assert stop_result["ok"] and stop_result["stop_requested"], stop_result
                command("auto", value=True)
                msg, preview = manual("chat_compose", value="host draft")
                assert preview["confirmation_required"] and preview["manual_confirmation_required"], preview
                assert route_action("chat_state")["draft"] == ""
                assert approve(msg)["ok"]
                chat = route_action("chat_state")
                assert chat["draft"] == "host draft", chat
                msg, preview = manual("chat_send_request")
                assert preview["confirmation_required"] and preview["manual_confirmation_required"], preview
                assert client.cancel(msg["request_id"], "coverage")["routing_status"] == "cancelled"
                assert route_action("chat_state")["generation"] == chat["generation"]
                msg, preview = manual("chat_compose", value="stale draft")
                command("draft", value="intervening draft")
                assert approve(msg)["error"] == "chat_changed_since_confirmation"
                assert route_action("chat_state")["draft"] == "intervening draft"
                command("auto", value=False)
                msg, preview = manual(
                    "create_project_setting", target="coverage/vector", value_type="Vector2i", value=[10, 20]
                )
                assert preview["confirmation_required"], preview
                assert approve(msg)["ok"]
                assert route_action("get_project_setting", target="coverage/vector")["value"] == [10, 20]
                msg, preview = manual("update_project_setting", target="coverage/vector", value=[20, 30])
                assert preview["confirmation_required"], preview
                command("disk_change")
                assert approve(msg)["error"] == "setting_changed_since_confirmation"
                assert route_action("get_project_setting", target="coverage/vector")["value"] == [10, 20]
                assert (
                    route_action("get_editor_setting", target="ai_chat/auto_execute_commands")["error"]
                    == "protected_setting"
                )
                assert (
                    route_action("get_editor_setting", target="interface/editor/behavior/save_on_focus_loss")["error"]
                    == "protected_setting"
                )
                assert route_action("get_editor_setting", target="interface/editor/appearance/display_scale")["ok"]
                msg, preview = manual(
                    "set_editor_setting", target="interface/theme/accent_color", value=[0.2, 0.4, 0.6, 1.0]
                )
                assert preview["confirmation_required"], preview
                assert approve(msg)["ok"]
                actual_color = route_action("get_editor_setting", target="interface/theme/accent_color")["value"]
                assert all(abs(a - b) < 0.00001 for a, b in zip(actual_color, [0.2, 0.4, 0.6, 1]))
                # Auth/session enforcement precedes the new state/cancel endpoint handlers.
                for method, endpoint in [("GET", "/v1/state"), ("POST", "/v1/cancel?id=cancel-exact&source=coverage")]:
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", urllib.parse.urlsplit(client.info["url"]).port, timeout=7
                    )
                    connection.request(
                        method,
                        endpoint,
                        headers={"Authorization": "Bearer " + "0" * 64, "X-Godot-Session": client.info["session"]},
                    )
                    response = connection.getresponse()
                    assert response.status == 401
                    response.read()
                    connection.close()
                restart_pending, restart_preview = manual("chat_compose", value="must-not-replay-after-restart")
                assert restart_preview["confirmation_required"]
                (project / "finish").touch()
                final = await_json(project / "final.json", process)
                assert final["text"] == "original", final
                assert process.wait(timeout=20) == 0
                receipt_file = project / ".godot/editor/ai_control_receipts.json"
                receipt_text = receipt_file.read_text()
                assert "host draft" not in receipt_text and "must-not-replay-after-restart" not in receipt_text
                for name in ("ready.json", "final.json", "finish"):
                    (project / name).unlink(missing_ok=True)
                old_session = client.info["session"]
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    env={**os.environ, "GODOT_AI_API_KEY": ""},
                    stdout=log,
                    stderr=log,
                )
                restarted = await_json(project / "ready.json", process)
                assert not restarted["errors"], restarted
                client = module.EditorClient(project)
                assert client.info["session"] != old_session
                recovered = client.status(restart_pending["request_id"], "coverage")
                assert recovered.get("receipt_restored") and recovered.get("error") in (
                    "interrupted_by_editor_restart",
                    "editor_closed",
                ), recovered
                assert client.route(restart_pending)["routing_status"] == "cancelled"
                cancelled_again = client.route(message)
                assert cancelled_again["receipt_restored"] and cancelled_again["routing_status"] == "cancelled", (
                    cancelled_again
                )
                assert not route_action("chat_state")["draft"].startswith("must-not-replay")
                crash_pending, crash_preview = manual("chat_compose", value="crash-must-not-replay")
                assert crash_preview["confirmation_required"]
                process.kill()
                assert process.wait(timeout=20) != 0
                for name in ("ready.json", "final.json", "finish"):
                    (project / name).unlink(missing_ok=True)
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    env={**os.environ, "GODOT_AI_API_KEY": ""},
                    stdout=log,
                    stderr=log,
                )
                await_json(project / "ready.json", process)
                client = module.EditorClient(project)
                crash_recovered = client.status(crash_pending["request_id"], "coverage")
                assert (
                    crash_recovered.get("receipt_restored")
                    and crash_recovered.get("error") == "interrupted_by_editor_restart"
                ), crash_recovered
                assert client.route(crash_pending)["routing_status"] == "cancelled"
                (project / "finish").touch()
                await_json(project / "final.json", process)
                assert process.wait(timeout=20) == 0
                uncertain = json.loads(receipt_file.read_text())
                for record in uncertain["records"]:
                    if record["result"]["request_id"] == crash_pending["request_id"]:
                        record["result"]["routing_status"] = "execution_interrupted"
                        record["result"]["ok"] = False
                receipt_file.write_text(json.dumps(uncertain))
                for name in ("ready.json", "final.json", "finish"):
                    (project / name).unlink(missing_ok=True)
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    env={**os.environ, "GODOT_AI_API_KEY": ""},
                    stdout=log,
                    stderr=log,
                )
                await_json(project / "ready.json", process)
                client = module.EditorClient(project)
                unknown = client.route(crash_pending)
                assert (
                    unknown["routing_status"] == "execution_unknown"
                    and unknown["error"] == "execution_result_unknown_after_restart"
                ), unknown
                assert command("snapshot")["text"] == "original"
                (project / "finish").touch()
                await_json(project / "final.json", process)
                assert process.wait(timeout=20) == 0
                # Wall-clock expiry remains 900 seconds across a restart.
                expired = json.loads(receipt_file.read_text())
                for record in expired["records"]:
                    record["updated"] = int(time.time() * 1000) - 901000
                receipt_file.write_text(json.dumps(expired))
                for name in ("ready.json", "final.json", "finish"):
                    (project / name).unlink(missing_ok=True)
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    env={**os.environ, "GODOT_AI_API_KEY": ""},
                    stdout=log,
                    stderr=log,
                )
                await_json(project / "ready.json", process)
                client = module.EditorClient(project)
                assert client.status(crash_pending["request_id"], "coverage")["error"] == "unknown_request"
                (project / "finish").touch()
                await_json(project / "final.json", process)
                assert process.wait(timeout=20) == 0
                # Corrupt/partial durable records deny execution instead of being treated as an empty store.
                receipt_file.write_text("{partial")
                for name in ("ready.json", "final.json", "finish"):
                    (project / name).unlink(missing_ok=True)
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    env={**os.environ, "GODOT_AI_API_KEY": ""},
                    stdout=log,
                    stderr=log,
                )
                await_json(project / "ready.json", process)
                client = module.EditorClient(project)
                blocked = client.route({
                    "intent": "engine_operation",
                    "request_id": "corrupt-store",
                    "source": "coverage",
                    "operation": {"action": "set_text", "target": restarted["target"], "value": "must-not-write"},
                })
                assert blocked["error"] == "receipt_store_unavailable", blocked
                (project / "finish").touch()
                final = await_json(project / "final.json", process)
                assert final["text"] == "original" and process.wait(timeout=20) == 0
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(
                    json.dumps(
                        {
                            "passed": True,
                            "checks": [
                                "core and explicit alias metadata with live protection",
                                "dynamic screens",
                                "resource open/path rejection",
                                "scene pagination",
                                "target pagination",
                                "state endpoint",
                                "exact cancellation",
                                "session rejection",
                                "manual-only chat requests",
                                "stale draft rejection",
                                "typed settings and disk conflict",
                                "restart recovery without replay",
                                "corrupt receipts fail closed",
                                "8192 target and 50000 node boundaries",
                                "scene edits and selection",
                                "animation paths and undo",
                                "field and popup observations",
                                "model index beyond 100 stale binding",
                                "900 second restart expiry",
                                "headless scene run and stop",
                            ],
                            "visual_acceptance": "not performed",
                        },
                        indent=2,
                    )
                )
            except BaseException:
                print(log_path.read_text()[-10000:])
                raise
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
