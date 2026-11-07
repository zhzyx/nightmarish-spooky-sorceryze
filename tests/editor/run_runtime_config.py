"""Real-editor checks with private self-contained configuration and offline CLI."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = r"""@tool
extends SceneTree
var dock: Node
var checks: Array = []
func _initialize():
    run.call_deferred()
func finish(ok: bool, error := ""):
    FileAccess.open(OS.get_environment("RUNTIME_RESULT"), FileAccess.WRITE).store_string(JSON.stringify({"ok":ok,"error":error,"checks":checks}))
    quit(0 if ok else 2)
func wait_file(path: String, seconds := 30.0) -> bool:
    var deadline := Time.get_ticks_msec() + int(seconds * 1000)
    while not FileAccess.file_exists(path) and Time.get_ticks_msec() < deadline:
        await create_timer(0.04).timeout
    return FileAccess.file_exists(path)
func contains_reply(node: Node) -> bool:
    if node is RichTextLabel and "OFFLINE_CHAT_FINISHED" in node.get_parsed_text():
        return true
    for child in node.get_children():
        if contains_reply(child):
            return true
    return false
func connection_page(node: Node):
    if node.has_method("_open_connection"):
        return node
    for child in node.get_children():
        var found = connection_page(child)
        if found != null:
            return found
    return null
