"""Independent offline behavioral checks, run only against a newly built editor.
All project/config/artifacts live in a temporary self-contained editor copy.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from editor_test_isolation import copy_editor

GDSCRIPT = r"""@tool
extends SceneTree
var dock: Node
var heartbeat := 0
var checks: Array = []
var case_name := ""
func _initialize():
    _run.call_deferred()
func events(kind: String) -> int:
    var path := OS.get_environment("ACCEPT_EVENTS")
    if not FileAccess.file_exists(path):
        return 0
    var total := 0
    for line in FileAccess.get_file_as_string(path).split("\n"):
        var item = JSON.parse_string(line) if not line.is_empty() else null
        if item is Dictionary and item.get("kind", "") == kind:
            total += 1
    return total
func finish(ok: bool, reason := ""):
    var status = dock.get_ai_settings_control().find_child("ModelStatus", true, false) if dock != null else null
    var result := {"ok": ok, "case": case_name, "error": reason, "checks": checks, "heartbeat": heartbeat, "model_status": status.text if status != null else "", "user_data": OS.get_user_data_dir()}
    FileAccess.open(OS.get_environment("ACCEPT_RESULT"), FileAccess.WRITE).store_string(JSON.stringify(result))
    print("MODEL_ACCEPTANCE_RESULT=", JSON.stringify(result))
    quit(0 if ok else 2)
func wait_count(kind: String, count: int, seconds := 15.0) -> bool:
    var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
    while events(kind) < count and Time.get_ticks_msec() < deadline:
        await create_timer(0.05).timeout
    return events(kind) == count
func stable_count(kind: String, count: int) -> bool:
    await create_timer(1.5).timeout
    return events(kind) == count
func selected_backend(value: int):
    var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
    backend.select(value)
    backend.item_selected.emit(value)
func catalog_has(id: String) -> bool:
    var picker = dock.get_ai_settings_control().find_child("ModelPicker", true, false)
    for i in range(picker.item_count):
        if str(picker.get_item_metadata(i)) == id:
            return true
    return false
func wait_backend_ready(id: String, seconds := 15.0) -> bool:
    var backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)
    var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
    while Time.get_ticks_msec() < deadline:
        if backend != null and not backend.disabled and catalog_has(id):
            return true
        await create_timer(0.05).timeout
    return backend != null and not backend.disabled and catalog_has(id)
