"""Native acceptance integration fixture; isolated authority/model transports.

Runs the real native completion owner and installed Python/Node acceptance
implementation. Fixture GitHub responses describe the isolated fixture repository;
no accepted flag or replacement acceptance implementation is injected.
"""

import io
import re
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import native_parent_delivery as parent_delivery
import run_design_batch as batch

batch.EVENT_TENANT = "gonggong-workspace"
batch.INDEPENDENT_ACCEPTANCE = True

PARENT_SCENARIOS = {
    "parent-completion",
    "parent-cli",
    "parent-stop",
    "parent-tools-off",
    "parent-consultation",
    "parent-delivery-bypass",
    "parent-delivery-no-progress",
    "parent-cold",
}
PARENT_STOP_SCENARIOS = {"parent-stop", "parent-tools-off", "parent-consultation"}
PARENT_STOP_SCENARIOS |= {name + "-authorize" for name in tuple(PARENT_STOP_SCENARIOS)}
PARENT_STOP_SCENARIOS |= {"parent-delivery-tools-off", "parent-delivery-tools-off-authorize"}
PARENT_SCENARIOS |= PARENT_STOP_SCENARIOS
PARENT_SCENARIOS |= parent_delivery.SCENARIOS
SCENARIO = "pass"
if "--scenario" in sys.argv:
    at = sys.argv.index("--scenario")
    SCENARIO = sys.argv[at + 1]
    del sys.argv[at : at + 2]
if SCENARIO not in PARENT_SCENARIOS | {
    "pass",
    "parent-completion",
    "unknown",
    "stale",
    "empty",
    "no-permission",
    "cancel",
    "cancel-verify",
    "parallel",
    "parallel-repair",
    "parallel-evidence-completion",
    "parallel-evidence-exhausted",
    "parallel-integration",
    "parallel-config-drift",
    "parallel-self-review",
    "parallel-preflight-failure",
    "repair",
    "receipt-tamper",
    "receipt-as-evidence",
    "directory-failure",
    "auxiliary-tamper",
    "auxiliary-as-evidence",
}:
    raise SystemExit("Unknown native acceptance scenario")

if SCENARIO.startswith("parallel") and "--case" not in sys.argv:
    sys.argv.extend(["--case", "models-initial-ok"])

batch.BRIDGE = batch.BRIDGE.replace("'tenant_id':'fixture'", "'tenant_id':'gonggong-workspace'")
_original_dumps = batch.json.dumps


def fixture_json(value, *args, **kwargs):
    if isinstance(value, dict) and value.get("repository") == "example/design-batch":
        value = dict(value, tenant_id="gonggong-workspace")
    return _original_dumps(value, *args, **kwargs)


batch.json.dumps = fixture_json

batch.FINALIZED = batch.FINALIZED.replace(
    "1. DESIGN_BATCH_CHILD_1 checks its assigned evidence\n",
    "1. DESIGN_BATCH_CHILD_1 checks its assigned evidence\n- 验收: A | fixture-input.txt contains UNTRUSTED_FIXTURE_FILE and execution succeeds\n",
).replace(
    "2. DESIGN_BATCH_CHILD_2 checks its assigned evidence\n",
    "2. DESIGN_BATCH_CHILD_2 checks its assigned evidence\n- 依赖: 1\n- 验收: B | fixture-input.txt was read successfully\n",
)
if SCENARIO in PARENT_SCENARIOS:
    batch.FINALIZED = "<!-- gonggong-parent-completion:v1 -->\n" + batch.FINALIZED
    # Native confirmation is backed by a genuine installed intake read; only
    # the GitHub transport is controlled, as in all acceptance fixtures.
    batch.BRIDGE = batch.BRIDGE.replace(
        "elif action=='flush':",
        " if 'delegation' not in request:\n"
        "  spec=importlib.util.spec_from_file_location('parent_fixture_host',Path(os.environ['DESIGN_BATCH_SOURCE'])/'customizations/components/godot-host/bridge.py'); host=importlib.util.module_from_spec(spec); spec.loader.exec_module(host)\n"
        "  verified=host.issue_binding(root,dict(request,daqian_bound=True),'gonggong-workspace')['verified_issue_source']\n"
        "  spec=importlib.util.spec_from_file_location('parent_fixture_contract',Path(os.environ['DESIGN_BATCH_SOURCE'])/'customizations/components/godot-host/parent_completion.py'); parent_host=importlib.util.module_from_spec(spec); spec.loader.exec_module(parent_host)\n"
        "  value['parent_confirmation_source']=parent_host.authority_snapshot(verified)\n"
        "elif action=='flush':",
    )

if SCENARIO == "empty":
    batch.FINALIZED = batch.FINALIZED.replace(
        "- 验收: A | fixture-input.txt contains UNTRUSTED_FIXTURE_FILE and execution succeeds\n", ""
    )
if SCENARIO.startswith("parallel"):
    import native_acceptance_parallel as parallel

    batch.FINALIZED = batch.FINALIZED.replace("- 依赖: 1\n", "")
    batch.FINALIZED += "\n3. DESIGN_BATCH_CHILD_3 consumes A and B\n- 依赖: 1, 2\n- 验收: C | fixture-input.txt was read successfully\n"
_original_program = batch.fixture_program


def authority_program(path, source):
    if path.name == "fake-gh":
        source = source.replace("'number': 441,", "'number': 441, 'title': 'Native acceptance fixture',")
        source = source.replace(
            "assert sys.argv[-1].endswith('/441')",
            "\nif 'graphql' in sys.argv: print(json.dumps({'errors':[{}]}));sys.exit(0)\nif sys.argv[-1]=='user': print(json.dumps({'login':'fixture-operator'}));sys.exit(0)\n"
            "if sys.argv[-1].endswith('/permission'): print(json.dumps({'permission':'write'}));sys.exit(0)\n"
            "assert sys.argv[-1].endswith('/441')",
        )
    if path.name == "fake-gh" and SCENARIO in PARENT_SCENARIOS:
        finalized = batch.FINALIZED
        case = sys.argv[sys.argv.index("--case") + 1] if "--case" in sys.argv else "normal"
        numbers = [1, 2]
        if case == "normal":
            finalized = (
                finalized
                .replace("1. DESIGN", "2. DESIGN")
                .replace("2. DESIGN_BATCH_CHILD_2", "4. DESIGN_BATCH_CHILD_2")
                .replace("- 依赖: 1\n", "- 依赖: 2\n")
                + "   - 依赖：工单 2。\n"
            )
            numbers = [2, 4]
        contract = {
            "version": 1,
            "scope": "complete-original-task",
            "request_id": "design-batch-fixture",
            "issue_number": 441,
            "design_sha256": batch.hashlib.sha256(finalized.encode()).hexdigest(),
            "criteria": [
                {
                    "id": "original-A",
                    "order": numbers[0],
                    "criterion": "A",
                    "requirement": "fixture-input.txt contains UNTRUSTED_FIXTURE_FILE and execution succeeds",
                    "kind": "acceptance",
                },
                {
                    "id": "original-B",
                    "order": numbers[1],
                    "criterion": "B",
                    "requirement": "fixture-input.txt was read successfully",
                    "kind": "delivery",
                },
            ],
        }
        body = (
            "<!-- gonggong-request:design-batch-fixture -->\n```gonggong-parent-contract\n"
            + batch.json.dumps(contract)
            + "\n```\n"
        )
        graph = {
            "data": {
                "viewer": {"login": "fixture-operator", "databaseId": 77},
                "repository": {
                    "nameWithOwner": "example/design-batch",
                    "databaseId": 88,
                    "viewerPermission": "WRITE",
                    "issue": {
                        "number": 441,
                        "title": "Native acceptance fixture",
                        "state": "OPEN",
                        "url": "https://github.com/example/design-batch/issues/441",
                        "updatedAt": "2026-11-07T00:00:00Z",
                        "body": body,
                        "labels": {
                            "nodes": [{"name": x} for x in ["type:bug", "status:in-progress", "workspace:gonggong"]],
                            "pageInfo": {"hasNextPage": False},
                        },
                    },
                },
            }
        }
        source = source.replace("print(json.dumps({'errors':[{}]}))", "print(json.dumps(" + repr(graph) + "))")
    if path.name == "fake-gh" and SCENARIO == "no-permission":
        source = source.replace("'permission':'write'", "'permission':'read'")
    if path.name == "fake-gh" and SCENARIO == "cancel-verify":
        source = (
            "import os,time\nfrom pathlib import Path\nroot=Path(os.environ['DESIGN_BATCH_ROOT']).parent\nif list((root/'isolated-editor/editor_data/cache').glob('*.request.live')):\n (root/'original/samples/project/verify-transport-running').touch()\n time.sleep(3)\n"
            + source
        )
    return _original_program(path, source)


