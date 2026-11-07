"""Exercise the editor build UI, approval, progress, cancellation and restart.

Uses a tiny mock build worker to avoid a second full engine build. The replacement
is a separate copy of the real, successfully compiled editor. No live user editor
is touched. The restart test uses the normal EditorNode save/restart path.
"""

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MOCK = r"""
import argparse, json, time
from pathlib import Path
p = argparse.ArgumentParser()
for key in ('current', 'status', 'log', 'cancel'):
    p.add_argument('--' + key, required=True)
p.add_argument('--scons-arg', action='append', default=[])
a = p.parse_args()
if not all(Path(value).is_absolute() for value in (a.status, a.log, a.cancel)):
    p.error('External build workers require absolute filesystem paths')
path = Path(a.status)
mode = Path(__file__).with_name('mode').read_text()
def state(**data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data), encoding='utf-8')
    temp.replace(path)
Path(a.log).write_text('MOCK_BUILD_LOG\n', encoding='utf-8')
for percent in (0, 25, 50, 75, 99):
    if Path(a.cancel).exists():
        state(stage='cancelled', exit_code=1, error='Cancelled', percent=0)
        raise SystemExit(1)
    state(stage='building', percent=percent, estimated=True)
    time.sleep(0.4)
if mode == 'fail':
    state(stage='failed', exit_code=7, error='Mock compiler failure', percent=0)
    raise SystemExit(7)
artifact = Path(__file__).resolve().parents[1] / 'bin/godot.windows.editor.dev.x86_64.self_update_b.mono.exe'
state(stage='ready', percent=100, exit_code=0, executable=str(artifact))
"""

SCRIPT = r"""
@tool
extends SceneTree

func _initialize():
    _run.call_deferred()

func _check(ok: bool, message: String):
    if not ok:
        push_error(message)
        quit(1)
        return false
    return true

func _run():
    await process_frame
    await process_frame
    var dock = root.find_child("AI Chat", true, false)
    if not _check(dock != null, "AI Chat dock missing"):
        return
    var build = dock.get_environment_settings_control().find_child("BuildEngine", true, false)
    var restart = dock.get_environment_settings_control().find_child("RestartUpdatedEngine", true, false)
    var cancel = dock.find_child("CancelEngineBuild", true, false)
    var progress = dock.find_child("EngineBuildProgress", true, false)
    var status = dock.find_child("EngineBuildStatus", true, false)
    var approval = dock.find_child("EngineBuildApproval", true, false)
    dock.get_environment_settings_control().find_child("CLIBridge", true, false).text = OS.get_environment("SELF_UPDATE_TEST_ENGINE") + "/tools/codebuddy_cli/godot_bridge.js"
    dock.get_environment_settings_control().find_child("EngineBuildPython", true, false).text = OS.get_environment("SELF_UPDATE_TEST_PYTHON")
    dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = true
    dock.get_ai_settings_control().find_child("AutoExecuteCommands", true, false).button_pressed = false
    dock.get_environment_settings_control().find_child("EngineAutoRestart", true, false).button_pressed = false
    build.pressed.emit()
    if not _check(approval.visible and cancel.disabled, "Missing build approval or started without approval"):
        return
    approval.hide()
    approval.canceled.emit()
    if not _check(cancel.disabled and progress.value == 0, "Rejected build executed"):
        return
    var mode = FileAccess.open(OS.get_environment("SELF_UPDATE_TEST_ENGINE") + "/tools/mode", FileAccess.WRITE)
    mode.store_string("fail")
    mode.close()
    build.pressed.emit()
    approval.hide()
    approval.confirmed.emit()
    var seen = false
    var deadline = Time.get_ticks_msec() + 20000
    while build.disabled and Time.get_ticks_msec() < deadline:
        if progress.value > 0 and progress.value < 100:
            seen = true
        await process_frame
    if not _check(seen and restart.disabled and progress.value < 100 and "失败" in status.text,
            "Failure path: seen=%s, restart_disabled=%s, progress=%s, status=%s" % [seen, restart.disabled, progress.value, status.text]):
        return
    mode = FileAccess.open(OS.get_environment("SELF_UPDATE_TEST_ENGINE") + "/tools/mode", FileAccess.WRITE)
    mode.store_string("ok")
    mode.close()
    build.pressed.emit()
    approval.hide()
    approval.confirmed.emit()
    cancel.pressed.emit()
    deadline = Time.get_ticks_msec() + 20000
    while build.disabled and Time.get_ticks_msec() < deadline:
        await process_frame
    if not _check(restart.disabled and "取消" in status.text, "Cancellation updated editor or timed out"):
        return
    dock.get_environment_settings_control().find_child("EngineAutoRestart", true, false).button_pressed = true
    build.pressed.emit()
    approval.hide()
    approval.confirmed.emit()
    deadline = Time.get_ticks_msec() + 20000
    while Time.get_ticks_msec() < deadline:
        await process_frame
    push_error("Successful build did not automatically restart")
    quit(1)
"""

