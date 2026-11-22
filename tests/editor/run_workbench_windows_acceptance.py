"""Q10. Run the Q06 editor and its preview on a private, non-input Win32 desktop."""

import argparse
import ctypes as ct
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from ctypes import wintypes as wt
from datetime import datetime, timezone
from pathlib import Path

from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


class Startup(ct.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("reserved", wt.LPWSTR),
        ("desktop", wt.LPWSTR),
        ("title", wt.LPWSTR),
        *((key, wt.DWORD) for key in ("x", "y", "width", "height", "columns", "rows", "fill", "flags")),
        ("show", wt.WORD),
        ("reserved_len", wt.WORD),
        ("reserved_ptr", ct.c_void_p),
        ("stdin", wt.HANDLE),
        ("stdout", wt.HANDLE),
        ("stderr", wt.HANDLE),
    ]


class ProcessInfo(ct.Structure):
    _fields_ = [("process", wt.HANDLE), ("thread", wt.HANDLE), ("pid", wt.DWORD), ("tid", wt.DWORD)]


def win(dll, name, result, *parameters):
    function = getattr(dll, name)
    function.restype = result
    function.argtypes = parameters
    return function


user = ct.WinDLL("user32", use_last_error=True)
kernel = ct.WinDLL("kernel32", use_last_error=True)
create_desktop = win(
    user, "CreateDesktopW", wt.HANDLE, wt.LPCWSTR, wt.LPCWSTR, ct.c_void_p, wt.DWORD, wt.DWORD, ct.c_void_p
)
close_desktop = win(user, "CloseDesktop", wt.BOOL, wt.HANDLE)
attach = win(user, "SetThreadDesktop", wt.BOOL, wt.HANDLE)
thread_desktop = win(user, "GetThreadDesktop", wt.HANDLE, wt.DWORD)
window_thread = win(user, "GetWindowThreadProcessId", wt.DWORD, wt.HWND, ct.POINTER(wt.DWORD))
enum_proc = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
desktop_windows = win(user, "EnumDesktopWindows", wt.BOOL, wt.HANDLE, enum_proc, wt.LPARAM)
info = win(user, "GetUserObjectInformationW", wt.BOOL, wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD))
ancestor = win(user, "GetAncestor", wt.HWND, wt.HWND, wt.UINT)
owner_or_parent = win(user, "GetParent", wt.HWND, wt.HWND)
spawn = win(
    kernel,
    "CreateProcessW",
    wt.BOOL,
    wt.LPCWSTR,
    wt.LPWSTR,
    ct.c_void_p,
    ct.c_void_p,
    wt.BOOL,
    wt.DWORD,
    ct.c_void_p,
    wt.LPCWSTR,
    ct.POINTER(Startup),
    ct.POINTER(ProcessInfo),
)
wait = win(kernel, "WaitForSingleObject", wt.DWORD, wt.HANDLE, wt.DWORD)
exit_code = win(kernel, "GetExitCodeProcess", wt.BOOL, wt.HANDLE, ct.POINTER(wt.DWORD))
close = win(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)


def checked(value):
    if not value:
        raise ct.WinError(ct.get_last_error())
    return value


def desktop_name(desktop):
    name = ct.create_unicode_buffer(256)
    checked(info(desktop, 2, name, ct.sizeof(name), ct.byref(wt.DWORD())))
    return name.value


def read_window(hwnd, desktop):
    pid = wt.DWORD()
    checked(window_thread(hwnd, ct.byref(pid)))
    roots = []
    checked(desktop_windows(desktop, enum_proc(lambda handle, _: roots.append(handle) or True), 0))
    assert ancestor(hwnd, 2) in roots
    return {"hwnd": hwnd, "pid": pid.value, "desktop": desktop_name(desktop)}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


GAME = """extends Node2D

func _ready():
    var observation := {"pid": OS.get_process_id(), "hwnd": DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE),
            "display": DisplayServer.get_name(), "embedded": Engine.is_embedded_in_editor(), "scene": scene_file_path,
            "root": str(name), "score": get_meta("score"), "sha256": FileAccess.get_sha256(scene_file_path),
            "main_scene": ProjectSettings.get_setting("application/run/main_scene")}
    var file := FileAccess.open("res://child.json.tmp", FileAccess.WRITE)
    file.store_string(JSON.stringify(observation))
    file.close()
    DirAccess.rename_absolute("res://child.json.tmp", "res://child.json")
"""