func _run():
    case_name = OS.get_environment("ACCEPT_CASE")
    var timer := Timer.new()
    timer.wait_time = 0.02
    timer.timeout.connect(func(): heartbeat += 1)
    root.add_child(timer)
    timer.start()
    await create_timer(0.25).timeout
    dock = root.find_child("AI Chat", true, false)
    if dock == null:
        finish(false, "missing AI Chat")
        return
    EditorInterface.set_main_screen_editor("AI Chat")
    if dock.get_ai_settings_control().find_child("RefreshModels", true, false) != null:
        finish(false, "manual refresh button still exists (old binary or incomplete change)")
        return
    checks.append("manual refresh button absent")
    var status = dock.get_ai_settings_control().find_child("ModelStatus", true, false)
    if case_name == "codex-startup":
        if not await wait_count("codex-model-list", 1) or not await stable_count("codex-model-list", 1):
            finish(false, "Codex startup must enumerate exactly once")
            return
        if not catalog_has("fixture-codex"):
            finish(false, "Codex advertised catalog missing")
            return
        checks.append("startup fetched advertised Codex model once")
    elif case_name in ["codex-login", "codex-busy-login", "codex-status-login-race"]:
        await create_timer(0.6).timeout
        if events("codex-model-list") != 0:
            finish(false, "logged-out startup unexpectedly enumerated models")
            return
        dock.get_ai_settings_control().find_child("CodexLogin", true, false).pressed.emit()
        if case_name == "codex-busy-login":
            dock.find_child("ConsultationOnly", true, false).button_pressed = true
            dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
            dock.find_child("ChatInput", true, false).text = "offline busy acceptance"
            dock.find_child("Send", true, false).pressed.emit()
            if not await wait_count("codex-offline-chat", 1):
                finish(false, "offline busy round did not start")
                return
        if not await wait_count("codex-login-success", 1) or not await wait_count("codex-model-list", 1, 20.0):
            finish(false, "login success did not eventually enumerate once")
            return
        if not await stable_count("codex-model-list", 1) or not catalog_has("fixture-codex"):
            finish(false, "duplicate or missing login model catalog")
            return
        checks.append("login completed, catalog eventually fetched exactly once")
        if case_name == "codex-status-login-race":
            checks.append("successful login superseded an older auth-status failure")
        if case_name == "codex-busy-login":
            if events("codex-offline-chat-done") != 1:
                finish(false, "refresh displaced the active chat")
                return
            checks.append("busy chat finished and pending login event survived")
    elif case_name == "codex-status-config-change":
        if not await wait_count("codex-login-status", 1):
            finish(false, "initial auth-status process did not start")
            return
        var entry = dock.get_environment_settings_control().find_child("CodexEntry", true, false)
        if not entry.editable:
            finish(false, "config-change fixture needs an editable field during auth-status check; review UI guard before judging product")
            return
        entry.text = OS.get_environment("ACCEPT_ALT_CODEX")
        entry.text_changed.emit(entry.text)
        if not await wait_count("codex-model-list", 1, 18.0) or not await stable_count("codex-model-list", 1):
            finish(false, "new Codex config event was lost behind stale auth-status process")
            return
        checks.append("changed config superseded a pending stale auth-status check")
    elif case_name == "codex-status-timeout":
        var deadline := Time.get_ticks_msec() + 35000
        while Time.get_ticks_msec() < deadline:
            if heartbeat >= 10 and ("超时" in status.text or "timeout" in status.text.to_lower()):
                break
            await create_timer(0.05).timeout
        if heartbeat < 10 or not ("超时" in status.text or "timeout" in status.text.to_lower()):
            finish(false, "auth status did not remain responsive and report a bounded timeout")
            return
        if events("codex-model-list") != 0:
            finish(false, "timed-out authentication triggered a catalog query")
            return
        checks.append("UI heartbeat continued during bounded auth-status timeout")
    elif case_name == "codex-catalog-failure":
        if not await wait_count("codex-model-list", 1) or not await stable_count("codex-model-list", 1):
            finish(false, "failure caused repeated model queries")
            return
        if "已获取" in status.text or catalog_has("fixture-codex") or status.text.is_empty() or not status.is_visible_in_tree():
            finish(false, "catalog failure not visibly distinguished from success")
            return
        checks.append("catalog failure visible without retry loop")
    elif case_name in ["api-chat-startup", "api-responses-startup", "codebuddy-startup"]:
        var kind := "codebuddy-model-list" if case_name == "codebuddy-startup" else "api-model-list"
        var id := "fixture-codebuddy" if case_name == "codebuddy-startup" else "fixture-api"
        if not await wait_count(kind, 1) or not await stable_count(kind, 1) or not catalog_has(id):
            finish(false, "configured backend startup cannot recover its catalog without the removed button")
            return
        checks.append("configured backend startup enumerated once")
    elif case_name == "backend-switch":
        if not await wait_count("codex-model-list", 1) or not await wait_backend_ready("fixture-codex"):
            finish(false, "initial Codex catalog or enabled selector missing")
            return
        for value in [0, 3, 1]:
            selected_backend(value)
            var kind := "codebuddy-model-list" if value == 1 else "api-model-list"
            var id := "fixture-codebuddy" if value == 1 else "fixture-api"
            var count := 1 if value != 3 else 2
            if not await wait_count(kind, count) or not await stable_count(kind, count) or not await wait_backend_ready(id):
                finish(false, "backend switch lost its one automatic refresh or selector remained disabled")
                return
        checks.append("all configured backend switches repopulated catalog once")
    else:
        finish(false, "unknown case")
        return
    finish(true)
