"""Private native confirmation-boundary regression for SceneTreeEditor Tree cells.

Only this fixture emits a native approval signal, after first asserting that the
dedicated scene action waits despite auto-execute. This is not human approval.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from editor_test_isolation import copy_editor

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tree_guard_client", ROOT / "tools/editor_control_client.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Editor client module loader is unavailable")
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "schema_version": 1,
        "issue_number": 559,
        "request_id": "editor-command-gaps-batch-20261108",
        "kind": "private_native_scene_tree_confirmation_regression",
        "ok": False,
        "checks": [],
        "confirmation": "Private native signal only after asserting the manual boundary; not human approval",
        "limits": ["Isolated headless native editor; no production project, owner, credentials or OS UI tested."],
    }
    settings_path = Path.home() / "Library/Application Support/Godot/editor_settings-4.8.tres"
    settings_before = hashlib.sha256(settings_path.read_bytes()).hexdigest() if settings_path.exists() else None
    os.environ.pop("GONGGONG_WORKSPACE", None)
    with tempfile.TemporaryDirectory(prefix="scene-tree-cell-guard-") as temporary:
        base = Path(temporary)
        binary = copy_editor(args.godot, base / "editor")
        report["editor_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        project = base / "project"
        project.mkdir()
        (binary.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\n'
        )
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Private SceneTree confirmation fixture"\n'
        )
        (project / "fixture.tscn").write_text(
            '[gd_scene format=3]\n[node name="FixtureRoot" type="Node2D"]\n[node name="Victim" type="Node2D" parent="."]\n'
        )
        shutil.copyfile(ROOT / "tests/editor/scene_tree_cell_guard.gd", project / "test.gd")
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GONGGONG_") and key not in {"OPENAI_API_KEY", "GODOT_AI_API_KEY"}
        }
        for key in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"]:
            (base / key).mkdir()
            env[key] = str(base / key)
        with (base / "editor.log").open("wb") as output:
            process = subprocess.Popen(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                cwd=base,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            sequence = 0
            request_number = 0

            def until(callback, timeout=40):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError("Private editor exited: " + (base / "editor.log").read_text()[-4000:])
                    result = callback()
                    if result:
                        return result
                    time.sleep(0.03)
                raise AssertionError("Private native fixture timeout: " + (base / "editor.log").read_text()[-4000:])

            def command(action):
                nonlocal sequence
                sequence += 1
                pending = project / "command.pending"
                pending.write_text(json.dumps({"sequence": sequence, "action": action}))
                pending.replace(project / "command.json")
                ack = project / f"ack-{sequence}.json"
                return until(lambda: json.loads(ack.read_text()) if ack.exists() else None)

            def route(action, **values):
                nonlocal request_number
                request_number += 1
                request_id = f"tree-guard-{request_number}"
                result = client.route({
                    "intent": "engine_operation",
                    "source": "private-tree-guard",
                    "request_id": request_id,
                    "operation": {"action": action, **values},
                })
                return request_id, result

            try:
                until(lambda: (project / "ready.json").exists())
                ready = json.loads((project / "ready.json").read_text())
                client = client_module.EditorClient(project, process.pid)
                assert ready["scene_target"] and ready["scene_callback_attached"], ready
                until(lambda: route("read_tree_cells", target=ready["scene_target"])[1].get("error") != "editor_busy")
                _, reveal = route("main_screen", target="2D")
                assert reveal["ok"], reveal
                _, reveal = route("open_target", target=ready["scene_target"])
                assert reveal["ok"], reveal
                state = until(lambda: value if (value := command("snapshot"))["scene_widget_visible"] else None)
                description = route("describe_target", target=state["scene_target"])[1]
                assert "edit_tree_cell" not in description["actions"], description
                _, rejected = route(
                    "edit_tree_cell", target=state["scene_target"], index=state["scene_row"], column=0, value="Bypass"
                )
                assert rejected.get("error") == "scene_action_required", rejected
                assert rejected.get("required_action") == "scene_rename_node", rejected
                observed = command("snapshot")
                assert observed["victim_name"] == "Victim" and not observed["confirmation_visible"], observed
                report["checks"].append("Actual scene Tree omits generic edit and refuses auto-execute mutation")

                request_id, proposal = route("scene_rename_node", target="Victim", name="HumanApprovedName")
                assert proposal.get("confirmation_required") and proposal.get("manual_confirmation_required"), proposal
                observed = command("snapshot")
                assert observed["victim_name"] == "Victim" and observed["confirmation_visible"], observed
                assert command("approve")["was_visible"]
                result = client.status(request_id, "private-tree-guard")
                assert result["ok"], result
                assert command("snapshot")["victim_name"] == "HumanApprovedName"
                report["checks"].append(
                    "Dedicated scene rename waits despite auto-execute and changes only after native test approval"
                )

                _, ordinary_result = route(
                    "edit_tree_cell", target=ready["ordinary_target"], index=0, column=0, value="OrdinaryAutoExecuted"
                )
                assert ordinary_result["ok"] and ordinary_result["requested"], ordinary_result
                observed = command("snapshot")
                assert observed["ordinary_text"] == "OrdinaryAutoExecuted" and observed["ordinary_edits"] == 1, observed
                assert not observed["confirmation_visible"]
                report["checks"].append(
                    "Ordinary editable Tree preserves existing auto-execute behavior and native callback"
                )

                moved = command("reparent_native_widget")
                assert not moved["has_scene_editor_ancestor"] and moved["scene_callback_attached"], moved
                assert moved["scene_target"] and moved["compound_target"], moved
                _, rejected = route(
                    "edit_tree_cell",
                    target=moved["scene_target"],
                    index=moved["scene_row"],
                    column=0,
                    value="ReparentBypass",
                )
                assert rejected.get("error") == "scene_action_required", rejected
                report["checks"].append(
                    "Reparented actual native Tree remains guarded through its SceneTreeEditor callback owner"
                )
                _, alias = route(
                    "invoke_semantic_action",
                    target=moved["compound_target"],
                    value={
                        "name": "scene_rename_alias",
                        "arguments": {"index": moved["scene_row"], "column": 0, "value": "AliasBypass"},
                    },
                )
                assert alias.get("ok") is False and alias.get("error") == "semantic_declaration_unavailable", alias
                observed = command("snapshot")
                assert observed["victim_name"] == "HumanApprovedName" and not observed["confirmation_visible"], observed
                report["checks"].append("Compound declaration cannot advertise or forward a prohibited scene Tree edit")
                report["ok"] = True
            finally:
                if process.poll() is None:
                    try:
                        command("exit")
                    except Exception:
                        process.terminate()
                process.wait(timeout=15)
                report["native_log_sha256"] = hashlib.sha256((base / "editor.log").read_bytes()).hexdigest()
                settings_after = (
                    hashlib.sha256(settings_path.read_bytes()).hexdigest() if settings_path.exists() else None
                )
                report["user_settings_unchanged"] = settings_before == settings_after
                report["source_manifest"] = {
                    path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                    for path in [
                        "editor/docks/ai_chat_editor_complex_actions.cpp",
                        "editor/docks/ai_chat_editor_registry.cpp",
                        "editor/docks/ai_chat_dock.cpp",
                        "editor/docks/ai_chat_editor_scene_actions.cpp",
                        "editor/scene/scene_tree_editor.cpp",
                        "tests/editor/run_scene_tree_cell_guard.py",
                        "tests/editor/scene_tree_cell_guard.gd",
                    ]
                }
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