def run(installed, scratch, receipt):
    from editor_control_client import EditorClient

    q06 = json.loads((ROOT / "data-collection/gonggong-ai-workbench-plan1-q06.json").read_text("utf-8"))
    manifest = json.loads((installed.parent / "installed.local.json").read_text("utf-8-sig"))
    assert manifest["main_revision"] == q06["freeze"]["source_commit"]
    bin_dir = scratch / "bin"
    bin_dir.mkdir()
    files = {}
    for entry in q06["installation"]["files"]:
        name = Path(entry["path"]).name
        copy = bin_dir / name
        shutil.copyfile(installed / name, copy)
        files[name] = sha(copy)
        assert files[name] == entry["sha256"] and copy.stat().st_size == entry["bytes"]
    editor = bin_dir / Path(manifest["default_editor"]).name
    receipt.update(
        source_commit=manifest["main_revision"],
        upstream_receipt="data-collection/gonggong-ai-workbench-plan1-q06.json",
        installation=files,
        host=platform.platform(),
        replay="python tests/editor/run_workbench_windows_acceptance.py --installed-bin <Q06 bin> "
        "--scratch-parent <private scratch> --report <new JSON file>",
        input_delivery="Godot InputEventKey via Window.push_input and native control signals on a private Win32 desktop",
        fixture_sha256={
            path.name: sha(path)
            for path in (
                Path(__file__),
                Path(__file__).with_name("workbench_windows_acceptance.gd"),
                Path(__file__).with_name("ai_chat_tab_order.gd"),
            )
        },
    )
    (bin_dir / "_sc_").touch()
    config = bin_dir / "editor_data"
    config.mkdir()
    (config / "editor_settings-4.8.tres").write_text(
        '[gd_resource type="EditorSettings" format=3]\n[resource]\ninterface/editor/editor_language = "en"\n'
        'ai_chat/editor_control_bridge_enabled = true\nai_chat/endpoint = ""\nrun/window_placement/game_embed_mode = 1\n',
        encoding="utf-8",
    )
    project = scratch / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Q10 private native acceptance"\nrun/main_scene="res://main.tscn"\n'
        "[display]\nwindow/size/viewport_width=320\nwindow/size/viewport_height=240\n"
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
        encoding="utf-8",
    )
    for fixture in ("workbench_windows_acceptance.gd", "ai_chat_tab_order.gd"):
        shutil.copyfile(Path(__file__).with_name(fixture), project / fixture)
    (project / "main.tscn").write_text('[gd_scene format=3]\n[node name="Main" type="Node2D"]\n', encoding="utf-8")
    part = project / "part.tscn"
    part.write_text(
        '[gd_scene format=3]\n[ext_resource type="Script" path="res://game.gd" id="1"]\n'
        '[node name="LocalPreview" type="Node2D"]\nscript = ExtResource("1")\nmetadata/score = 37\n',
        encoding="utf-8",
    )
    (project / "game.gd").write_text(GAME, encoding="utf-8")
    env = sanitized_environment(scratch)
    env["GONGGONG_WORKSPACE"] = str(project)
    env["GONGGONG_RUNTIME_CONFIG"] = str(project / "runtime.json")
    block = ct.create_unicode_buffer(
        "\0".join(f"{k}={v}" for k, v in sorted(env.items(), key=lambda p: p[0].upper())) + "\0"
    )
    name = "GongGong-Q10-" + uuid.uuid4().hex
    desktop = checked(create_desktop(name, None, None, 0, 0x01FF, None))
    original = checked(thread_desktop(kernel.GetCurrentThreadId()))
    startup = Startup(cb=ct.sizeof(Startup), desktop=name)
    child = ProcessInfo()
    log = project / "q10.log"
    args = [
        str(editor),
        "--display-driver",
        "windows",
        "--rendering-method",
        "gl_compatibility",
        "--audio-driver",
        "Dummy",
        "--editor",
        "--path",
        str(project),
        "--log-file",
        str(log),
        "--script",
        "res://workbench_windows_acceptance.gd",
    ]
    try:
        checked(attach(desktop))
        checked(
            spawn(
                str(editor),
                ct.create_unicode_buffer(subprocess.list2cmdline(args)),
                None,
                None,
                False,
                0x08000400,
                block,
                str(project),
                ct.byref(startup),
                ct.byref(child),
            )
        )
        checked(close(child.thread))

        def observe(key, timeout=40):
            path = project / (key + ".json")
            deadline = time.monotonic() + timeout
            while not path.exists():
                if wait(child.process, 40) == 0 or time.monotonic() > deadline:
                    raise RuntimeError(
                        f"Missing {key}. "
                        + (log.read_text("utf-8", errors="replace")[-3000:] if log.exists() else "No engine log")
                    )
            value = json.loads(path.read_text("utf-8"))
            receipt[key] = value
            return value

        display = observe("display")
        editor_window = read_window(display["hwnd"], desktop)
        assert editor_window["desktop"] == name and editor_window["pid"] == display["editor_pid"] == child.pid
        receipt["editor_window"] = editor_window
        for key in ("keyboard", "modal", "dock", "before_preview"):
            observe(key)
        client = EditorClient(project, child.pid)
        source = "q10"
        request_id = "preview-current-scene"
        request = {
            "intent": "engine_operation",
            "source": source,
            "request_id": request_id,
            "operation": {"action": "run_scene", "target": "res://part.tscn"},
        }
        offered = client.route(request)
        receipt["preview_request"] = {
            k: offered.get(k)
            for k in ("request_id", "source", "routing_status", "confirmation_required", "manual_confirmation_required")
        }
        assert offered.get("confirmation_required") and offered.get("manual_confirmation_required"), offered
        game = observe("child")
        assert game["display"] == "Windows" and game["embedded"] and game["main_scene"] == "res://main.tscn"
        assert (
            game["scene"] == "res://part.tscn"
            and game["root"] == "LocalPreview"
            and game["score"] == 37
            and game["sha256"] == sha(part)
        )
        embedded_view = observe("embedded_view")
        assert embedded_view["hwnd"] == display["hwnd"]
        game_window = read_window(game["hwnd"], desktop)
        game_window["owner_or_parent_hwnd"] = owner_or_parent(game["hwnd"])
        receipt["preview_window"] = game_window
        assert game_window["desktop"] == name and game_window["pid"] == game["pid"] != child.pid
        assert game_window["owner_or_parent_hwnd"] == editor_window["hwnd"], game_window
        result = client.status(request_id, source)
        receipt["preview_approval"] = {
            k: result.get(k) for k in ("ok", "request_id", "source", "routing_status", "run_requested", "target")
        }
        assert result.get("ok") and result.get("run_requested"), result
        (project / "observed-child").touch()
        observe("after_preview")
        assert wait(child.process, 20000) == 0
        code = wt.DWORD()
        checked(exit_code(child.process, ct.byref(code)))
        receipt["exit_code"] = code.value
        assert code.value == 0
        diagnostics = [
            line
            for line in log.read_text("utf-8", errors="replace").splitlines()
            if "SCRIPT ERROR" in line or line.startswith(("ERROR:", "WARNING:"))
        ]
        receipt["diagnostics"] = diagnostics
        assert not any("SCRIPT ERROR" in line for line in diagnostics)
    finally:
        if child.process:
            if wait(child.process, 0) != 0:
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=True,
                )
                assert wait(child.process, 15000) == 0
            checked(close(child.process))
        checked(attach(original))
        checked(close_desktop(desktop))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("Run with Python assertions enabled.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-bin", type=Path, required=True)
    parser.add_argument("--scratch-parent", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    args.scratch_parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "issue_number": 1733,
        "request_id": "gonggong-ai-workbench-plan1-q10",
        "passed": False,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with tempfile.TemporaryDirectory(dir=args.scratch_parent.resolve(), prefix="q10-") as folder:
            run(args.installed_bin.resolve(), Path(folder), receipt)
        receipt["passed"] = True
    finally:
        args.report.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