batch.fixture_program = authority_program
# The native Windows fixture ordinarily keeps real Git for candidate helpers.
# Its isolated origin uses insteadOf to avoid networking; the real intake reader
# needs the fixture Git transport to return the configured GitHub origin.
_original_run = batch.subprocess.run
integration_restore_report: dict[str, Any] = {}
integration_restarting = False
integration_binary = ""
parent_cold_report: dict[str, Any] = {}


def native_run(command, *args, **kwargs):
    global integration_restore_report, integration_restarting, integration_binary, parent_cold_report
    if SCENARIO in parent_delivery.SCENARIOS and "mklink" in command and Path(command[-2]).name == "tools":
        batch.shutil.copytree(
            batch.ROOT / "tools", Path(command[-2]), ignore=batch.shutil.ignore_patterns("node_modules", "__pycache__")
        )
        return batch.subprocess.CompletedProcess(command, 0, b"", b"")
    if SCENARIO.startswith("parallel") and "mklink" in command and Path(command[-2]).name == "tools":
        target = Path(command[-2])
        batch.shutil.copytree(
            batch.ROOT / "tools", target, ignore=batch.shutil.ignore_patterns("node_modules", "__pycache__")
        )
        batch.shutil.copytree(
            batch.ROOT / "customizations",
            target.parent / "customizations",
            ignore=batch.shutil.ignore_patterns("node_modules", "__pycache__"),
        )
        batch.shutil.copytree(
            batch.ROOT / "integrations",
            target.parent / "integrations",
            ignore=batch.shutil.ignore_patterns("node_modules", "__pycache__"),
        )
        batch.shutil.copytree(
            batch.ROOT / "framework",
            target.parent / "framework",
            ignore=batch.shutil.ignore_patterns("node_modules", "__pycache__"),
        )
        batch.shutil.copyfile(batch.ROOT / "CURRENT_FRAMEWORK.json", target.parent / "CURRENT_FRAMEWORK.json")
        native = Path("codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-x64/job-object.node")
        (target / native).parent.mkdir(parents=True, exist_ok=True)
        job_object = Path(batch.os.environ.get("NATIVE_ACCEPTANCE_JOB_OBJECT", str(batch.ROOT / "tools" / native)))
        if not job_object.is_absolute() or not job_object.is_file():
            raise RuntimeError(
                "Set NATIVE_ACCEPTANCE_JOB_OBJECT to the trusted installed Windows job-object.node absolute path"
            )
        batch.shutil.copyfile(job_object, target / native)
        return batch.subprocess.CompletedProcess(command, 0, b"", b"")
    env = kwargs.get("env")
    if env and "DESIGN_BATCH_PROJECT" in env and "--editor" in command:
        integration_binary = str(command[0])
        env = dict(env)
        env["NATIVE_ACCEPTANCE_SCENARIO"] = SCENARIO
        if SCENARIO in parent_delivery.SCENARIOS:
            parent_delivery.prepare(batch, env, command, SCENARIO)
            kwargs["timeout"] = 780
        if SCENARIO == "parent-delivery-no-progress":
            env["GONGGONG_KUAFU_LOCAL_ONLY"] = "1"
        if SCENARIO == "parent-cli":
            entry = Path(env["DESIGN_BATCH_ROOT"]).parent / "parent-model-fixture.js"
            entry.write_text(
                """'use strict';
const fs = require('node:fs');
if (process.argv.includes('app-server')) process.exit(2); // Controlled exec-only provider; real bridge fallback.
let text = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', value => text += value);
process.stdin.on('end', () => {
  const request = JSON.parse(text.slice(text.indexOf('\\n') + 1));
  if (!request.messages.some(m => m.role === 'user' && m.content.includes('BOUND_PARENT_STAGE'))) throw Error('Not the bound parent stage');
  const answer = {content: 'BOUND_PARENT_STAGE_A_FINISHED', actions: []};
  const events = [{type:'item.completed',item:{type:'agent_message',text:JSON.stringify(answer)}},{type:'turn.completed',usage:{}}];
  fs.writeFileSync(process.env.NATIVE_PARENT_CLI_LOG, JSON.stringify({request_seen:true, events}));
  process.stdout.write(events.map(e=>JSON.stringify(e)).join('\\n')+'\\n');
});
""",
                encoding="utf8",
            )
            # Runtime configuration requires an executable path on POSIX. Use
            # the existing executable fixture launcher (native PE on Windows),
            # forwarding unchanged stdio/arguments to the controlled provider.
            # The installed Codex bridge and native CLI callback remain real.
            launcher = _original_program(
                entry.with_name("parent-model-executable"),
                "import subprocess,sys\nraise SystemExit(subprocess.call("
                + repr([env["DESIGN_BATCH_NODE"], str(entry)])
                + " + sys.argv[1:]))\n",
            )
            env["NATIVE_PARENT_CLI_ENTRY"] = str(launcher)
            env["NATIVE_PARENT_CLI_LOG"] = str(entry.with_suffix(".receipt.json"))
        env["GONGGONG_GIT"] = str(
            Path(env["DESIGN_BATCH_PROJECT"]).parents[2] / ("git.exe" if batch.os.name == "nt" else "git")
        )
        if SCENARIO.startswith("parallel"):
            parallel.prepare(env)
            if SCENARIO == "parallel-preflight-failure":
                blocked = Path(command[0]).parent / "editor_data/cache/gonggong-dependency-evidence"
                blocked.parent.mkdir(parents=True, exist_ok=True)
                blocked.write_bytes(b"Actual storage obstruction; do not replace old evidence")
            batch.os.environ["NATIVE_PARALLEL_NODE"] = env["DESIGN_BATCH_NODE"]
            batch.os.environ["NATIVE_PARALLEL_PYTHON"] = env["DESIGN_BATCH_PYTHON"]
        kwargs["env"] = env
    completed = _original_run(command, *args, **kwargs)
    if (
        SCENARIO == "parallel-integration"
        and env
        and "DESIGN_BATCH_PROJECT" in env
        and "--editor" in command
        and completed.returncode == 0
    ):
        report_path = Path(env["DESIGN_BATCH_PROJECT"]) / "design-batch-report.json"
        initial_report = report_path.read_bytes()
        cold_kwargs = dict(kwargs)
        cold_kwargs["env"] = dict(kwargs["env"], DESIGN_BATCH_PHASE="integration-restore")
        cold_kwargs["timeout"] = 180
        integration_restarting = True
        restored = _original_run(command, *args, **cold_kwargs)
        integration_restore_report = batch.json.loads(report_path.read_text(encoding="utf8"))
        assert restored.returncode == 0, restored.stdout + restored.stderr
        assert (
            integration_restore_report["ok"] and "NATIVE_INTEGRATION_RECOVERED" in integration_restore_report["stages"]
        ), integration_restore_report
        # The base fixture assesses the first run; keep both real reports.
        report_path.with_name("integration-restore-report.json").write_bytes(report_path.read_bytes())
        report_path.write_bytes(initial_report)
        completed = batch.subprocess.CompletedProcess(
            command, restored.returncode, completed.stdout + restored.stdout, completed.stderr + restored.stderr
        )
    if (
        SCENARIO == "parent-cold"
        and env
        and "DESIGN_BATCH_PROJECT" in env
        and "--editor" in command
        and completed.returncode == 0
    ):
        report_path = Path(env["DESIGN_BATCH_PROJECT"]) / "design-batch-report.json"
        first_report = report_path.read_bytes()
        count = len(parent_stages)
        cold_kwargs = dict(kwargs, env=dict(kwargs["env"], DESIGN_BATCH_PHASE="parent-cold"))
        cold = _original_run(command, *args, **cold_kwargs)
        parent_cold_report = batch.json.loads(report_path.read_text())
        parent_cold_report["new_parent_stages"] = len(parent_stages) - count
        parent_cold_report["exit_code"] = cold.returncode
        report_path.with_name("parent-cold-report.json").write_text(batch.json.dumps(parent_cold_report))
        report_path.write_bytes(first_report)
    return completed


