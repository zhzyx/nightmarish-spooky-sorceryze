"""Controlled remote ports for native mapped delivery; the finalizer stays real.

Only disposable installation copies are instrumented. Native confirmation,
independent decisions, guard serialization, provenance ownership, installed
parent adapter and finalizer/journal all execute normally. GitHub readbacks and
mutations terminate in a private JSON file, never an external repository.
"""

import ctypes
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

SCENARIOS = {"parent-finalize", "parent-finalize-stop", "parent-finalize-timeout", "parent-finalize-destroy"}


def timeout_observed(diagnostics):
    history = next(json.loads(item["body"]) for item in diagnostics if item["path"] == "history")
    results = [
        json.loads(message["content"])
        for agent in history["agents"]
        for message in agent.get("messages", [])
        if message.get("role") == "tool" and message.get("tool_call_id") == "native-finalize"
    ]
    return len(results) == 1 and results[0].get("timed_out") is True and results[0].get("ok") is False


def prepare(batch, env, command, scenario):
    installation = Path(command[0]).parent.parent
    tools = installation / "tools"
    if tools.is_symlink():
        tools.unlink()
    if not tools.exists():
        shutil.copytree(batch.ROOT / "tools", tools, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    assert tools.resolve().is_relative_to(installation)
    for name in ("customizations", "integrations", "framework", ".github"):
        target = installation / name
        if not target.exists():
            shutil.copytree(batch.ROOT / name, target, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    shutil.copyfile(batch.ROOT / "CURRENT_FRAMEWORK.json", installation / "CURRENT_FRAMEWORK.json")
    bridge = installation / "customizations/components/godot-host/bridge.py"
    marker = 'if __name__ == "__main__":'
    text = bridge.read_text()
    assert text.count(marker) == 1
    transport = (
        "if __name__ == '__main__' and sys.argv[1] in {'issue-agent', 'chat', 'flush'}:\n"
        "    exec(" + repr(batch.BRIDGE) + ")\n    sys.exit(0)\n\n"
    )
    bridge.write_text(text.replace(marker, transport + marker))
    ports = tools / "native_parent_delivery_ports.py"
    shutil.copyfile(Path(__file__), ports)
    finalizer = tools / "editor_delivery_finalize.py"
    text = finalizer.read_text()
    marker = "    result = complete(args.source_root, request)"
    assert text.count(marker) == 1
    finalizer.write_text(
        text.replace(
            marker,
            "    import native_parent_delivery_ports\n    native_parent_delivery_ports.install_finalizer(sys.modules[__name__], args.source_root, request)\n"
            + marker,
        )
    )
    env.update(
        DESIGN_BATCH_SOURCE=str(installation),
        NATIVE_PARENT_DELIVERY_MODE=scenario,
        NATIVE_PARENT_DELIVERY_STATE=str(installation / "native-delivery-state.json"),
    )


def install_finalizer(module, root, request):
    """Substitute only remote/account/activation ports, as in finalizer tests."""
    root = root.resolve()
    state_path = Path(os.environ["NATIVE_PARENT_DELIVERY_STATE"])
    binding = request["binding"]
    repository, issue_id = binding["repository"], binding["issue"]
    state = {
        "request": request,
        "writes": [],
        "comments": [],
        "issue": {
            "number": issue_id,
            "url": f"https://github.com/{repository}/issues/{issue_id}",
            "body": "<!-- gonggong-request:" + binding["request_id"] + " -->",
            "state": "OPEN",
            "stateReason": None,
            "labels": [{"name": x} for x in ("type:bug", "workspace:gonggong", "status:in-progress")],
        },
    }

    def save():
        module._candidate.atomic_json(state_path, state)

    def inspect(actual_root, actual_repository, pr):
        assert actual_root == root and actual_repository == repository and pr == request["pr"]
        head = module.submission.git(root, "rev-parse", "HEAD")
        assert head == request["expected_candidate"]
        issue = state["issue"]
        return {
            "repository": repository,
            "issue": issue_id,
            "request_id": binding["request_id"],
            "candidate": head,
            "signed_commit": request["expected_signed_commit"],
            "tree": module.submission.git(root, "rev-parse", "HEAD^{tree}"),
            "current_main": head,
            "merge_commit": head,
            "pull_request": f"https://github.com/{repository}/pull/{pr}",
            "pr_state": "MERGED",
            "delivered_paths_differ": [],
            "issue_receipt": {
                "state": issue["state"],
                "reason": issue["stateReason"],
                "labels": [v["name"] for v in issue["labels"]],
            },
        }

    def writer(actual_repository):
        assert actual_repository == repository
        if not state.get("started"):
            state.update(started=True, pid=os.getpid())
            save()
            if os.environ["NATIVE_PARENT_DELIVERY_MODE"] != "parent-finalize":
                # The original native 600-second timeout is not shortened.
                # After cancellation, the observer releases this gate to expose
                # an escaped process as an actual late controlled mutation.
                trigger = state_path.with_suffix(".release")
                while not trigger.exists():
                    time.sleep(0.02)
        return {"login": "fixture-operator", "databaseId": 77}

    def gh(*args):
        if args[:2] == ("pr", "view"):
            return json.dumps({
                "headRefOid": request["expected_signed_commit"],
                "statusCheckRollup": [{"name": "controlled remote CI", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            })
        if args[:2] == ("issue", "view"):
            return json.dumps(state["issue"])
        if args[0] == "api":
            return json.dumps([state["comments"]])
        state["writes"].append(list(args))
        if args[:2] == ("issue", "comment"):
            state["comments"].append({"body": Path(args[-1]).read_text()})
        elif "--add-label" in args:
            state["issue"]["labels"].append({"name": args[-1]})
        elif "--remove-label" in args:
            state["issue"]["labels"] = [v for v in state["issue"]["labels"] if v["name"] != args[-1]]
        elif args[:2] == ("issue", "close"):
            state["issue"].update(state="CLOSED", stateReason="COMPLETED")
        else:
            raise AssertionError(args)
        save()
        return ""

    module.submission.inspect_pr = inspect
    module.submission.writer = writer
    module.submission.work_items.gh = gh
    module._activation.after_delivery = lambda *_: {"state": "not_applicable", "reason": "isolated fixture"}
    save()


def model_response(batch, prompt, body):
    if not isinstance(prompt, str) or "current_host_design_batch" not in prompt:
        return None
    results = {m.get("tool_call_id"): m.get("content", "") for m in body["messages"] if m["role"] == "tool"}
    if "parent-verifier" not in results:
        return None
    assert json.loads(results["parent-verifier"])["exit_code"] == 0
    if "native-finalize-commit" not in results:
        code = "import subprocess;subprocess.run(['git','add','--all'],check=True);subprocess.run(['git','commit','--allow-empty','-m','Controlled mapped delivery candidate'],check=True)"
        return batch.tool_call("native-finalize-commit", "run_command", {"command": batch.python_command(code)})
    assert json.loads(results["native-finalize-commit"])["exit_code"] == 0
    assert "native-finalize" not in results, "Finalizer must end natively without another model turn"
    notice = json.loads(prompt[prompt.index("\n{") + 1 :])
    root = Path(notice["workspace"])
    candidate = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    return batch.tool_call(
        "native-finalize",
        "complete_delivery",
        {"pr": 7, "candidate": candidate, "signed_commit": "b" * 40, "acceptance_items": []},
    )


def scene(script):
    script = script.replace(
        "func _initialize():", "func _initialize():\n\tprocess_frame.connect(_native_delivery_observer)"
    )
    script = script.replace(
        '_wait_marker("DESIGN_BATCH_PARENT_VERIFIED_OK")',
        '_wait_marker("DESIGN_BATCH_PARENT_VERIFIED_OK", 740.0)',
    )
    return (
        script
        + """
var native_delivery_stopped := false
var native_delivery_finished := false
func _native_delivery_observer():
	if native_delivery_finished or not is_instance_valid(dock):
		return
	var path := OS.get_environment("NATIVE_PARENT_DELIVERY_STATE")
	if not FileAccess.file_exists(path):
		if dock.get_meta("parent_completion_state", "") == "readback_required":
			native_delivery_finished = true
			_check(false, "Delivery failed before the finalizer started; inspect retained worker diagnostic")
			_finish()
		return
	var state = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not state is Dictionary or not state.get("started", false):
		if dock.get_meta("parent_completion_state", "") == "readback_required":
			native_delivery_finished = true
			_check(false, "Finalizer initialization failed; inspect retained worker diagnostic")
			_finish()
		return
	var mode := OS.get_environment("NATIVE_PARENT_DELIVERY_MODE")
	var stop = dock.find_child("Stop", true, false)
	if mode == "parent-finalize-destroy":
		_check(not stop.disabled, "Delivery owner was not running before editor shutdown")
		native_delivery_finished = true
		_file("native-finalize-observed")
		_finish() # Actual editor shutdown exercises EXIT_TREE/destruction cancellation.
		return
	if mode == "parent-finalize-stop" and not native_delivery_stopped:
		_check(not stop.disabled, "Delivery owner was not running before Stop")
		native_delivery_stopped = true
		stop.pressed.emit()
		return
	if not stop.disabled:
		return
	if mode == "parent-finalize":
		_check(dock.get_meta("gonggong_status", "") == "delivery_completed", "Native finalization did not complete")
		_check(dock.get_meta("parent_business_accepted", false), "Native finalization lost complete acceptance")
	else:
		_check(not dock.get_meta("parent_business_accepted", false), "Cancelled delivery was accepted")
	native_delivery_finished = true
	_file("native-finalize-observed")
	_finish()
"""
    )


def collect(root):
    path = root / "native-delivery-state.json"
    if not path.exists():
        return {"started": False}
    before = json.loads(path.read_text())
    if not before.get("started"):
        return {
            "before_release": before,
            "after_release": before,
            "child_running_after_native_terminal": False,
            "late_mutations": False,
        }

    def running():
        if os.name == "nt":
            # os.kill(pid, 0) terminates processes on Windows. Only query here.
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, before["pid"])
            if not handle:
                if ctypes.get_last_error() == 87:
                    return False
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                code = wintypes.DWORD()
                if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                    raise ctypes.WinError(ctypes.get_last_error())
                return code.value == 259
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(before["pid"], 0)
            return True
        except ProcessLookupError:
            return False

    deadline = time.monotonic() + 3
    while running() and time.monotonic() < deadline:
        time.sleep(0.02)
    still_running = running()
    path.with_suffix(".release").touch()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        time.sleep(0.02)
    after = json.loads(path.read_text())
    return {
        "before_release": before,
        "after_release": after,
        "child_running_after_native_terminal": still_running,
        "late_mutations": after["writes"] != before["writes"],
    }
