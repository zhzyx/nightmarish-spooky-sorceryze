"""Independent offline behavioral checks, run only against a newly built editor.
All project/config/artifacts live in a temporary self-contained editor copy.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
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
func fixture_pid_running(pid: int) -> bool:
    # Godot's process table only knows its direct children; inspect the actual
    # owned fixture descendant through the POSIX process table instead.
    var output: Array = []
    if OS.execute("/bin/ps", ["-p", str(pid), "-o", "stat="], output) != 0:
        return false
    var state := "".join(output).strip_edges()
    return not state.is_empty() and not state.begins_with("Z")
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
    for option in dock.get_model_catalog_snapshot().options:
        if option.id == id:
            return true
    return false
func project_model_is(id: String) -> bool:
    var field = dock.get_ai_settings_control().find_child("CodexModel", true, false)
    return field.text == id and EditorInterface.get_editor_settings().get_project_metadata("ai_chat", "codex_model", "") == id
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
    if not dock.has_method("get_model_catalog_snapshot") or dock.get_ai_settings_control().find_child("RefreshModels", true, false) == null:
        finish(false, "explicit catalog recovery API/button missing")
        return
    checks.append("explicit catalog recovery API/button available")
    var status = dock.get_ai_settings_control().find_child("ModelStatus", true, false)
    if case_name == "catalog-process-boundary":
        if OS.get_name() != "macOS" and OS.get_name() != "Linux":
            finish(false, "SIGSTOP timeout probe is POSIX-specific")
            return
        for attempt in [1, 2]:
            if attempt == 2:
                dock.refresh_model_catalog()
            if not await wait_count("catalog-descendants", attempt):
                finish(false, "real CLI descendant process did not start")
                return
            var event: Dictionary = {}
            for line in FileAccess.get_file_as_string(OS.get_environment("ACCEPT_EVENTS")).split("\n"):
                var item = JSON.parse_string(line) if not line.is_empty() else null
                if item is Dictionary and item.get("kind", "") == "catalog-descendants":
                    event = item
            var pids: Array = [int(event.pid), int(event.bridge_pid), int(event.descendant_pid)]
            if not pids.all(func(pid): return pid > 1 and fixture_pid_running(pid)):
                finish(false, "descendant ownership fixture did not observe all live PIDs")
                return
            if attempt == 1:
                dock.cancel_model_catalog()
            else:
                # Stop the real JS bridge's event loop: its own 30s timer cannot
                # help. The native 35s deadline must terminate the owned group.
                if OS.execute("/bin/kill", ["-STOP", str(int(event.bridge_pid))]) != 0:
                    finish(false, "could not suspend owned bridge for native-timeout probe")
                    return
                var timeout_deadline := Time.get_ticks_msec() + 40000
                while dock.get_model_catalog_snapshot().loading and Time.get_ticks_msec() < timeout_deadline:
                    await create_timer(0.05).timeout
                if dock.get_model_catalog_snapshot().state != "failed" or not "超时" in dock.get_model_catalog_snapshot().status:
                    finish(false, "native timeout did not finish the stalled catalog")
                    return
            var deadline := Time.get_ticks_msec() + 5000
            while pids.any(func(pid): return fixture_pid_running(pid)) and Time.get_ticks_msec() < deadline:
                await create_timer(0.05).timeout
            if pids.any(func(pid): return fixture_pid_running(pid)):
                finish(false, "cancel/timeout left a CLI or descendant PID alive")
                return
            checks.append("cancel terminated real bridge, CLI and SIGTERM-ignoring descendant" if attempt == 1 else "native 35s timeout terminated suspended bridge, CLI and SIGTERM-ignoring descendant")
    elif case_name in ["catalog-recovery", "api-recovery"]:
        var kind := "codex-model-list" if case_name == "catalog-recovery" else "api-model-list"
        var selected := "CodexModel" if case_name == "catalog-recovery" else "APIModel"
        if not await wait_count(kind, 1):
            finish(false, "initial catalog request did not reach fixture")
            return
        var deadline := Time.get_ticks_msec() + 10000
        while dock.get_model_catalog_snapshot().loading and Time.get_ticks_msec() < deadline:
            await create_timer(0.05).timeout
        if dock.get_model_catalog_snapshot().state != "failed" or not await stable_count(kind, 1):
            finish(false, "failed query must be actionable without an automatic retry loop")
            return
        checks.append("fixture counted initial failure; failure did not loop")
        # The actual UI recovery action must start another request, not a backend signal.
        dock.get_ai_settings_control().find_child("RefreshModels", true, false).pressed.emit()
        if not await wait_count(kind, 2):
            finish(false, "explicit retry was swallowed")
            return
        var ai = dock.get_ai_settings_control()
        var field = ai.find_child(selected, true, false)
        if not field.editable or ai.find_child("AIBackend", true, false).disabled or dock.find_child("Send", true, false).disabled or dock.find_child("AddAgent", true, false).disabled:
            finish(false, "catalog blocked independent controls")
            return
        field.text = "manual-during-query"
        field.text_changed.emit(field.text)
        var tabs = dock.find_child("AgentTabs", true, false)
        dock.find_child("AddAgent", true, false).pressed.emit()
        if tabs.tab_count != 2:
            finish(false, "catalog blocked creation of another session")
            return
        tabs.current_tab = 0
        tabs.tab_changed.emit(0)
        if dock.get_model_catalog_snapshot().current != "manual-during-query":
            finish(false, "switching session changed current project selection")
            return
        checks.append("pending catalog allows manual selection, new session and switching")
        dock.find_child("ConsultationOnly", true, false).button_pressed = true
        ai.find_child("AllowTools", true, false).button_pressed = false
        dock.find_child("ChatInput", true, false).text = "offline catalog concurrent acceptance"
        dock.find_child("Send", true, false).pressed.emit()
        if not await wait_count("codex-offline-chat" if case_name == "catalog-recovery" else "api-chat", 1):
            finish(false, "query prevented actual inference fixture start")
            return
        FileAccess.open(OS.get_environment("ACCEPT_CONTROL") + "/release-catalog", FileAccess.WRITE).store_string("release")
        deadline = Time.get_ticks_msec() + 5000
        while dock.get_model_catalog_snapshot().loading and Time.get_ticks_msec() < deadline:
            await create_timer(0.05).timeout
        if dock.get_model_catalog_snapshot().state != "ready" or dock.find_child("Stop", true, false).disabled:
            finish(false, "catalog completion reset active inference busy state")
            return
        if dock.get_model_catalog_snapshot().current != "manual-during-query":
            finish(false, "catalog completion overwrote manual selection")
            return
        if not await wait_count("codex-offline-chat-done" if case_name == "catalog-recovery" else "api-chat-done", 1):
            finish(false, "catalog stole or cancelled inference transport")
            return
        deadline = Time.get_ticks_msec() + 5000
        while not dock.find_child("Stop", true, false).disabled and Time.get_ticks_msec() < deadline:
            await create_timer(0.05).timeout
        checks.append("actual inference finished concurrently; catalog completion preserved busy state and selection")
        var snapshot: Dictionary = dock.get_model_catalog_snapshot()
        var provider_entries: Array = snapshot.options.filter(func(option): return option.id == "fixture-recovered")
        if provider_entries.size() != 1 or provider_entries[0].get("source", "").is_empty() or not provider_entries[0].get("reasoning_efforts", []).has("high"):
            finish(false, "stable snapshot lost source or advertised capability")
            return
        if case_name == "api-recovery" and (provider_entries[0].source != "fixture-wire" or snapshot.options.any(func(option): return typeof(option.id) != TYPE_STRING or option.id == "123")):
            finish(false, "source provenance or typed ID filtering lost")
            return
        if provider_entries[0].has("apiKey"):
            finish(false, "snapshot exported a private provider field")
            return
        snapshot.options.clear()
        if not catalog_has("fixture-recovered"):
            finish(false, "snapshot mutation modified native catalog")
            return
        checks.append("detached stable snapshot retains source and capability")
        dock.refresh_model_catalog()
        if not await wait_count(kind, 3):
            finish(false, "cancellable request did not start")
            return
        var previous: int = dock.get_model_catalog_snapshot().generation
        dock.get_ai_settings_control().find_child("CancelModels", true, false).pressed.emit()
        if dock.get_model_catalog_snapshot().loading or dock.get_model_catalog_snapshot().state != "cancelled":
            finish(false, "explicit cancel did not terminate catalog operation")
            return
        dock.refresh_model_catalog()
        if not await wait_count(kind, 4) or not await wait_backend_ready("fixture-current"):
            finish(false, "cancelled query could not retry")
            return
        if dock.get_model_catalog_snapshot().generation <= previous or dock.get_model_catalog_snapshot().current != "manual-during-query":
            finish(false, "retry generation or current selection invalid")
            return
        await create_timer(3.5).timeout
        if catalog_has("fixture-cancelled") or not catalog_has("fixture-current"):
            finish(false, "cancelled late result contaminated current catalog")
            return
        checks.append("cancel and retry counted separately; cancelled late response cannot replace current catalog")
        dock.refresh_model_catalog()
        if not await wait_count(kind, 5):
            finish(false, "configuration race request did not start")
            return
        OS.set_environment("OPENAI_BASE_URL", "https://changed.invalid/v1")
        if not await wait_count(kind, 6) or not await wait_backend_ready("fixture-new-environment"):
            finish(false, "changed effective environment did not isolate pending result and refresh")
            return
        if catalog_has("fixture-old-environment") or dock.get_model_catalog_snapshot().current != "manual-during-query":
            finish(false, "old environment result contaminated catalog or selection")
            return
        checks.append("environment identity change rejected late result and refreshed current source")
    elif case_name == "codex-completed-status-delayed-poll":
        # Hold the event loop until the actual subprocess has completed, then
        # delay the native poll beyond its deadline without changing any clock.
        var deadline := Time.get_ticks_msec() + 3000
        while events("codex-login-status") < 1 and Time.get_ticks_msec() < deadline:
            OS.delay_msec(10)
        if events("codex-login-status") != 1 or events("codex-model-list") != 0:
            finish(false, "status subprocess was not started before delayed poll")
            return
        var status_pid := 0
        for line in FileAccess.get_file_as_string(OS.get_environment("ACCEPT_EVENTS")).split("\n"):
            if line.is_empty():
                continue
            var event = JSON.parse_string(line)
            if event is Dictionary and event.get("kind", "") == "codex-login-status":
                # On Windows the editor owns the PE launcher's process handle;
                # the Python interpreter recording this event is its child.
                status_pid = int(event.get("entry_pid", 0))
        if status_pid < 2:
            finish(false, "actual fixture status PID missing")
            return
        deadline = Time.get_ticks_msec() + 3000
        while OS.is_process_running(status_pid) and Time.get_ticks_msec() < deadline:
            OS.delay_msec(10)
        if OS.is_process_running(status_pid) or OS.get_process_exit_code(status_pid) != 0:
            finish(false, "successful status child did not finish before delayed poll")
            return
        checks.append("successful status subprocess finished before delayed native poll")
        OS.delay_msec(11000)
        if not await wait_count("codex-model-list", 1) or not await wait_backend_ready("fixture-codex"):
            finish(false, "completed status result lost after delayed native poll")
            return
        if not await stable_count("codex-model-list", 1):
            finish(false, "delayed status poll caused duplicate automatic discovery")
            return
        checks.append("completed exit result survived an eleven second UI pause; catalog fetched once")
    elif case_name == "codex-startup":
        if not await wait_count("codex-model-list", 1) or not await stable_count("codex-model-list", 1):
            finish(false, "Codex startup must enumerate exactly once")
            return
        if not catalog_has("fixture-codex"):
            finish(false, "Codex advertised catalog missing")
            return
        checks.append("startup fetched advertised Codex model once")
    elif case_name == "session-reuse":
        if not await wait_count("codex-model-list", 1) or not await wait_backend_ready("fixture-codex"):
            finish(false, "initial Codex catalog missing")
            return
        var field = dock.get_ai_settings_control().find_child("CodexModel", true, false)
        var tabs = dock.find_child("AgentTabs", true, false)
        var draft = dock.find_child("ChatInput", true, false)
        draft.text = "session A draft"
        field.text = "parent-choice"
        field.text_changed.emit(field.text)
        dock.find_child("AddAgent", true, false).pressed.emit()
        if tabs.tab_count != 2 or not catalog_has("fixture-codex") or not project_model_is("parent-choice") or not draft.text.is_empty():
            finish(false, "new session did not reuse project selection/catalog with a separate draft")
            return
        draft.text = "session B draft"
        field.text = "child-choice"
        field.text_changed.emit(field.text)
        tabs.current_tab = 0
        tabs.tab_changed.emit(0)
        # AddAgent creates ordinary conversations, which share project AI settings.
        # Their drafts stay separate; execution-child overrides are a different path.
        if not project_model_is("child-choice") or not catalog_has("fixture-codex") or draft.text != "session A draft":
            finish(false, "A lost latest project selection/catalog or its own draft")
            return
        field.text = "updated-project-choice"
        field.text_changed.emit(field.text)
        tabs.current_tab = 1
        tabs.tab_changed.emit(1)
        if not project_model_is("updated-project-choice") or not catalog_has("fixture-codex") or draft.text != "session B draft":
            finish(false, "B lost updated project selection/catalog or its own draft")
            return
        if not await stable_count("codex-model-list", 1):
            finish(false, "session creation triggered duplicate discovery")
            return
        var entry = dock.get_environment_settings_control().find_child("CodexEntry", true, false)
        entry.text = OS.get_environment("ACCEPT_ALT_CODEX")
        entry.text_changed.emit(entry.text)
        if catalog_has("fixture-codex"):
            finish(false, "old catalog remained after connection changed")
            return
        checks.append("ordinary sessions share project selection and metadata in both directions while retaining separate drafts")
        checks.append("new session reused catalog without query; config change invalidated old catalog")
    elif case_name == "session-catalog-freshness":
        if not await wait_count("codex-model-list", 1) or not await wait_backend_ready("fixture-codex-old"):
            finish(false, "initial catalog C1 missing")
            return
        var field = dock.get_ai_settings_control().find_child("CodexModel", true, false)
        var tabs = dock.find_child("AgentTabs", true, false)
        field.text = "parent-choice"
        field.text_changed.emit(field.text)
        dock.find_child("AddAgent", true, false).pressed.emit()
        if tabs.tab_count != 2 or not catalog_has("fixture-codex-old") or not project_model_is("parent-choice"):
            finish(false, "B did not reuse C1 and project selection")
            return
        field.text = "child-choice"
        field.text_changed.emit(field.text)
        dock.get_ai_settings_control().find_child("CodexLogin", true, false).pressed.emit()
        if not await wait_count("codex-login-success", 1) or not await wait_count("codex-model-list", 2, 20.0) or not await wait_backend_ready("fixture-codex-new"):
            finish(false, "login refresh did not produce C2")
            return
        tabs.current_tab = 0
        tabs.tab_changed.emit(0)
        if not project_model_is("child-choice") or not catalog_has("fixture-codex-new") or catalog_has("fixture-codex-old"):
            finish(false, "A restored stale C1 instead of latest C2 or lost project selection")
            return
        tabs.current_tab = 1
        tabs.tab_changed.emit(1)
        if not project_model_is("child-choice") or not catalog_has("fixture-codex-new") or catalog_has("fixture-codex-old"):
            finish(false, "B lost C2 or project selection")
            return
        if not await stable_count("codex-model-list", 2):
            finish(false, "switching sessions duplicated the login catalog refresh")
            return
        checks.append("same-connection login refresh replaced archived C1 with C2 in both sessions and preserved project selection without duplicate discovery")
    elif case_name == "shared-config-inflight":
        if not await wait_count("codex-model-list", 2, 20.0) or not await wait_backend_ready("fixture-codex-new"):
            finish(false, "shared C2 change did not trigger a current-connection query")
            return
        if catalog_has("fixture-codex-old"):
            finish(false, "C1 response polluted the current C2 catalog")
            return
        dock.find_child("AddAgent", true, false).pressed.emit()
        if not catalog_has("fixture-codex-new") or catalog_has("fixture-codex-old"):
            finish(false, "new session reused a C1 response under C2")
            return
        checks.append("external shared-config edit during in-flight C1 query retained only C2 catalog")
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
    elif case_name == "external-status-config-change":
        if not await wait_count("codex-login-status", 2, 18.0) or not await wait_count("codex-model-list", 1, 18.0) or not await wait_backend_ready("fixture-codex"):
            finish(false, "external runtime edit left stale login status or never queried the current source")
            return
        var snap = dock.get_model_catalog_snapshot()
        var refresh = dock.get_ai_settings_control().find_child("RefreshModels", true, false)
        if snap.state != "ready" or snap.loading or refresh.disabled or not await stable_count("codex-model-list", 1):
            finish(false, "current-source recovery left refresh disabled or duplicated discovery")
            return
        checks.append("external runtime file edit during login-status check recovered current catalog and explicit refresh without UI signals")
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
        dock.find_child("AdvancedToggle", true, false).pressed.emit()
        await process_frame
        if "已获取" in status.text or catalog_has("fixture-codex") or status.text.is_empty() or not status.is_visible_in_tree():
            finish(false, "catalog failure not visibly distinguished from success after opening AI settings")
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

FAKE_CODEX = r"""import json, os, sys, time, signal, subprocess
from pathlib import Path
state = Path(__STATE__)
case = __CASE__
def event(kind, **extra):
    fd = os.open(state / 'events.jsonl', os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    entry_pid = os.getppid() if os.name == 'nt' else os.getpid()
    os.write(fd, (json.dumps({'kind': kind, 'pid': os.getpid(), 'entry_pid': entry_pid, **extra})+'\n').encode('utf-8')); os.close(fd)
a=sys.argv[1:]
if a[:2]==['login','status']:
    event('codex-login-status')
    if case in ['codex-status-timeout','codex-status-config-change']: time.sleep(90)
    if case=='external-status-config-change':
        time.sleep(.2)
        config=Path(__CONFIG_PATH__)
        temporary=config.with_suffix('.changed.tmp')
        temporary.write_text(json.dumps({'schema_version':1,'runtimes':{'codex':__ALT_CODEX__,'node':__NODE__}}))
        temporary.replace(config)
        time.sleep(.2)
    if case=='codex-status-login-race' and not (state/'logged-in').exists(): time.sleep(4); sys.exit(1)
    if case=='session-catalog-freshness' and (state/'refresh-login').exists(): sys.exit(0)
    sys.exit(0 if (state/'logged-in').exists() else 1)
if a and a[0]=='login':
    event('codex-login-start')
    time.sleep(0.8)
    (state/'logged-in').touch(); (state/'refresh-login').touch(); event('codex-login-success'); sys.exit(0)
if a and a[0]=='app-server':
    for line in sys.stdin:
        p=json.loads(line)
        if 'id' not in p: continue
        if p.get('method')=='initialize': result={}
        elif p.get('method')=='model/list':
            event('codex-model-list')
            if case=='catalog-process-boundary':
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                descendant = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(90)', str(state)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                event('catalog-descendants', bridge_pid=os.getppid(), descendant_pid=descendant.pid)
                while True: time.sleep(1)
            if case=='catalog-recovery':
                count = sum(json.loads(line)['kind']=='codex-model-list' for line in (state/'events.jsonl').read_text().splitlines())
                if count==1:
                    print(json.dumps({'id':p['id'],'error':{'code':-32603,'message':'offline catalog failure'}}),flush=True);continue
                if count==2:
                    deadline=time.monotonic()+15
                    while not (state/'release-catalog').exists() and time.monotonic()<deadline: time.sleep(.02)
                if count in [3,5]: time.sleep(3)
                model = {2:'fixture-recovered',3:'fixture-cancelled',4:'fixture-current',5:'fixture-old-environment',6:'fixture-new-environment'}.get(count,'unexpected-duplicate')
                result={'data':[{'id':model,'model':model,'displayName':'Offline Codex','supportedReasoningEfforts':[{'reasoningEffort':'high'}]}],'nextCursor':None}
                print(json.dumps({'id':p['id'],'result':result}),flush=True);continue
            if case=='codex-catalog-failure':
                print(json.dumps({'id':p['id'],'error':{'code':-32603,'message':'offline catalog failure'}}),flush=True);continue
            model = 'fixture-codex'
            if case == 'session-catalog-freshness':
                model = 'fixture-codex-new' if (state/'refresh-login').exists() else 'fixture-codex-old'
            elif case == 'shared-config-inflight':
                # Keep the C1 response in flight while the independent test
                # controller changes the shared durable configuration.
                time.sleep(1.0)
                model = 'fixture-codex-old'
            elif case == 'shared-config-current':
                model = 'fixture-codex-new'
            result={'data':[{'id':model,'model':model,'displayName':'Offline Codex','isDefault':True}],'nextCursor':None}
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
    "catalog-process-boundary",
    "catalog-recovery",
    "api-recovery",
    "codex-startup",
    "codex-completed-status-delayed-poll",
    "session-reuse",
    "session-catalog-freshness",
    "shared-config-inflight",
    "codex-login",
    "codex-busy-login",
    "codex-status-timeout",
    "codex-catalog-failure",
    "codex-status-config-change",
    "external-status-config-change",
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


def fixture_program(path, script):
    if os.name == "nt":
        # Match the existing native Python fixture launcher used by design-batch.
        # Windows CreateProcess cannot execute a Unix shebang script directly.
        from pip._vendor.distlib.scripts import ScriptMaker

        launcher = ScriptMaker(None, None)._get_launcher("t")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("__main__.py", script)
        path = path.with_suffix(".exe")
        path.write_bytes(launcher + ('#!"' + sys.executable + '"\n').encode() + archive.getvalue())
    else:
        path.write_text("#!" + sys.executable + "\n" + script, encoding="utf-8")
        path.chmod(0o700)
    return path


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
        if os.name == "nt":
            # Standalone Codex establishes its real Windows process boundary with
            # this helper when the optional CodeBuddy native module is absent.
            shutil.copy2(source / "tools/codex_cli/attach_job.ps1", root / "tools/codex_cli/attach_job.ps1")
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
            + '\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        (project / "accept.gd").write_text(GDSCRIPT, encoding="utf-8")
        if case not in ["codex-login", "codex-busy-login", "codex-status-login-race"]:
            (state / "logged-in").touch()
        config_file = root / "bin/editor_data/gonggong/config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        codex = fixture_program(
            root / "fake-codex",
            FAKE_CODEX
            .replace("__STATE__", repr(str(state)))
            .replace("__CASE__", repr(case))
            .replace("__CONFIG_PATH__", repr(str(config_file)))
            .replace("__ALT_CODEX__", repr(str(root / "fake-codex-fixed")))
            .replace("__NODE__", repr(str(node))),
        )
        alt_codex = fixture_program(
            root / "fake-codex-fixed",
            FAKE_CODEX
            .replace("__STATE__", repr(str(state)))
            .replace("__CASE__", repr("shared-config-current" if case == "shared-config-inflight" else "codex-startup"))
            .replace("__CONFIG_PATH__", repr(str(config_file)))
            .replace("__ALT_CODEX__", repr(str(root / "fake-codex-fixed")))
            .replace("__NODE__", repr(str(node))),
        )
        config_file.write_text(
            json.dumps({"schema_version": 1, "runtimes": {"codex": str(codex), "node": str(node)}}),
            encoding="utf-8",
        )
        codebuddy = root / "fake-codebuddy.js"
        codebuddy.write_text(FAKE_CODEBUDDY.replace("__STATE__", json.dumps(str(state))), encoding="utf-8")
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                with lock:
                    with (state / "events.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"kind": "api-model-list"}) + "\n")
                code = 200
                model = "fixture-api"
                if case == "api-recovery":
                    count = sum(
                        json.loads(line)["kind"] == "api-model-list"
                        for line in (state / "events.jsonl").read_text().splitlines()
                    )
                    code = 503 if count == 1 else 200
                    if count == 2:
                        deadline = time.monotonic() + 15
                        while not (state / "release-catalog").exists() and time.monotonic() < deadline:
                            time.sleep(0.02)
                    if count in (3, 5):
                        time.sleep(3)
                    model = {
                        2: "fixture-recovered",
                        3: "fixture-cancelled",
                        4: "fixture-current",
                        5: "fixture-old-environment",
                        6: "fixture-new-environment",
                    }.get(count, "unexpected-duplicate")
                body = json.dumps({
                    "data": [
                        {
                            "id": model,
                            "reasoning_efforts": ["high"],
                            "source": "fixture-wire",
                            "apiKey": "fixture-private-provider-field",
                        },
                        {"id": 123},
                    ]
                }).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_POST(self):
                if case != "api-recovery":
                    self.send_error(500, "Unexpected inference request in offline model-list fixture")
                    return
                self.rfile.read(int(self.headers["Content-Length"]))
                with lock, (state / "events.jsonl").open("a") as stream:
                    stream.write(json.dumps({"kind": "api-chat"}) + "\n")
                time.sleep(2.5)
                body = json.dumps({
                    "choices": [{"message": {"role": "assistant", "content": "OFFLINE_CHAT_FINISHED"}}]
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                with lock, (state / "events.jsonl").open("a") as stream:
                    stream.write(json.dumps({"kind": "api-chat-done"}) + "\n")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        backend = (
            0
            if case in ("api-chat-startup", "api-recovery")
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
            + "\n",
            encoding="utf-8",
        )
        output = root / "result.json"
        config_writer = None
        if case == "shared-config-inflight":

            def change_shared_config():
                events_file = state / "events.jsonl"
                import time

                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if events_file.exists() and any(
                        '"kind": "codex-model-list"' in line or '"kind":"codex-model-list"' in line
                        for line in events_file.read_text(encoding="utf-8").splitlines()
                    ):
                        replacement = {"schema_version": 1, "runtimes": {"codex": str(alt_codex), "node": str(node)}}
                        temporary = config_file.with_suffix(".json.tmp")
                        temporary.write_text(json.dumps(replacement), encoding="utf-8")
                        temporary.replace(config_file)
                        return
                    time.sleep(0.02)

            config_writer = threading.Thread(target=change_shared_config, daemon=True)
            config_writer.start()
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
            "ACCEPT_CONTROL": str(state),
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
                        event = json.loads(line)
                        for pid in (event.get("pid"), event.get("bridge_pid"), event.get("descendant_pid")):
                            if not isinstance(pid, int):
                                continue
                            probe = subprocess.run(
                                ["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
                            )
                            if probe.returncode == 0 and str(root) in probe.stdout:
                                os.kill(pid, signal.SIGKILL)
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
        "editor/docks/daqian/workspace.gd",
        "editor/docks/daqian/model_settings.gd",
        "tests/editor/run_model_autofetch.py",
        "tools/codex_cli/godot_bridge.js",
        "tools/codex_cli/attach_job.ps1",
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
        for case in a.case or [case for case in CASES if case != "catalog-process-boundary" or os.name != "nt"]:
            result = run_case(binary, source, a.node.resolve(), case, a.windows_job_boundary)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            current = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in checked_sources}
            report = {
                "binary_sha256": binary_sha,
                "source_sha256": hashes,
                "issue_number": 992,
                "request_id": "model-catalog-recovery-20261113",
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