"""

FAKE_CODEX = r"""import json, os, sys, time
from pathlib import Path
state = Path(__STATE__)
case = __CASE__
def event(kind):
    fd = os.open(state / 'events.jsonl', os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    os.write(fd, (json.dumps({'kind': kind, 'pid': os.getpid()})+'\n').encode()); os.close(fd)
a=sys.argv[1:]
if a[:2]==['login','status']:
    event('codex-login-status')
    if case in ['codex-status-timeout','codex-status-config-change']: time.sleep(90)
    if case=='codex-status-login-race' and not (state/'logged-in').exists(): time.sleep(4); sys.exit(1)
    sys.exit(0 if (state/'logged-in').exists() else 1)
if a and a[0]=='login':
    event('codex-login-start')
    time.sleep(0.8)
    (state/'logged-in').touch(); event('codex-login-success'); sys.exit(0)
if a and a[0]=='app-server':
    for line in sys.stdin:
        p=json.loads(line)
        if 'id' not in p: continue
        if p.get('method')=='initialize': result={}
        elif p.get('method')=='model/list':
            event('codex-model-list')
            if case=='codex-catalog-failure':
                print(json.dumps({'id':p['id'],'error':{'code':-32603,'message':'offline catalog failure'}}),flush=True);continue
            result={'data':[{'id':'fixture-codex','model':'fixture-codex','displayName':'Offline Codex','isDefault':True}],'nextCursor':None}
        else: result={}
        print(json.dumps({'id':p['id'],'result':result}),flush=True)
    sys.exit(0)
if a and a[0]=='exec':
    sys.stdin.read(); event('codex-offline-chat'); time.sleep(2.5); event('codex-offline-chat-done')
    print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'content':'OFFLINE_CHAT_FINISHED','actions':[]})}}),flush=True)
    print(json.dumps({'type':'turn.completed'}),flush=True); sys.exit(0)