batch.subprocess.run = native_run

_original_copyfile = batch.shutil.copyfile


def fixture_copyfile(source, target, *args, **kwargs):
    result = _original_copyfile(source, target, *args, **kwargs)
    if Path(source).name == "design_batch.gd" and SCENARIO in PARENT_SCENARIOS | {
        "pass",
        "parent-completion",
        "repair",
        "parallel",
        "parallel-repair",
        "parallel-evidence-completion",
        "parallel-evidence-exhausted",
        "parallel-integration",
    }:
        # Independent review and a repair add real processes to the base batch.
        # Keep the wait bounded while allowing those extra completion events.
        script = Path(target).read_text(encoding="utf8")
        script = script.replace("seconds := 90.0", "seconds := 180.0")
        # This fixture completes through independent native acceptance. The
        # ordinary batch separately tests the manual acceptance/consultation UI.
        script = script.replace("\t\tawait _verify_dependency_handoff()", "\t\tpass")
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO in PARENT_SCENARIOS:
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            '"ok": failure.is_empty(), "failure": failure, "stages": stages,',
            '"ok": failure.is_empty(), "failure": failure, "stages": stages, "parent_completion_state": dock.get_meta("parent_completion_state", ""), "parent_business_accepted": dock.get_meta("parent_business_accepted", false),',
        )
        script = script.replace(
            '\t\tawait create_timer(1.0).timeout\n\t\tvar tabs = dock.find_child("AgentTabs", true, false)',
            '\t\tfor attempt in range(1800):\n\t\t\tif dock.get_meta("parent_completion_state", "") == "complete":\n\t\t\t\tbreak\n\t\t\tawait create_timer(0.05).timeout\n\t\t_check(dock.get_meta("parent_business_accepted", false), "Complete contract did not reach independent acceptance")\n\t\tvar tabs = dock.find_child("AgentTabs", true, false)',
        )
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO in PARENT_STOP_SCENARIOS:
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            "func _initialize():", "func _initialize():\n\tprocess_frame.connect(_parent_cancel_boundary)"
        )
        script += """
var parent_cancelled := false
var parent_cancel_finished := false
func _parent_cancel_boundary():
	if not is_instance_valid(dock) or parent_cancel_finished:
		return
	var scenario := OS.get_environment("NATIVE_ACCEPTANCE_SCENARIO")
	var boundary := "authorize" if scenario.ends_with("-authorize") else "check"
	if not parent_cancelled and dock.get_meta("parent_completion_state", "") == boundary:
		parent_cancelled = true
		if scenario.begins_with("parent-stop"):
			dock.find_child("Stop", true, false).pressed.emit()
		elif "tools-off" in scenario:
			dock.get_ai_settings_control().find_child("AllowTools", true, false).button_pressed = false
		else:
			dock.find_child("ConsultationOnly", true, false).button_pressed = true
	if parent_cancelled and dock.find_child("Stop", true, false).disabled:
		parent_cancel_finished = true
		_check(not dock.get_meta("parent_business_accepted", false), "Cancelled parent was accepted")
		_file("native-parent-cancelled")
		_finish()
"""
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO == "parent-cli":
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            "\tconfirmation.get_ok_button().pressed.emit()\n\nfunc _verify_dependency_handoff",
            '\tconfirmation.get_ok_button().pressed.emit()\n\t_check(dock.set_runtime_field("codex", OS.get_environment("NATIVE_PARENT_CLI_ENTRY")).is_empty(), "Cannot bind controlled Codex")\n\tvar selected_backend = dock.get_ai_settings_control().find_child("AIBackend", true, false)\n\tselected_backend.select(2)\n\t# Controlled transport selection; do not simulate a human mid-bind connection reset.\n\tdock.get_ai_settings_control().find_child("CodexModel", true, false).text = "controlled-parent"\n\nfunc _verify_dependency_handoff',
        )
        script = script.replace(
            "func _work_event(_workspace: String, _binding: Dictionary, _worker: String, kind: String, _phase: String, status: String):",
            'func _work_event(_workspace: String, _binding: Dictionary, _worker: String, kind: String, _phase: String, status: String):\n\tif not parent_cli_restore_scheduled and kind == "request_end" and status == "completed" and dock.get_meta("parent_completion_state", "") == "dispatch_registered":\n\t\tparent_cli_restore_scheduled = true\n\t\t_file("native-parent-cli-completed")\n\t\t_restore_parent_cli_runtime.call_deferred()',
        )
        script += '\nvar parent_cli_restore_scheduled := false\nfunc _restore_parent_cli_runtime():\n\t# The terminal signal precedes busy=false; restore only after that owner releases.\n\t_check(dock.find_child("Stop", true, false).disabled, "CLI parent terminal owner has not released")\n\tdock.get_ai_settings_control().find_child("AIBackend", true, false).select(0)\n\t_check(dock.set_runtime_field("codex", OS.get_environment("DESIGN_BATCH_NODE")).is_empty(), "Cannot restore fixture runtime after CLI parent terminal")\n'
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO == "parent-delivery-no-progress":
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            "func _initialize():", "func _initialize():\n\tprocess_frame.connect(_parent_no_progress_boundary)"
        )
        script += """
var parent_no_progress_finished := false
func _parent_no_progress_boundary():
	if parent_no_progress_finished or not is_instance_valid(dock):
		return
	if dock.get_meta("parent_completion_state", "") != "kuafu_required" or not dock.find_child("Stop", true, false).disabled:
		return
	parent_no_progress_finished = true
	await create_timer(1.0).timeout
	_check(dock.find_child("Stop", true, false).disabled, "Bounded stop resumed a model request")
	_check(not dock.get_meta("parent_business_accepted", false), "No-progress parent was accepted")
	_file("native-parent-no-progress")
	_finish()
"""
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO == "parent-cold":
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            '\tif OS.get_environment("DESIGN_BATCH_PHASE") == "blocked-restore":',
            '\tif OS.get_environment("DESIGN_BATCH_PHASE") == "parent-cold":\n\t\tawait create_timer(2.0).timeout\n\t\t_check(dock.find_child("Stop", true, false).disabled, "Cold history resumed a parent")\n\t\t_check(not dock.get_meta("parent_business_accepted", false), "Cold history restored live acceptance")\n\t\t_finish()\n\t\treturn\n\tif OS.get_environment("DESIGN_BATCH_PHASE") == "blocked-restore":',
        )
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO.startswith("parallel"):
        script = Path(target).read_text(encoding="utf8")
        # External parallel workers have their own verified lifecycle; the
        # base HTTP child handshake is exercised only by the directory suite.
        script = script.replace('if mode.begins_with("models-initial-"):', "if false:")
        script = script.replace("await _observe_models(mode)", 'await _wait_marker("DESIGN_BATCH_PARENT_VERIFIED_OK")')
        script = script.replace(
            'settings.set_setting("ai_chat/parallel_work_orders_config", "")',
            'settings.set_setting("ai_chat/parallel_work_orders_config", OS.get_environment("NATIVE_PARALLEL_CONFIG"))',
        )
        if SCENARIO == "parallel-preflight-failure":
            script = script.replace(
                '_wait_marker("DESIGN_BATCH_PARENT_VERIFIED_OK")',
                '_wait_marker("dependency_evidence_persist_failed_or_capacity_exceeded", 90.0, false)',
            )
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO == "parallel-integration":
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            '\tvar mode := OS.get_environment("DESIGN_BATCH_CASE")\n\tif OS.get_environment("DESIGN_BATCH_PHASE") == "review-restore":',
            '\tvar mode := OS.get_environment("DESIGN_BATCH_CASE")\n\tif OS.get_environment("DESIGN_BATCH_PHASE") == "integration-restore":\n\t\tawait create_timer(0.5).timeout\n\t\t_check(dock.find_child("Stop", true, false).disabled, "Cold integration restarted work without user input")\n\t\tdock.get_ai_settings_control().find_child("APIKey", true, false).text = "design-batch-isolated-secret"\n\t\t_send("NATIVE_INTEGRATION_RECOVERY")\n\t\tawait _wait_marker("NATIVE_INTEGRATION_RECOVERED", 120.0)\n\t\t_finish()\n\t\treturn\n\tif OS.get_environment("DESIGN_BATCH_PHASE") == "review-restore":',
        )
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO in {"cancel", "cancel-verify"}:
        script = Path(target).read_text(encoding="utf8")
        script = script.replace(
            "func _initialize():", "func _initialize():\n\tprocess_frame.connect(_cancel_native_review)"
        )
        script += """
func _cancel_native_review():
	if not is_instance_valid(dock) or FileAccess.file_exists("res://native-review-cancelled"):
		return
	if "独立只读验收。" in _text() and not dock.find_child("Stop", true, false).disabled:
		_file("native-review-cancelled")
		dock.find_child("Stop", true, false).pressed.emit()
"""
        if SCENARIO == "cancel-verify":
            script = script.replace(
                '"独立只读验收。" in _text()', 'FileAccess.file_exists("res://verify-transport-running")'
            )
        Path(target).write_text(script, encoding="utf8")
    if Path(source).name == "design_batch.gd" and SCENARIO in parent_delivery.SCENARIOS:
        Path(target).write_text(parent_delivery.scene(Path(target).read_text()), encoding="utf8")
    return result