PLUGIN = r"""
@tool
extends EditorPlugin

func _enter_tree():
    _ready_check.call_deferred()

func _ready_check():
    if ".self_update_b." not in OS.get_executable_path():
        return
    await get_tree().process_frame
    await get_tree().process_frame
    var dock = get_tree().root.find_child("AI Chat", true, false)
    var project_path = ProjectSettings.globalize_path("res://").replace("\\", "/").trim_suffix("/")
    var expected_project = OS.get_environment("SELF_UPDATE_TEST_PROJECT").replace("\\", "/").trim_suffix("/")
    var ok = dock != null and FileAccess.file_exists("res://.godot/editor/ai_chat_history.json") and project_path == expected_project
    var receipt = FileAccess.open("res://receipt.tmp", FileAccess.WRITE)
    receipt.store_string(JSON.stringify({"ok": ok, "executable": OS.get_executable_path(), "pid": OS.get_process_id(), "project": project_path}))
    receipt.close()
    DirAccess.rename_absolute("res://receipt.tmp", "res://receipt.json")
    get_tree().quit(0 if ok else 1)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This self-update test targets Windows")
    with tempfile.TemporaryDirectory(prefix="self_update_test_", dir=ROOT / "bin") as directory:
        base = Path(directory)
        engine = base / "engine"
        project = base / "project"
        (engine / "tools/codebuddy_cli").mkdir(parents=True)
        (engine / "bin").mkdir()
        # Current hosts locate sources from the executable before consulting CLI
        # settings. Keep both the initial executable and source marker isolated.
        (engine / "SConstruct").write_text("# Isolated mock build fixture\n", encoding="utf-8")
        source_editor = args.godot.resolve()
        if source_editor.name.endswith(".console.exe"):
            source_editor = source_editor.with_name(source_editor.name.replace(".console.exe", ".exe"))
        initial = engine / "bin/godot.windows.editor.dev.x86_64.self_update_a.mono.exe"
        os.link(source_editor, initial)
        (project / "addons/restart_receipt").mkdir(parents=True)
        (engine / "tools/editor_self_build.py").write_text(MOCK, encoding="utf-8")
        (engine / "tools/mode").write_text("fail", encoding="utf-8")
        # The real watchdog, so the supervised handoff is exercised. Without it
        # the host silently falls back to an unsupervised restart and a broken
        # watchdog invocation would never be noticed here.
        shutil.copyfile(ROOT / "tools/editor_restart_watchdog.py", engine / "tools/editor_restart_watchdog.py")
        # A distinct executable proves the actual process was switched, not just reopened.
        artifact = engine / "bin/godot.windows.editor.dev.x86_64.self_update_b.mono.exe"
        os.link(source_editor, artifact)
        for name in ["GodotSharp", "D3D12Core.dll", "d3d12SDKLayers.dll"]:
            source = args.godot.resolve().parent / name
            destination = artifact.parent / name
            if source.is_dir():
                # Keep fixture cleanup independent of Windows junction handling.
                shutil.copytree(source, destination)
            elif source.is_file():
                os.link(source, destination)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Self Update Test"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n[editor_plugins]\nenabled=PackedStringArray("res://addons/restart_receipt/plugin.cfg")\n',
            encoding="utf-8",
        )
        (project / "integration.gd").write_text(SCRIPT, encoding="utf-8")
        (project / "addons/restart_receipt/plugin.gd").write_text(PLUGIN, encoding="utf-8")
        (project / "addons/restart_receipt/plugin.cfg").write_text(
            '[plugin]\nname="Restart Receipt"\ndescription="Integration fixture"\nauthor="Godot"\nversion="1"\nscript="plugin.gd"\n',
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["SELF_UPDATE_TEST_ENGINE"] = str(engine)
        env["SELF_UPDATE_TEST_PROJECT"] = str(project)
        env["SELF_UPDATE_TEST_PYTHON"] = sys.executable
        env["APPDATA"] = str(base / "appdata")
        env["LOCALAPPDATA"] = str(base / "localappdata")
        env["DOTNET_ROOT"] = str(ROOT / ".dotnet")
        env["DOTNET_ROOT_X64"] = str(ROOT / ".dotnet")
        env["PATH"] = str(ROOT / ".dotnet") + os.pathsep + env.get("PATH", "")
        command = [str(initial), "--headless", "--editor", "--path", str(project), "--script", "res://integration.gd"]
        # Native create_instance() does not promise inherited captured pipes.
        # Watch the atomic startup receipt instead of mistaking old-process exit
        # for new-process readiness, without racing fixture cleanup against startup.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.FindFirstChangeNotificationW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL, wintypes.DWORD]
        kernel.FindFirstChangeNotificationW.restype = wintypes.HANDLE
        kernel.FindNextChangeNotification.argtypes = [wintypes.HANDLE]
        kernel.FindCloseChangeNotification.argtypes = [wintypes.HANDLE]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        change = kernel.FindFirstChangeNotificationW(str(project), False, 0x001 | 0x010)
        if change == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        receipt = project / "receipt.json"
        try:
            result = subprocess.run(
                command, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=70
            )
            print(result.stdout)
            print(result.stderr)
            deadline = time.monotonic() + 20
            while result.returncode == 0 and not receipt.is_file():
                remaining = int((deadline - time.monotonic()) * 1000)
                if remaining <= 0 or kernel.WaitForSingleObject(change, remaining) != 0:
                    break
                if not kernel.FindNextChangeNotification(change):
                    raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.FindCloseChangeNotification(change)
        if result.returncode or not receipt.is_file():
            print("SELF_UPDATE_UI_RESTART_FAILED", result.returncode)
            return 1
        data = json.loads(receipt.read_text(encoding="utf-8"))
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        child = kernel.OpenProcess(0x00100000, False, data["pid"])
        if child:
            try:
                if kernel.WaitForSingleObject(child, 20000) != 0:
                    raise RuntimeError("Restarted test editor did not exit; fixture retained")
            finally:
                kernel.CloseHandle(child)
        elif ctypes.get_last_error() != 87:
            raise ctypes.WinError(ctypes.get_last_error())
        ok = (
            data["ok"]
            and ".self_update_b." in data["executable"]
            and Path(data["project"]).resolve() == project.resolve()
        )
        print("RESTART_RECEIPT", json.dumps(data, ensure_ascii=False))
        print("SELF_UPDATE_UI_RESTART_OK" if ok else "SELF_UPDATE_UI_RESTART_FAILED")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