sys.exit(3)
"""

FAKE_CODEBUDDY = r"""const fs = require('node:fs');
const state = __STATE__;
let pending='';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
 pending+=chunk; let end;
 while((end=pending.indexOf('\n'))>=0) {
  const line=pending.slice(0,end);pending=pending.slice(end+1);if(!line.trim())continue;
  const p=JSON.parse(line);
  if(p.type==='control_request') {
   fs.appendFileSync(state+'/events.jsonl',JSON.stringify({kind:'codebuddy-model-list',pid:process.pid})+'\n');
   console.log(JSON.stringify({type:'control_response',response:{request_id:p.request_id,subtype:'success',response:{models:[{id:'fixture-codebuddy',name:'Offline CodeBuddy'}]}}}));
  }
 }
});
"""

CASES = [
    "codex-startup",
    "codex-login",
    "codex-busy-login",
    "codex-status-timeout",
    "codex-catalog-failure",
    "codex-status-config-change",
    "codex-status-login-race",
    "api-chat-startup",
    "api-responses-startup",
    "codebuddy-startup",
    "backend-switch",
]


def private_editor(binary, directory):
    # The child gets no inherited binding; copy_editor audits its ancestors too.
    binding = os.environ.pop("GONGGONG_WORKSPACE", None)
    try:
        return copy_editor(binary, directory)
    finally:
        if binding is not None:
            os.environ["GONGGONG_WORKSPACE"] = binding


def run_case(binary, source, node, case, windows_job_boundary=None):
    with tempfile.TemporaryDirectory(prefix="issue387-independent-") as folder:
        root = Path(folder).resolve()
        (root / "state").mkdir()
        executable = private_editor(binary, root / "bin")
        (root / "SConstruct").touch()
        # Copy only the fixture bridge implementations, never live CLI packages.
        for name in ("codex_cli", "codebuddy_cli"):
            target = root / "tools" / name
            target.mkdir(parents=True)
            for bridge in (source / "tools" / name).glob("*.js"):
                shutil.copy2(bridge, target / bridge.name)
        boundary_receipt = None
        if os.name == "nt" and case in ("codebuddy-startup", "backend-switch"):
            relative_boundary = Path(
                "tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-x64/job-object.node"
            )
            installed_boundary = (windows_job_boundary or source / relative_boundary).resolve(strict=True)
            private_boundary = root / relative_boundary
            private_boundary.parent.mkdir(parents=True)
            shutil.copy2(installed_boundary, private_boundary)
            source_digest = hashlib.sha256(installed_boundary.read_bytes()).hexdigest()
            private_digest = hashlib.sha256(private_boundary.read_bytes()).hexdigest()
            if source_digest != private_digest:
                raise RuntimeError("Private Windows process-boundary module differs from its installed source")
            boundary_receipt = {
                "module": "win32-x64/job-object.node",
                "source_sha256": source_digest,
                "temporary_sha256": private_digest,
                "only_native_boundary_copied": True,
            }
        state = root / "state"
        project = root / "project"
        project.mkdir()
        project_name = "Issue387IndependentAcceptance-" + root.name
        (project / "project.godot").write_text(
            "config_version=5\n[application]\nconfig/name="
            + json.dumps(project_name)
            + '\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        (project / "accept.gd").write_text(GDSCRIPT)
        if case not in ["codex-login", "codex-busy-login", "codex-status-login-race"]:
            (state / "logged-in").touch()
        codex = root / "fake-codex"
        codex.write_text(
            "#!"
            + sys.executable
            + "\n"
            + FAKE_CODEX.replace("__STATE__", repr(str(state))).replace("__CASE__", repr(case))
        )
        codex.chmod(0o755)
        alt_codex = root / "fake-codex-fixed"
        alt_codex.write_text(
            "#!"
            + sys.executable
            + "\n"
            + FAKE_CODEX.replace("__STATE__", repr(str(state))).replace("__CASE__", repr("codex-startup"))
        )
        alt_codex.chmod(0o755)
        codebuddy = root / "fake-codebuddy.js"
        codebuddy.write_text(FAKE_CODEBUDDY.replace("__STATE__", json.dumps(str(state))))
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                with lock:
                    with (state / "events.jsonl").open("a") as stream:
                        stream.write(json.dumps({"kind": "api-model-list"}) + "\n")
                body = json.dumps({"data": [{"id": "fixture-api"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.send_error(500, "Unexpected inference request in offline model-list fixture")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        backend = (
            0
            if case == "api-chat-startup"
            else 3
            if case == "api-responses-startup"
            else 1
            if case == "codebuddy-startup"
            else 2
        )
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/" + ("responses" if backend == 3 else "chat/completions")
        settings = root / "bin/editor_data/editor_settings-4.8.tres"
        settings.parent.mkdir(parents=True, exist_ok=True)
        values = {
            "ai_chat/backend": backend,
            "ai_chat/codex_entry": str(codex),
            "ai_chat/codex_model": "unlisted-codex",
            "ai_chat/cli_node": str(node),
            "ai_chat/cli_bridge": str(root / "tools/codebuddy_cli/godot_bridge.js"),
            "ai_chat/cli_entry": str(codebuddy),
            "ai_chat/cli_model": "unlisted-codebuddy",
            "ai_chat/endpoint": endpoint,
            "ai_chat/model": "unlisted-api",
            "ai_chat/editor_control_bridge_enabled": False,
            "gonggong/workspace": "",
            "gonggong/python": "",
        }
        settings.write_text(
            '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
            + "\n".join(k + " = " + json.dumps(v, ensure_ascii=False) for k, v in values.items())
            + "\n"
        )
        output = root / "result.json"
        environment = {
            **{
                key: value
                for key, value in os.environ.items()
                if not any(
                    part in key.upper()
                    for part in (
                        "GONGGONG",
                        "AINATIVE",
                        "OPENAI",
                        "ANTHROPIC",
                        "CODEX",
                        "API_KEY",
                        "TOKEN",
                        "SECRET",
                        "CREDENTIAL",
                    )
                )
            },
            "ACCEPT_CASE": case,
            "ACCEPT_ALT_CODEX": str(alt_codex),
            "ACCEPT_EVENTS": str(state / "events.jsonl"),
            "ACCEPT_RESULT": str(output),
            "GODOT_AI_API_KEY": "offline-acceptance-key",
            "OPENAI_API_KEY": "",
            "APPDATA": str(root / "appdata"),
            "LOCALAPPDATA": str(root / "localappdata"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "CODEX_HOME": str(root / "codex-home"),
        }
        for key in (
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "CODEX_HOME",
            "TMP",
            "TEMP",
        ):
            if key not in environment or key in ("HOME", "USERPROFILE", "TMP", "TEMP"):
                environment[key] = str(root / "private-profile" / key.lower())
            Path(environment[key]).mkdir(parents=True, exist_ok=True)
        environment["PYTHONNOUSERSITE"] = "1"
        try:
            run = subprocess.run(
                [str(executable), "--headless", "--editor", "--path", str(project), "--script", "res://accept.gd"],
                env=environment,
                cwd=root,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            result = (
                json.loads(output.read_text(encoding="utf-8"))
                if output.exists()
                else {"ok": False, "error": "No behavioral receipt; possible blocked main thread"}
            )
            if boundary_receipt is not None:
                result["windows_job_boundary"] = boundary_receipt
            result["returncode"] = run.returncode
            result["ok"] = result.get("ok", False) and run.returncode == 0
            result["events"] = (
                [json.loads(line) for line in (state / "events.jsonl").read_text(encoding="utf-8").splitlines()]
                if (state / "events.jsonl").exists()
                else []
            )
            if not result["ok"]:
                result["diagnostic_tail"] = (run.stdout + run.stderr)[-4000:]
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "case": case,
                "error": "Editor acceptance timed out; responsiveness or operation did not finish",
            }
        finally:
            server.shutdown()
            server.server_close()
            if sys.platform == "darwin":
                owned_user_data = Path.home() / "Library/Application Support/Godot/app_userdata" / project_name
                if owned_user_data.is_dir():
                    shutil.rmtree(owned_user_data)
            # Kill only fixture children whose live command still contains this
            # unique temporary root. Never signal a real CLI or a reused PID.
            if (state / "events.jsonl").exists():
                for line in (state / "events.jsonl").read_text(encoding="utf-8").splitlines():
                    try:
                        pid = json.loads(line).get("pid")
                        if not isinstance(pid, int):
                            continue
                        probe = subprocess.run(
                            ["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
                        )
                        if probe.returncode == 0 and str(root) in probe.stdout:
                            os.kill(pid, signal.SIGTERM)
                    except (ValueError, OSError):
                        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--godot", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--node", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-sha")
    p.add_argument(
        "--windows-job-boundary",
        type=Path,
        help="Existing Windows x64 process-boundary module; only this file is copied into the private fixture bridge (defaults to the source tree module)",
    )
    p.add_argument("--case", choices=CASES, action="append")
    a = p.parse_args()
    source = a.source.resolve()
    checked_sources = [
        "editor/docks/ai_chat_dock.cpp",
        "editor/docks/ai_chat_dock.h",
        "tools/codex_cli/godot_bridge.js",
        "tools/codebuddy_cli/godot_bridge.js",
    ]
    hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in checked_sources}
    results = []
    # Freeze one tested artifact before all cases, even if the native owner later
    # produces another binary at the same build output pathname.
    with tempfile.TemporaryDirectory(prefix="issue387-frozen-artifact-") as folder:
        binary = private_editor(a.godot.resolve(), Path(folder) / "editor")
        binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
        if a.expected_sha and a.expected_sha != binary_sha:
            raise RuntimeError("Host artifact digest changed before independent validation")
        for case in a.case or CASES:
            result = run_case(binary, source, a.node.resolve(), case, a.windows_job_boundary)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            current = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in checked_sources}
            report = {
                "binary_sha256": binary_sha,
                "source_sha256": hashes,
                "source_unchanged": current == hashes,
                "provider": "Offline CLI/HTTP fixtures; real editor binary; no real inference",
                "isolated_settings": True,
                "results": results,
                "ok": all(r["ok"] for r in results) and current == hashes,
            }
            a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if report["ok"] else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