batch.shutil.copyfile = fixture_copyfile

# Exercise a real read-only native reviewer through the HTTP transport. Its
# model supplies only a verdict and paths; identity/digests come from the host.
review_calls: list[dict[str, Any]] = []
repair_calls: list[dict[str, Any]] = []
failure_notices: list[str] = []
repair_returns: list[str] = []
integration_receipts: list[dict[str, Any]] = []
integration_runtime: dict[str, Any] = {}
parent_stages: list[str] = []


class AcceptanceServer(ThreadingHTTPServer):
    def __init__(self, address, handler):
        original = handler.do_POST
        original_get = handler.do_GET

        def get(instance):
            if SCENARIO == "parallel-integration" and integration_restarting and instance.path.endswith("/models"):
                data = batch.json.dumps({"data": [{"id": "design-batch-fixture"}]}).encode()
                instance.send_response(200)
                instance.send_header("Content-Type", "application/json")
                instance.send_header("Content-Length", str(len(data)))
                instance.end_headers()
                instance.wfile.write(data)
                return
            return original_get(instance)

        handler.do_GET = get

        def post(instance):
            raw = instance.rfile.read(int(instance.headers["Content-Length"]))
            body = batch.json.loads(raw)
            prompt = next((m.get("content", "") for m in reversed(body["messages"]) if m["role"] == "user"), "")
            if SCENARIO in parent_delivery.SCENARIOS:
                message = parent_delivery.model_response(batch, prompt, body)
                if message is not None:
                    data = batch.json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                    instance.send_response(200)
                    instance.send_header("Content-Type", "application/json")
                    instance.send_header("Content-Length", str(len(data)))
                    instance.end_headers()
                    instance.wfile.write(data)
                    return
            if SCENARIO in PARENT_SCENARIOS and isinstance(prompt, str) and "BOUND_PARENT_STAGE" in prompt:
                parent_stages.append(prompt)
                message = {"role": "assistant", "content": "BOUND_PARENT_STAGE_A_FINISHED"}
                if SCENARIO.startswith("parent-delivery-"):
                    results = [m["content"] for m in body["messages"] if m.get("tool_call_id") == "premature-delivery"]
                    if not results or SCENARIO == "parent-delivery-no-progress":
                        message = batch.tool_call(
                            "premature-delivery-" + str(len(parent_stages))
                            if SCENARIO == "parent-delivery-no-progress"
                            else "premature-delivery",
                            "complete_delivery",
                            {
                                "pr": 7,
                                "candidate": "a" * 40,
                                "signed_commit": "b" * 40,
                                "acceptance_items": [
                                    {
                                        "id": "producer-done",
                                        "module": "all",
                                        "acceptance": "Producer says done",
                                        "state": "done",
                                        "evidence": "self declaration",
                                    }
                                ],
                            },
                        )
                    else:
                        assert "independent acceptance is not ready" in str(results), results
                    if SCENARIO == "parent-delivery-no-progress" and len(parent_stages) > 3:
                        # Bound the failing fixture itself; a fourth request is
                        # evidence that the native no-progress stop was bypassed.
                        message = {"role": "assistant", "content": "UNEXPECTED_CONTINUE_AFTER_KUAFU"}
                data = batch.json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                instance.send_response(200)
                instance.send_header("Content-Type", "application/json")
                instance.send_header("Content-Length", str(len(data)))
                instance.end_headers()
                instance.wfile.write(data)
                return
            if isinstance(prompt, str) and (
                prompt.startswith("独立验收纠正：")
                or (
                    SCENARIO
                    in {
                        "unknown",
                        "stale",
                        "receipt-tamper",
                        "receipt-as-evidence",
                        "directory-failure",
                        "auxiliary-tamper",
                        "auxiliary-as-evidence",
                    }
                    and "current_host_design_batch" in prompt
                )
            ):
                if prompt.startswith("独立验收纠正："):
                    results = [
                        m["content"]
                        for m in body["messages"]
                        if m["role"] == "tool" and m.get("tool_call_id") == "repair-write"
                    ]
                    if not results:
                        message = batch.tool_call(
                            "repair-write",
                            "run_command",
                            {
                                "command": batch.python_command(
                                    "from pathlib import Path; Path('repair-evidence.txt').write_text('actual repaired execution'); print('ACTUAL_REPAIR_OK')"
                                )
                            },
                        )
                    else:
                        assert any("ACTUAL_REPAIR_OK" in str(r) for r in results)
                        message = {
                            "role": "assistant",
                            "content": "Corrected original production evidence; ready for independent review.",
                        }
                    repair_calls.append({"completed": bool(results)})
                else:
                    failure_notices.append(prompt)
                    message = {"role": "assistant", "content": "NATIVE_ACCEPTANCE_BLOCKED_NOTED"}
                data = batch.json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                instance.send_response(200)
                instance.send_header("Content-Type", "application/json")
                instance.send_header("Content-Length", str(len(data)))
                instance.end_headers()
                instance.wfile.write(data)
                return
            if SCENARIO == "parallel-integration" and prompt == "NATIVE_INTEGRATION_RECOVERY":
                results = {m.get("tool_call_id"): m.get("content", "") for m in body["messages"] if m["role"] == "tool"}
                if "integration-cold-list" not in results:
                    message = batch.tool_call(
                        "integration-cold-list", "integrate_production_result", {"action": "list"}
                    )
                else:
                    listed = batch.json.loads(results["integration-cold-list"])
                    producer = next(p for p in listed["producers"] if p["work_order"] == 3)
                    assert producer["live_independent_acceptance"] is False, producer
                    if "integration-cold-rollback" not in results:
                        assert (
                            parallel.folder / "original/samples/project/production-output.txt"
                        ).read_text() == "ACCEPTED_NATIVE_PROJECT_OUTPUT"
                        message = batch.tool_call(
                            "integration-cold-rollback",
                            "integrate_production_result",
                            {"action": "rollback", "producer_id": producer["producer_id"]},
                        )
                    else:
                        value = batch.json.loads(results["integration-cold-rollback"])
                        assert value.get("ok") is True and value["state"] == "rolled_back", value
                        assert not (parallel.folder / "original/samples/project/production-output.txt").exists()
                        assert not (parallel.folder / "original/samples/project/production-output.gd").exists()
                        integration_receipts.append(
                            dict(action="rollback", result=value, cold_restart=True, live_reviewer=False)
                        )
                        message = {"role": "assistant", "content": "NATIVE_INTEGRATION_RECOVERED"}
                data = batch.json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                instance.send_response(200)
                instance.send_header("Content-Type", "application/json")
                instance.send_header("Content-Length", str(len(data)))
                instance.end_headers()
                instance.wfile.write(data)
                return
            if SCENARIO.startswith("parallel") and prompt == "DESIGN_BATCH_START":
                parallel.setup(SCENARIO)
            if (
                (SCENARIO.startswith("parallel") or SCENARIO == "repair")
                and isinstance(prompt, str)
                and "current_host_design_batch" in prompt
            ):
                if SCENARIO.startswith("parallel"):
                    if SCENARIO != "parallel-integration" or prompt not in parallel.returns:
                        parallel.returns.append(prompt)
                else:
                    assert "acceptance_findings" in prompt and "Missing repair-evidence.txt execution proof" in prompt
                    repair_returns.append(prompt)
                message = {"role": "assistant", "content": "DESIGN_BATCH_PARENT_VERIFIED_OK"}
                if SCENARIO == "parallel-integration":
                    results = {
                        m.get("tool_call_id"): m.get("content", "") for m in body["messages"] if m["role"] == "tool"
                    }

                    def native_result(action):
                        value = batch.json.loads(results["integration-" + action])
                        assert value.get("ok") is True, value
                        if not any(item["action"] == action for item in integration_receipts):
                            integration_receipts.append(dict(action=action, result=value))
                        return value

                    if "integration-list" not in results:
                        message = batch.tool_call("integration-list", "integrate_production_result", {"action": "list"})
                    else:
                        listed = native_result("list")
                        producer = next(
                            p["producer_id"]
                            for p in listed["producers"]
                            if p["work_order"] == 3 and p["live_independent_acceptance"]
                        )
                        for action, expected in (("plan", "planned"), ("apply", "applied")):
                            if "integration-" + action not in results:
                                message = batch.tool_call(
                                    "integration-" + action,
                                    "integrate_production_result",
                                    {"action": action, "producer_id": producer},
                                )
                                break
                            value = native_result(action)
                            assert value["state"] == expected, value
                            if action == "plan":
                                assert value["changed_files"] == ["production-output.gd", "production-output.txt"], (
                                    value
                                )
                        else:
                            if "integration-run" not in results:
                                game_command = [
                                    integration_binary,
                                    "--headless",
                                    "--path",
                                    str(parallel.folder / "original/samples/project"),
                                    "--script",
                                    "res://production-output.gd",
                                ]
                                code = (
                                    "import subprocess; p=subprocess.run("
                                    + repr(game_command)
                                    + ",capture_output=True,text=True,timeout=30); print(p.stdout); print(p.stderr); raise SystemExit(p.returncode)"
                                )
                                message = batch.tool_call(
                                    "integration-run", "run_command", {"command": batch.python_command(code)}
                                )
                            else:
                                actual = batch.json.loads(results["integration-run"])
                                assert (
                                    actual["exit_code"] == 0
                                    and "NATIVE_INTEGRATION_EXECUTED:ACCEPTED_NATIVE_PROJECT_OUTPUT"
                                    in batch.json.dumps(actual)
                                ), actual
                                integration_runtime.update(actual)
                data = batch.json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
                instance.send_response(200)
                instance.send_header("Content-Type", "application/json")
                instance.send_header("Content-Length", str(len(data)))
                instance.end_headers()
                instance.wfile.write(data)
                return
            if not isinstance(prompt, str) or not prompt.startswith("独立只读验收。"):
                instance.rfile = io.BytesIO(raw)
                return original(instance)
            system = "\n".join(m.get("content", "") for m in body["messages"] if m["role"] == "system")
            assert "read_only_reviewer" in system
            assert not {"write_file", "run_command"} & {t["function"]["name"] for t in body.get("tools", [])}
            roots = re.findall(r"Authoritative source to review: ([^\n]+)", system)
            assert roots, system
            root = Path(roots[-1])
            criteria = batch.json.loads(prompt.split("\n")[1])
            producer_receipt = batch.json.loads(prompt.split("\n")[2])
            auxiliary = root.parent / "native-review-auxiliary.txt"
            results = [m["content"] for m in body["messages"] if m["role"] == "tool"]
            repair_evidence = criteria[0]["id"] == "A" and (
                (SCENARIO == "repair" and any(r["completed"] for r in repair_calls))
                or (
                    SCENARIO in {"parallel-repair", "parallel-evidence-completion", "parallel-evidence-exhausted"}
                    and (root / "repair-evidence.txt").exists()
                )
            )
            if not results:
                if not auxiliary.exists():
                    auxiliary.write_text("Untrusted external context, not criterion evidence", encoding="utf8")
                message = batch.tool_call("acceptance-read", "read_file", {"path": str(root / "fixture-input.txt")})
                if getattr(batch, "COMPLETE_GAME", False):
                    message["tool_calls"].append(
                        batch.tool_call(
                            "acceptance-game", "read_file", {"path": str(root / "samples/project/production-output.gd")}
                        )["tool_calls"][0]
                    )
                message["tool_calls"].append(
                    batch.tool_call("acceptance-auxiliary-context", "read_file", {"path": str(auxiliary)})[
                        "tool_calls"
                    ][0]
                )
                message["tool_calls"].append(
                    batch.tool_call(
                        "acceptance-directory",
                        "list_directory",
                        {"path": str(root / "missing-directory" if SCENARIO == "directory-failure" else root)},
                    )["tool_calls"][0]
                )
                message["tool_calls"].append(
                    batch.tool_call("acceptance-producer-context", "read_file", {"path": producer_receipt["path"]})[
                        "tool_calls"
                    ][0]
                )
                if SCENARIO.startswith("parallel"):
                    terminal = batch.json.loads(Path(producer_receipt["path"]).read_text(encoding="utf8"))
                    transcript = (
                        producer_receipt["path"].removesuffix(f".{terminal['execution_id']}.terminal.json") + ".log"
                    )
                    message["tool_calls"].append(
                        batch.tool_call("acceptance-transcript-context", "read_file", {"path": transcript})[
                            "tool_calls"
                        ][0]
                    )
                    if criteria[0]["id"] == "C":
                        for name in "AB":
                            message["tool_calls"].append(
                                batch.tool_call(
                                    "acceptance-upstream-" + name,
                                    "read_file",
                                    {"path": str(parallel.folder / ("external-" + name) / "fixture-input.txt")},
                                )["tool_calls"][0]
                            )
                    message["tool_calls"].append(
                        batch.tool_call(
                            "acceptance-registration-context", "read_file", {"path": terminal["registration"]["path"]}
                        )["tool_calls"][0]
                    )
                if repair_evidence:
                    message["tool_calls"].append(
                        batch.tool_call("repair-proof-read", "read_file", {"path": str(root / "repair-evidence.txt")})[
                            "tool_calls"
                        ][0]
                    )
            else:
                assert any("UNTRUSTED_FIXTURE_FILE" in str(r) for r in results)
                if repair_evidence:
                    assert any("actual repaired execution" in str(r) for r in results)
                if SCENARIO == "parallel-config-drift":
                    config = parallel.folder / "parallel-config.json"
                    config.write_text(config.read_text(encoding="utf8") + " ", encoding="utf8")
                if SCENARIO == "stale":
                    (root / "fixture-input.txt").write_text("changed after actual reviewer read", encoding="utf8")
                if SCENARIO == "receipt-tamper":
                    receipt_file = Path(producer_receipt["path"])
                    receipt_file.write_bytes(receipt_file.read_bytes() + b" ")
                if SCENARIO == "auxiliary-tamper":
                    auxiliary.write_text("changed after successful contextual read", encoding="utf8")
                failing = criteria[0]["id"] == "A" and (
                    (SCENARIO == "repair" and not any(r["completed"] for r in repair_calls))
                    or (
                        SCENARIO in {"parallel-repair", "parallel-evidence-completion"}
                        and not (root / "repair-evidence.txt").exists()
                    )
                    or SCENARIO == "parallel-evidence-exhausted"
                )
                verdict = {
                    "verdict": "unknown" if SCENARIO == "unknown" else "fail" if failing else "pass",
                    "reason": "Missing repair-evidence.txt execution proof"
                    if failing
                    else "Successful host read of fixture evidence",
                    "criteria": [
                        {
                            "id": c["id"],
                            "met": not failing,
                            "evidence": [producer_receipt["path"]]
                            if SCENARIO == "receipt-as-evidence"
                            else [str(auxiliary)]
                            if SCENARIO == "auxiliary-as-evidence"
                            else ["fixture-input.txt"]
                            + (
                                ["samples/project/production-output.gd"]
                                if getattr(batch, "COMPLETE_GAME", False)
                                else []
                            )
                            + (["repair-evidence.txt"] if repair_evidence else []),
                        }
                        for c in criteria
                    ],
                }
                if SCENARIO in {"parallel-evidence-completion", "parallel-evidence-exhausted"} and failing:
                    verdict["verdict"] = "unknown"
                    verdict["unknown_kind"] = "missing_execution_evidence"
                    for criterion in verdict["criteria"]:
                        criterion["met"] = None
                        criterion["missing_evidence"] = "Run assigned verification and persist repair-evidence.txt"
                message = {"role": "assistant", "content": batch.json.dumps(verdict)}
            review_calls.append({"root": str(root), "criteria": criteria, "completed": bool(results)})
            data = batch.json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]}).encode()
            instance.send_response(200)
            instance.send_header("Content-Type", "application/json")
            instance.send_header("Content-Length", str(len(data)))
            instance.end_headers()
            instance.wfile.write(data)

        handler.do_POST = post
        super().__init__(address, handler)