func run():
    await create_timer(0.4).timeout
    dock = root.find_child("AI Chat", true, false)
    if dock == null or not dock.has_method("get_runtime_configuration"):
        finish(false,"missing runtime API")
        return
    var runtime: Dictionary = dock.get_runtime_configuration()
    if runtime.get("config_path") != OS.get_environment("EXPECTED_CONFIG"):
        finish(false,"self-contained scope was not authoritative")
        return
    checks.append("self-contained path ignores ambient config locator")
    var role := OS.get_environment("RUNTIME_ROLE")
    if role == "B":
        if not await wait_file(OS.get_environment("A_OPEN")):
            finish(false,"original window did not open its connection page")
            return
        var field = dock.get_environment_settings_control().find_child("CLINode",true,false)
        var deadline := Time.get_ticks_msec()+20000
        while not field.editable and Time.get_ticks_msec()<deadline:
            await create_timer(0.04).timeout
        if not field.editable:
            finish(false,"node field did not become editable")
            return
        field.text = OS.get_environment("NODE_B")
        field.text_changed.emit(field.text)
        var workflow = dock.get_environment_settings_control().find_child("GongGongPython",true,false)
        workflow.text = OS.get_environment("PYTHON_B")
        workflow.text_changed.emit(workflow.text)
        FileAccess.open(OS.get_environment("B_SAVED"), FileAccess.WRITE).store_string("saved")
        finish(true)
        return
    if role == "A":
        var connection = connection_page(root)
        if connection == null:
            finish(false,"missing actual workspace connection page")
            return
        connection.call("_open_connection")
        FileAccess.open(OS.get_environment("A_OPEN"),FileAccess.WRITE).store_string("open")
        if not await wait_file(OS.get_environment("B_SAVED")):
            finish(false,"other window did not save")
            return
        runtime = dock.get_runtime_configuration()
        if runtime.paths.node != OS.get_environment("NODE_B") or dock.get_environment_settings_control().find_child("CLINode",true,false).text != OS.get_environment("NODE_A"):
            finish(false,"fixture did not retain stale UI while reading fresh config")
            return
        checks.append("other window edit read despite stale local LineEdit")
        var environment = dock.get_environment_settings_control()
        if environment.find_child("GongGongPython",true,false).text != OS.get_environment("VALID_PYTHON"):
            finish(false,"central environment fixture did not retain its original Python draft")
            return
        environment.find_child("GongGongWorkspace",true,false).text = OS.get_environment("OTHER_WORKSPACE")
        environment.find_child("SaveGongGongEnvironment",true,false).pressed.emit()
        await create_timer(0.5).timeout
        if dock.get_runtime_configuration().configured.workflow_python != OS.get_environment("PYTHON_B"):
            finish(false,"connection save overwrote another window's Python")
            return
        checks.append("workspace-only connection save retains another window's Python")
        if not str(runtime.paths.get("build_python", "")).is_empty():
            finish(false,"invalid legacy build Python was migrated")
            return
        var input = dock.find_child("ChatInput",true,false)
        var send = dock.find_child("Send",true,false)
        var deadline := Time.get_ticks_msec()+20000
        while send.disabled and Time.get_ticks_msec()<deadline:
            await create_timer(0.04).timeout
        dock.find_child("ConsultationOnly",true,false).button_pressed = true
        input.text = "Offline runtime configuration consultation"
        send.pressed.emit()
        deadline = Time.get_ticks_msec()+30000
        while not contains_reply(dock) and Time.get_ticks_msec()<deadline:
            await create_timer(0.04).timeout
        if not contains_reply(dock):
            finish(false,"real Codex bridge did not finish using the new Node")
            return
        checks.append("consultation works without build Python and uses actual CLI bridge")
        var build = dock.get_environment_settings_control().find_child("EngineBuildPython",true,false)
        build.text = OS.get_environment("VALID_PYTHON")
        build.text_changed.emit(build.text)
        runtime = dock.get_runtime_configuration()
        if runtime.paths.node != OS.get_environment("NODE_B") or runtime.configured.build_python != OS.get_environment("VALID_PYTHON"):
            finish(false,"single field write replaced another window's Node")
            return
        checks.append("single field merge retains concurrent Node update")
        dock.set_runtime_field("node", "relative-node-draft")
        dock.get_environment_settings_control().find_child("CLIBridge",true,false).text = "/missing/bridge.js"
        dock.get_environment_settings_control().find_child("CLIEntry",true,false).text = "/missing/codebuddy.js"
        var backend = dock.get_ai_settings_control().find_child("AIBackend",true,false)
        backend.select(1)
        backend.item_selected.emit(1)
        dock.get_ai_settings_control().find_child("CLILogin",true,false).pressed.emit()
        var login_error: String = dock.get_ai_settings_control().find_child("CLILoginStatus",true,false).text
        if not "Node.js" in login_error or not "Godot 对话桥接脚本" in login_error or not "CodeBuddy CLI 入口" in login_error:
            finish(false,"invalid CodeBuddy login did not report all runtime paths")
            return
        dock.set_runtime_field("node", OS.get_environment("NODE_B"))
        checks.append("invalid CodeBuddy login reports all paths without launching a terminal")
    elif role == "override":
        if runtime.paths.node != OS.get_environment("NODE_B") or runtime.sources.node != "environment" or runtime.configured.node != OS.get_environment("NODE_A"):
            finish(false,"temporary override did not stay separate")
            return
        OS.set_environment("GONGGONG_NODE", OS.get_environment("NODE_A"))
        if dock.get_runtime_configuration().paths.node != OS.get_environment("NODE_B"):
            finish(false,"internal environment export changed external override")
            return
        checks.append("external override frozen without durable overwrite")
    elif role == "cold":
        if runtime.paths.node != OS.get_environment("NODE_A") or runtime.sources.node != "configuration":
            finish(false,"temporary override leaked into a fresh launch")
            return
        checks.append("fresh launch reads durable path")
    elif role == "invalid-override":
        if runtime.sources.node != "environment" or not runtime.executables.node.is_empty():
            finish(false,"invalid external Node did not remain authoritative")
            return
        dock.prepare_runtime_configuration()
        var output: Array = []
        var code := "import importlib.util,json,sys;s=importlib.util.spec_from_file_location('runtime',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(json.dumps(m.read_effective()))"
        var exit_code := OS.execute(OS.get_environment("VALID_PYTHON"), ["-I","-c",code,OS.get_environment("RUNTIME_READER")],output)
        var child = JSON.parse_string(str(output[0])) if not output.is_empty() else null
        if exit_code != 0 or not child is Dictionary or child.sources.node != "environment" or not child.executables.node.is_empty():
            finish(false,"native child export silently fell back from an invalid external override")
            return
        checks.append("native export preserves invalid external override in isolated Python child")
    finish(true)