batch.ThreadingHTTPServer = AcceptanceServer
# Preserve private fixture failures before its isolated directory is removed.


class DiagnosticDirectory(TemporaryDirectory[str]):
    def __exit__(self, *args):
        root = Path(self.name)
        if root.name.startswith("native-design-batch-"):
            diagnostics = []
            if SCENARIO.startswith("parallel"):
                diagnostics.extend(parallel.diagnostics())
            for candidate in root.glob("godot-candidate-*"):
                for file in candidate.glob(".gonggong-outbox/intake-failures/*.json"):
                    diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
            for file in (root / "isolated-editor/editor_data/cache").glob("gonggong-acceptance*.result"):
                diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
            for file in (root / "isolated-editor/editor_data/cache").glob("gonggong-parent*.result"):
                diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
            for file in (root / "isolated-editor/editor_data/cache/gonggong-dependency-evidence").rglob("*.json"):
                diagnostics.append({
                    "path": str(file.relative_to(root)),
                    "sha256": batch.hashlib.sha256(file.read_bytes()).hexdigest(),
                    "body": file.read_text(encoding="utf8"),
                })
            for file in (root / "isolated-editor/editor_data/cache").glob("gonggong-project-integration*.result"):
                diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
            for file in (root / "original/samples/project/.godot/editor/ai_chat_snapshots").glob("*acceptance.json"):
                diagnostics.append({
                    "path": str(file.relative_to(root)),
                    "sha256": batch.hashlib.sha256(file.read_bytes()).hexdigest(),
                    "body": file.read_text(encoding="utf8"),
                })
            for file in (root / "original/samples/project/.godot/editor/ai_chat_snapshots").glob(
                "*.tool-receipts.json"
            ):
                diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
            if (root / "original/samples/project/native-review-cancelled").exists():
                diagnostics.append({"path": "cancelled", "body": "actual Stop signal"})
            for file in root.glob("parent-model-fixture.receipt.json"):
                diagnostics.append({"path": "parent-cli-receipt", "body": file.read_text(encoding="utf8")})
            if (root / "original/samples/project/native-parent-cancelled").exists():
                diagnostics.append({"path": "parent-cancelled", "body": "actual native permission/Stop boundary"})
            if (root / "original/samples/project/native-parent-no-progress").exists():
                diagnostics.append({"path": "parent-no-progress", "body": "actual held native control boundary"})
            if SCENARIO == "parent-delivery-no-progress":
                for file in (root / "original/.git/gonggong-kuafu").glob("*/detected.json"):
                    diagnostics.append({
                        "path": "kuafu-detected/" + file.parent.name,
                        "body": file.read_text(encoding="utf8"),
                    })
            for file in (root / "isolated-editor/editor_data/cache").glob("delivery-finalize*.original.json"):
                diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
            if SCENARIO in parent_delivery.SCENARIOS:
                for file in (root / "isolated-editor/editor_data/cache").glob("delivery-finalize*.retained.json"):
                    diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
                diagnostics.append({
                    "path": "native-finalization",
                    "body": batch.json.dumps(parent_delivery.collect(root)),
                })
                for file in (root / "original/.git/gonggong-delivery-finalization").rglob("*.json"):
                    diagnostics.append({"path": str(file.relative_to(root)), "body": file.read_text(encoding="utf8")})
                if (root / "original/samples/project/native-finalize-observed").exists():
                    diagnostics.append({"path": "native-finalize-observed", "body": "actual native delivery terminal"})
            history = root / "original/samples/project/.godot/editor/ai_chat_history.json"
            if history.exists():
                diagnostics.append({"path": "history", "body": history.read_text(encoding="utf8")})
            out = Path(sys.argv[sys.argv.index("--out") + 1]).with_suffix(".diagnostics-report.json")
            out.write_text(batch.json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf8")
        return super().__exit__(*args)


batch.tempfile.TemporaryDirectory = DiagnosticDirectory
if __name__ == "__main__":
    batch.main()
    output = Path(sys.argv[sys.argv.index("--out") + 1])
    result = batch.json.loads(output.read_text(encoding="utf8"))
    diagnostics = batch.json.loads(output.with_suffix(".diagnostics-report.json").read_text(encoding="utf8"))
    history_entry = next((item for item in diagnostics if item["path"] == "history"), None)
    if history_entry is None:
        # A native parse/startup failure may happen before history exists.
        # Preserve its real report instead of masking it with StopIteration.
        result.update(
            ok=False, transport_fixture_ok=result["ok"], verification_status="failed", native_scenario=SCENARIO
        )
        result["diagnostic_failure"] = (
            "Native fixture ended before creating history; inspect original errors/stdout/stderr"
        )
        output.write_text(batch.json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
        raise SystemExit(1)
    history = batch.json.loads(history_entry["body"])
    producers = [a for a in history["agents"] if a.get("sub_agent", {}).get("source") == "design"]
    accepted = [a for a in producers if a["sub_agent"].get("acceptance")]
    decisions = []
    for producer in accepted:
        acceptance = producer["sub_agent"]["acceptance"]
        stored = next(item for item in diagnostics if item["path"].endswith(Path(acceptance["evidence"]).name))
        assert stored["sha256"] == acceptance["decision_file_sha256"]
        envelope = batch.json.loads(stored["body"])
        assert (
            batch.hashlib.sha256(envelope["payload"].encode()).hexdigest()
            == envelope["sha256"]
            == acceptance["decision_sha256"]
        )
        decision = batch.json.loads(envelope["payload"])
        reviewer_receipt = next(
            item for item in diagnostics if item["path"].endswith(Path(decision["reviewer"]["receipt"]["path"]).name)
        )
        reviewer_payload = batch.json.loads(batch.json.loads(reviewer_receipt["body"])["payload"])
        assert (
            not reviewer_payload.get("review_source_unverified")
            and reviewer_payload.get("unknown_receipt_count", 0) == 0
        )
        assert any(r["tool"] == "list_directory" and r["ok"] is True for r in reviewer_payload["receipts"])
        assert any(
            r.get("host_context_kind") == "producer_terminal" and not r.get("candidate_relative_path")
            for r in reviewer_payload["receipts"]
        )
        assert reviewer_payload["review_auxiliary_manifest"]
        assert any(
            r.get("host_context_kind") == "untrusted_auxiliary"
            and r.get("untrusted") is True
            and not r.get("candidate_relative_path")
            for r in reviewer_payload["receipts"]
        )
        assert decision["producer"]["worker_id"] != decision["reviewer"]["worker_id"]
        assert (
            decision["producer"].get("execution_id", decision["producer"].get("conversation_id"))
            != decision["reviewer"]["conversation_id"]
        )
        assert decision["verdict"] == "pass" and decision["criteria"]
        assert acceptance["operator"] == "fixture-operator" and isinstance(acceptance["reviewer"], str)
        decisions.append({
            "producer": producer["id"],
            "decision_sha256": acceptance["decision_sha256"],
            "criteria": [c["id"] for c in decision["criteria"]],
        })
    stages = result["stage_requests"]
    if SCENARIO.startswith("parallel"):
        events = [
            batch.json.loads(line)
            for item in diagnostics
            if item["path"] == "worker-events"
            for line in item["body"].splitlines()
        ]
        starts = {name: [e for e in events if e["name"] == name and e["phase"] == "start"] for name in "ABC"}
        finishes = {name: [e for e in events if e["name"] == name and e["phase"] == "finish"] for name in "ABC"}
        ledgers = [
            batch.json.loads(item["body"]) for item in diagnostics if item["path"].endswith(".yuanheng/state.json")
        ]
        valid = (
            not result["errors"]
            and result["editor"]["ok"]
            and len(accepted) == 3
            and len(parallel.returns) == 1
            and len(ledgers) == 3
            and all(s["tasks"][0]["status"] == "done" for s in ledgers)
        )
        if SCENARIO == "parallel":
            registrations = [
                batch.json.loads(item["body"]) for item in diagnostics if item["path"].endswith(".registration.json")
            ]
            downstream = [item for item in registrations if item.get("order") == 3]
            checks = {
                item["sha256"]: batch.json.loads(item["body"])
                for item in diagnostics
                if "gonggong-dependency-evidence" in item["path"] and "sha256" in item
            }
            assert len(downstream) == 1, "Actual downstream registration required"
            request_ref = downstream[0]["dispatch_request"]
            requests = [
                batch.json.loads(item["body"])
                for item in diagnostics
                if batch.hashlib.sha256(item["body"].encode()).hexdigest() == request_ref["sha256"]
            ]
            assert len(requests) == 1, "Registration must reference actual durable dispatch bytes"
            sources = downstream[0]["dependency_preflight"]
            assert (
                next(worker for worker in requests[0]["workers"] if worker["order"] == 3)["dependency_preflight"]
                == sources
            )
            assert len(sources) == 2, "Both actual upstream checks must survive registration"
            for source in sources:
                ref = source["candidate_check"]
                record = checks[ref["sha256"]]
                request = batch.json.loads(record["request_json"])
                response = batch.json.loads(record["response_json"])
                assert request["request_nonce"] == response["request_nonce"] == ref["request_nonce"]
                assert response["ok"] is True
                assert request["candidate"] == source["verified_response"]["current_candidate"]
                assert response["candidate_sha256"] == request["candidate"]["files_sha256"]
                assert source["decision"]["verdict"] == "pass"
        counts = {
            "A": 2
            if SCENARIO in {"parallel-repair", "parallel-evidence-completion", "parallel-evidence-exhausted"}
            else 1,
            "B": 1,
            "C": 1,
        }
        valid = valid and all(len(starts[n]) == len(finishes[n]) == counts[n] for n in "ABC")
        if valid:
            valid = max(starts[n][0]["time"] for n in "AB") < min(finishes[n][0]["time"] for n in "AB") and starts["C"][
                0
            ]["time"] > max(finishes[n][-1]["time"] for n in "AB")
        if SCENARIO == "parallel-evidence-completion":
            originals = [
                batch.json.loads(d["body"]) for d in diagnostics if d["path"].endswith(".unknown-acceptance.json")
            ]
            continuations = [
                batch.json.loads(d["body"])
                for d in diagnostics
                if "parallel-ticket-" in d["path"] and "-repair-" in d["path"]
            ]
            valid = valid and len(originals) == 1 and len(continuations) == 1
            if valid:
                original, continuation = originals[0], continuations[0]
                valid = (
                    original["verdict"] == "unknown"
                    and original["unknown_kind"] == "missing_execution_evidence"
                    and original["criteria"][0]["met"] is None
                )
                valid = (
                    valid
                    and continuation["repair_of"]["mode"] == "missing_execution_evidence"
                    and continuation["execution_id"] != original["producer"]["execution_id"]
                )
                valid = (
                    valid and len([r for r in review_calls if r["completed"] and r["criteria"][0]["id"] == "A"]) == 2
                )
        if SCENARIO == "parallel-evidence-exhausted":
            valid = (
                not result["errors"]
                and len(parallel.returns) == 1
                and len(starts["A"]) == len(finishes["A"]) == 2
                and len(starts["B"]) == len(finishes["B"]) == 1
                and not starts["C"]
                and len(accepted) == 1
                and len([r for r in review_calls if r["completed"] and r["criteria"][0]["id"] == "A"]) == 2
            )
        if SCENARIO == "parallel-config-drift":
            valid = (
                not result["errors"]
                and not accepted
                and len(parallel.returns) == 1
                and not starts["C"]
                and len(ledgers) == 3
                and all(s["tasks"][0]["status"] == "running" for s in ledgers)
            )
        if SCENARIO == "parallel-self-review":
            valid = (
                not result["errors"]
                and not starts["C"]
                and not any(d["producer"] == 1 for d in decisions)
                and any(s["tasks"][0]["owner"] == "4" and s["tasks"][0]["status"] == "running" for s in ledgers)
            )
        if SCENARIO == "parallel-preflight-failure":
            valid = (
                not result["errors"]
                and result["editor"]["ok"]
                and len(accepted) >= 1
                and not starts["C"]
                and starts["A"]
                and starts["B"]
                and not any(
                    item["path"].endswith(".registration.json") and batch.json.loads(item["body"]).get("order") == 3
                    for item in diagnostics
                )
                and not any("gonggong-dependency-evidence" in item["path"] for item in diagnostics)
            )
        result["external_events"] = events
        result["external_parent_returns"] = len(parallel.returns)
    elif SCENARIO in {"pass", "repair"} | PARENT_SCENARIOS:
        valid = (
            not result["errors"]
            and result["editor"]["ok"]
            and stages.get("child1") == 3
            and stages.get("child2") == 3
            and result["parent_return_count"] == 1
            and len(accepted) == 2
            and len([r for r in review_calls if r["completed"]]) == 2
        )
        if SCENARIO == "pass":
            started = [batch.json.loads(item["body"]) for item in diagnostics if item["path"].endswith(".started.json")]
            assert len(started) == 1 and started[0]["conversation_id"] and started[0]["generation"] >= 0
            assert any(item.get("sha256") == started[0]["dispatch"]["sha256"] for item in diagnostics)
        if SCENARIO == "repair":
            valid = (
                not result["errors"]
                and result["editor"]["ok"]
                and stages.get("child1") == 3
                and stages.get("child2") == 3
                and len(repair_returns) == 1
                and len(accepted) == 2
                and len([r for r in review_calls if r["completed"]]) == 3
                and len([r for r in repair_calls if r["completed"]]) == 1
            )
    else:
        valid = not result["errors"] and stages.get("child1") == 3 and stages.get("child2", 0) == 0 and not accepted
        if SCENARIO in {
            "unknown",
            "stale",
            "receipt-tamper",
            "receipt-as-evidence",
            "directory-failure",
            "auxiliary-tamper",
            "auxiliary-as-evidence",
        }:
            valid = valid and len([r for r in review_calls if r["completed"]]) == 1
        elif SCENARIO in {"cancel", "cancel-verify"}:
            valid = valid and any(item["path"] == "cancelled" for item in diagnostics)
        else:
            valid = valid and not review_calls
    if SCENARIO == "parallel-integration":
        valid = (
            valid
            and integration_restore_report.get("ok") is True
            and integration_runtime.get("exit_code") == 0
            and [item["action"] for item in integration_receipts] == ["list", "plan", "apply", "rollback"]
        )
        result["integration_receipts"] = integration_receipts
        result["integration_restore"] = integration_restore_report
        result["integration_runtime"] = integration_runtime
    if SCENARIO in PARENT_SCENARIOS:
        cli = [item for item in diagnostics if item["path"] == "parent-cli-receipt"]
        expected_stages = 2 if SCENARIO == "parent-delivery-bypass" else 0 if SCENARIO == "parent-cli" else 1
        if SCENARIO in parent_delivery.SCENARIOS:
            receipt = next(batch.json.loads(x["body"]) for x in diagnostics if x["path"] == "native-finalization")
            original_requests = [
                batch.json.loads(x["body"])
                for x in diagnostics
                if x["path"].endswith(".original.json") and "delivery-finalize" in x["path"]
            ]
            valid = (
                not result["errors"]
                and result["editor"].get("ok")
                and len(accepted) == 2
                and len(original_requests) == 1
                and {c["id"] for c in original_requests[0]["acceptance_items"]} == {"original-A", "original-B"}
                and len(original_requests[0]["parent_completion_guard"]["live_decisions"]) == 2
                and any(x["path"] == "native-finalize-observed" for x in diagnostics)
                and receipt.get("before_release", {}).get("started") is True
                and not receipt.get("child_running_after_native_terminal", True)
                and not receipt.get("late_mutations", True)
            )
            if SCENARIO == "parent-finalize":
                valid = (
                    valid
                    and receipt["before_release"]["issue"]["state"] == "CLOSED"
                    and result["editor"].get("parent_business_accepted") is True
                )
            else:
                valid = (
                    valid
                    and receipt["before_release"]["writes"] == []
                    and not result["editor"].get("parent_business_accepted")
                )
            result["native_finalization"] = receipt
            if SCENARIO == "parent-finalize-timeout":
                result["native_timeout_observed"] = parent_delivery.timeout_observed(diagnostics)
                valid = valid and result["native_timeout_observed"]
        elif SCENARIO == "parent-delivery-no-progress":
            expected_stages = 3
            blockers = [
                batch.json.loads(x["body"])["blocker_receipt"]
                for x in diagnostics
                if "gonggong-parent-" in x["path"]
                and x["path"].endswith(".result")
                and "blocker_receipt" in batch.json.loads(x["body"])
            ]
            detected = [batch.json.loads(x["body"]) for x in diagnostics if x["path"].startswith("kuafu-detected/")]
            valid = (
                not result["errors"]
                and result["editor"].get("ok")
                and result["editor"].get("parent_completion_state") == "kuafu_required"
                and not result["editor"].get("parent_business_accepted")
                and stages.get("child1", 0) == stages.get("child2", 0) == 0
                and any(x["path"] == "parent-no-progress" for x in diagnostics)
                and len(blockers) == len(detected) == 1
                and batch.json.loads(blockers[0]["output"]).get("dispatch") == "local_only"
                and detected[0]["issue"] == 441
                and detected[0]["action"] == "dispatch"
            )
            result["bounded_stop_receipts"] = {"blockers": blockers, "detected": detected}
        elif SCENARIO in PARENT_STOP_SCENARIOS:
            valid = (
                not result["errors"]
                and result["editor"].get("ok")
                and not result["editor"].get("parent_business_accepted")
                and stages.get("child1", 0) == stages.get("child2", 0) == 0
                and any(x["path"] == "parent-cancelled" for x in diagnostics)
            )
        else:
            valid = (
                valid
                and result["ok"]
                and result["recorded_event_files"] > 0
                and result["editor"].get("parent_completion_state") == "complete"
                and result["editor"].get("parent_business_accepted") is True
            )
        valid = valid and len(parent_stages) == expected_stages
        if SCENARIO == "parent-cli":
            valid = valid and len(cli) == 1 and batch.json.loads(cli[0]["body"])["request_seen"] is True
        if SCENARIO == "parent-cold":
            valid = (
                valid
                and parent_cold_report.get("ok")
                and parent_cold_report.get("new_parent_stages") == 0
                and parent_cold_report.get("exit_code") == 0
            )
            result["parent_cold_report"] = parent_cold_report
        result["parent_stage_count"] = len(parent_stages)
        result["parent_cli_receipts"] = cli
        result["scope"] = (
            "Actual native mapped completion and installed finalizer/journal; controlled account, signed/main/CI and Issue mutation ports, no real remote writes"
            if SCENARIO in parent_delivery.SCENARIOS
            else "Controlled original complete fixture scope: actual command/read delivery, not GitHub merge or provider effectiveness"
        )
    result["transport_fixture_ok"] = result["ok"]
    result["ok"] = bool(valid)
    result["verification_status"] = "native_acceptance_passed" if valid else "failed"
    result["native_scenario"] = SCENARIO
    result["verified_decisions"] = decisions
    result["review_calls"] = review_calls
    result["repair_calls"] = repair_calls
    result["failure_notice_count"] = len(failure_notices)
    output.write_text(batch.json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(batch.json.dumps({"native_acceptance": result["ok"], "scenario": SCENARIO, "decisions": decisions}))
    raise SystemExit(0 if valid else 1)