"""


def clone(source, target):
    result = (
        subprocess.run(["cp", "-c", str(source), str(target)], capture_output=True)
        if sys.platform == "darwin"
        else None
    )
    if result is None or result.returncode:
        shutil.copy2(source, target)


def run(args):
    spec = importlib.util.spec_from_file_location(
        "autofetch_fixture", args.source / "tests/editor/run_model_autofetch.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    results = []
    with tempfile.TemporaryDirectory(prefix="runtime-config-共工 space-") as temporary:
        root = Path(temporary).resolve()
        isolation_spec = importlib.util.spec_from_file_location(
            "editor_isolation", args.source / "tests/editor/editor_test_isolation.py"
        )
        isolation = importlib.util.module_from_spec(isolation_spec)
        isolation_spec.loader.exec_module(isolation)
        os.environ.pop("GONGGONG_WORKSPACE", None)
        bare = args.godot
        if any(part.endswith(".app") for part in bare.parts):
            bare = root / ("unpacked.exe" if os.name == "nt" else "unpacked")
            clone(args.godot, bare)
            assert hashlib.sha256(bare.read_bytes()).digest() == hashlib.sha256(args.godot.read_bytes()).digest()
        editor = root / "editor"
        binary = isolation.copy_editor(bare, editor)
        (root / "SConstruct").touch()
        (root / "tools").symlink_to(args.source / "tools", target_is_directory=True)
        state = root / "state"
        state.mkdir()
        (state / "logged-in").touch()
        codex = root / "offline-codex"
        codex.write_text(
            "#!"
            + sys.executable
            + "\n"
            + fixture.FAKE_CODEX.replace("__STATE__", repr(str(state))).replace("__CASE__", repr("codex-startup"))
        )
        codex.chmod(0o755)
        wrappers = {}
        for tag in ("A", "B"):
            wrapper = root / ("node-" + tag)
            wrapper.write_text(
                "#!"
                + sys.executable
                + "\nimport json,os,sys\nwith open("
                + repr(str(state / "node-events.jsonl"))
                + ",'a') as f:f.write(json.dumps({'tag':"
                + repr(tag)
                + ",'role':os.environ.get('RUNTIME_ROLE'),'argv':sys.argv[1:]})+'\\n')\nos.execv("
                + repr(str(args.node))
                + ", ["
                + repr(str(args.node))
                + ", *sys.argv[1:]])\n"
            )
            wrapper.chmod(0o755)
            wrappers[tag] = wrapper
        workflow = root / "python-B"
        workflow.write_text(
            "#!"
            + sys.executable
            + "\nimport os,sys\nos.execv("
            + repr(sys.executable)
            + ", ["
            + repr(sys.executable)
            + ", *sys.argv[1:]])\n"
        )
        workflow.chmod(0o755)
        workspaces = []
        for name in ("workspace-A", "workspace-B"):
            workspace = root / name
            board = workspace / "customizations/components/godot-host/daqian/board.py"
            board.parent.mkdir(parents=True)
            board.write_text(
                "import json,pathlib,sys\na=sys.argv[1:]\nif '--result' in a:pathlib.Path(a[a.index('--result')+1]).write_text(json.dumps({'denied':True,'error':'offline fixture'}))\n"
            )
            workspaces.append(workspace)
        settings = editor / "editor_data/editor_settings-4.8.tres"
        settings.parent.mkdir(exist_ok=True)
        values = {
            "ai_chat/backend": 2,
            "ai_chat/cli_node": str(wrappers["A"]),
            "ai_chat/codex_entry": str(codex),
            "ai_chat/codex_model": "fixture-codex",
            "ai_chat/cli_bridge": str(args.source / "tools/codebuddy_cli/godot_bridge.js"),
            "ai_chat/build_python": str(root / "missing-python"),
            "gonggong/python": sys.executable,
            "gonggong/workspace": str(workspaces[0]),
            "ai_chat/editor_control_bridge_enabled": False,
        }
        settings.write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "\n".join(key + " = " + json.dumps(value, ensure_ascii=False) for key, value in values.items())
            + "\n"
        )
        config = editor / "editor_data/gonggong/config.json"
        sentinel = root / "must-not-read-config.json"
        sentinel.write_text('{"schema_version":999}')
        sentinel_bytes = sentinel.read_bytes()
        environment = {
            **{
                key: value
                for key, value in os.environ.items()
                if not re.search(r"KEY|TOKEN|SECRET|CREDENTIAL|PASSWORD|AUTH", key, re.IGNORECASE)
                and not key.upper().startswith(("GONGGONG_", "AINATIVE_", "OPENAI_", "ANTHROPIC_", "CODEX_"))
            },
            **{
                name: ""
                for name in (
                    "GONGGONG_NODE",
                    "GONGGONG_PYTHON",
                    "GONGGONG_BUILD_PYTHON",
                    "GONGGONG_CODEX",
                    "GONGGONG_RUNTIME_DERIVED_ENV",
                )
            },
            "GONGGONG_RUNTIME_CONFIG": str(sentinel),
            "EXPECTED_CONFIG": str(config),
            "NODE_A": str(wrappers["A"]),
            "NODE_B": str(wrappers["B"]),
            "B_SAVED": str(state / "B-saved"),
            "VALID_PYTHON": sys.executable,
            "RUNTIME_READER": str(args.source / "tools/gonggong_runtime_config.py"),
            "PYTHON_B": str(workflow),
            "A_OPEN": str(state / "A-open"),
            "OTHER_WORKSPACE": str(workspaces[1]),
            "OPENAI_API_KEY": "",
            "GODOT_AI_API_KEY": "",
        }
        for name in (
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "TMP",
            "TEMP",
        ):
            private_path = root / "private-home" / name.lower()
            private_path.mkdir(parents=True, exist_ok=True)
            environment[name] = str(private_path)
        environment["PYTHONNOUSERSITE"] = "1"
        launched = []

        def launch(role):
            project = root / ("project-" + role)
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="RuntimeConfigAcceptance-'
                + root.name
                + "-"
                + role
                + '"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
            )
            (project / "check.gd").write_text(SCRIPT)
            output = root / (role + ".json")
            env = {**environment, "RUNTIME_ROLE": role, "RUNTIME_RESULT": str(output)}
            if role == "override":
                env["GONGGONG_NODE"] = str(wrappers["B"])
            elif role == "invalid-override":
                env["GONGGONG_NODE"] = str(root / "missing-external-node")
            stdout = (root / (role + ".stdout")).open("wb")
            stderr = (root / (role + ".stderr")).open("wb")
            process = subprocess.Popen(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://check.gd"],
                cwd=project,
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
            launched.append((process, stdout, stderr, output, role))
            return process

        try:
            launch("A")
            launch("B")
            for process, stdout, stderr, output, role in launched:
                code = process.wait(timeout=70)
                stdout.close()
                stderr.close()
                value = (
                    json.loads(output.read_text())
                    if output.exists()
                    else {"ok": False, "error": "missing editor receipt"}
                )
                value.update(
                    role=role, exit_code=code, stderr=(root / (role + ".stderr")).read_text(errors="replace")[-5000:]
                )
                results.append(value)
            node_events = [json.loads(line) for line in (state / "node-events.jsonl").read_text().splitlines()]
            assert any(
                value["tag"] == "B" and value["role"] == "A" and "chat" in value["argv"] for value in node_events
            ), node_events
            # Return to known durable Node before checking override and cold start.
            document = json.loads(config.read_text())
            document["runtimes"]["node"] = str(wrappers["A"])
            config.write_text(json.dumps(document))
            for role in ("override", "cold", "invalid-override"):
                process = launch(role)
                code = process.wait(timeout=30)
                _, stdout, stderr, output, _ = launched[-1]
                stdout.close()
                stderr.close()
                value = (
                    json.loads(output.read_text())
                    if output.exists()
                    else {"ok": False, "error": "missing editor receipt"}
                )
                value.update(
                    role=role, exit_code=code, stderr=(root / (role + ".stderr")).read_text(errors="replace")[-3000:]
                )
                results.append(value)
            assert sentinel.read_bytes() == sentinel_bytes and not Path(str(sentinel) + ".lock").exists()
            return {
                "ok": all(item["ok"] and item["exit_code"] == 0 for item in results),
                "artifact_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
                "cases": results,
                "node_events": node_events,
                "sentinel_untouched": True,
            }
        finally:
            for process, stdout, stderr, _, _ in launched:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                stdout.close()
                stderr.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.godot = args.godot.resolve()
    args.source = args.source.resolve()
    args.node = args.node.resolve()
    try:
        report = run(args)
    except Exception as error:
        report = {"ok": False, "error": repr(error)}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": report["ok"], "report": str(args.out)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
