"""Verify two independent signed stages and one unsigned sibling with the native editor and Sinan."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_confirmed_native_stage import COMPONENT, StageHost, fixture
from run_workbench_offline_document import serve
from run_workbench_task_confirmations import copy_editor, create_app, run_editor

ROOT = Path(__file__).resolve().parents[2]
# One independently executable prototype and one one-second animated bridge deck.
PROGRAM = """def pull(raised):
    return not raised


if __name__ == "__main__":
    print("raised" if pull(False) else "lowered")
"""
PREVIEW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="8" y="30" width="48" height="4" fill="steelblue">
    <animateTransform attributeName="transform" type="rotate" values="-90 8 32;0 8 32" dur="1s" fill="freeze"/>
  </rect>
</svg>
"""
TASKS = [
    ("程序", "可运行原型", "拉杆切换桥面一次，再拉一次复位", "a", "bridge.py"),
    ("动画", "动画预览", "24 帧/秒，第 24 帧桥面水平展开并保持", "b", "bridge.svg"),
    ("音效", "音效草稿", "开桥时响铃", "c", "bell.wav"),
]
CHECK = """import os, runpy
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path(os.environ["DUOBAO_INPUT"])
if (root / "a").is_dir():
    pull = runpy.run_path(str(root / "a/bridge.py"))["pull"]
    assert pull(False) is True and pull(pull(False)) is False
else:
    svg = ET.parse(root / "b/bridge.svg").getroot()
    ns = "{http://www.w3.org/2000/svg}"
    assert svg.tag == ns + "svg"
    deck, = svg.findall(ns + "rect")
    assert float(deck.get("width")) > float(deck.get("height")) > 0
    motion, = deck.findall(ns + "animateTransform")
    assert motion.get("attributeName") == "transform" and motion.get("type") == "rotate"
    assert motion.get("values").split(";") == ["-90 8 32", "0 8 32"]
    assert motion.get("dur") == "1s" and motion.get("fill") == "freeze"
"""


def install_plans(workflow, actor, issues, initial, folder):
    launches = folder / "starts.jsonl"
    producer = folder / "bridge_worker.py"
    producer.write_text(
        "import json, os\nfrom pathlib import Path\n"
        "context = Path(os.environ['NATIVE_CONTEXT'])\n"
        "grant = json.loads(context.read_text(encoding='utf-8'))['stage_authorization']\n"
        "with open(os.environ['STARTS'], 'a', encoding='utf-8') as log:\n"
        "    print(json.dumps(dict(execution=context.parent.name, pid=os.getpid(), grant=grant)), file=log)\n"
        f"outputs = {{{TASKS[0][1]!r}: ('a/bridge.py', {PROGRAM!r}), {TASKS[1][1]!r}: ('b/bridge.svg', {PREVIEW!r})}}\n"
        "path, content = outputs[grant['stage']]\n"
        "Path(path).write_bytes(content.encode('utf-8'))\n",
        encoding="utf-8",
    )
    profile = workflow.worker.profiles["local"]
    profile["argv"] = [profile["argv"][0], str(producer)]
    profile["env"]["STARTS"] = str(launches)
    registry = workflow.runner._registry["check"]
    registry["argv"] = [registry["argv"][0], "-I", "-c", CHECK]
    plans = {}
    for issue, (_, stage, criteria, module, filename) in zip(issues, TASKS, strict=True):
        plans[issue["id"]] = dict(
            selected={module: initial[module]},
            writes={module: [filename]},
            dependencies={},
            profile="local",
            product="bridge",
            checks=["check"],
            mandate="installed-k03",
            stage=stage,
            stage_criteria=criteria,
        )

    def installed(operator, issue):
        assert operator == actor
        return plans[issue]

    workflow.installed_plan = installed
    return launches


def dispatch(url, token):
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    env.update(NATIVE_SERVICE_URL=url, NATIVE_SERVICE_TOKEN=token)
    completed = subprocess.run(
        [shutil.which("node"), COMPONENT / "sinan-workorders/native_dispatch.mjs"],
        env=env,
        capture_output=True,
        check=True,
        timeout=60,
    )
    batch = json.loads(completed.stdout)
    assert not batch["errors"] and not batch["deliveries"], batch
    return batch


def read_result(host, issue, spec, key, dispatch_receipt, stop, launch, closure):
    workflow = host.workflow
    _, stage, criteria, module, filename = spec
    row = host.api("status", key=key).raise_for_status().json()
    task = json.loads(row["task"])
    local = workflow.worker.reconcile(task, key)
    assert local == json.loads(row["terminal"]) and local["state"] == "produced"
    detail = host.detail(issue)
    progress = detail["execution_progress"]
    assert progress == row["progress"] and progress["id"] == key
    assert row["stage_result"] == stop and stop["state"] == row["state"] == progress["state"] == "stage-reached"
    assert row["acceptance"] is None and stop["reason"] == "authorized_stage_criteria_met"
    assert local["candidate"] == stop["candidate"] == progress["candidate"]
    assert local["modules"] == stop["modules"] == progress["events"][-1]["details"]["modules"]
    assert dispatch_receipt["workerId"] == dispatch_receipt["reference"] == stop["task"] == key
    assert dispatch_receipt["worker_ref"] == local["origin"]["worker_ref"] == progress["worker_ref"]
    grant = launch["grant"]
    assert launch["pid"] > 0 and launch["execution"] == key
    assert grant == stop["authorization"] == task["source"]["definition"]["stage_authorization"]
    assert (grant["document_id"], grant["issue_id"], grant["stage"], grant["criteria"]) == (
        host.doc,
        issue["id"],
        stage,
        criteria,
    )
    signed = detail["task_confirmation"]
    assert signed["status"] == "confirmed" and grant["confirmed_by"] == signed["confirmed_by"] == host.actor
    assert grant["confirmation_revision"] == signed["revision"]
    assert all(grant[field] == signed[field] for field in ("version", "target_revision", "issue_revision"))
    assert progress["stage"] == stage and local["exit_code"] == closure["exit_code"] == 0 and not closure["reasons"]
    check = workflow.runner.status(task["tenant"], host.actor, key + "-check")
    assert check["outcome"] == "passed" and check["exit_code"] == 0 and check["candidate"] == local["candidate"]
    assert stop["checks"]["check"] == dict(evidence=check["evidence"], outcome=check["outcome"])
    edits = local["intake"]["inputs"][module]["edits"]
    assert set(edits) == {filename}
    content = workflow.worker.store.read(task["tenant"], module, local["modules"][module], filename)
    assert content == (PROGRAM if module == "a" else PREVIEW).encode()
    return dict(
        issue_id=issue["id"],
        number=issue["number"],
        execution=key,
        dispatch=dispatch_receipt,
        physical_starts=1,
        pid=launch["pid"],
        closure=closure,
        local=dict(
            state=local["state"],
            candidate=local["candidate"],
            modules=local["modules"],
            worker_ref=local["origin"]["worker_ref"],
        ),
        stage_stop=stop,
        issue_progress=progress,
        check_exit=check["exit_code"],
        artifact=dict(
            path=module + "/" + filename,
            revision=local["modules"][module],
            bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content=content.decode(),
        ),
    )


def exercise(folder, binary):
    editor = copy_editor(binary, folder / "editor")
    with contextmanager(fixture.__wrapped__)(folder) as (workflow, actor, tenant, _, initial, _), ExitStack() as stack:
        host = StageHost()
        host.workflow, host.actor = workflow, actor
        domain = workflow.domain
        host.doc = domain.create_doc(actor, "开桥机关", "\n\n".join(row[2] for row in TASKS))["id"]
        domain.design_signoff(actor, host.doc, 1, "开桥程序、展开动画与提示音")
        issues = domain.split_design(
            actor,
            host.doc,
            1,
            "studio",
            [
                dict(paragraph=i, title=title, module_id="default", acceptance=criteria)
                for i, (title, _, criteria, _, _) in enumerate(TASKS, 1)
            ],
            "k03-bridge",
        )
        journal = install_plans(workflow, actor, issues, initial, folder)
        token = domain.issue_session(actor)
        stack.enter_context(
            patch.dict(
                os.environ,
                TIANXUAN_AUTH_MODE="accounts",
                TIANXUAN_TENANT_ID=tenant,
                TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
            )
        )
        app = create_app(domain, native_store=workflow.worker.store, native_workflow=workflow)
        operations = Counter()

        @app.middleware("http")
        async def count_calls(request, call_next):
            if request.url.path.startswith("/api/v1/native/workflow/"):
                operations[request.url.path.rsplit("/", 1)[1]] += 1
            return await call_next(request)

        with (
            serve(app, 0) as port,
            httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                headers={"Authorization": "Bearer " + token},
                trust_env=False,
            ) as host.client,
        ):
            url = str(host.client.base_url)
            for issue, (_, stage, criteria, _, _) in zip(issues, TASKS, strict=True):
                host.target(issue, stage, criteria)
                assert host.api("authorize", issue=issue["id"]).status_code == 409
            assert not journal.exists()
            confirmations = []
            for index, issue in enumerate(issues[:2]):
                ui = run_editor(
                    folder, editor, url, token, "studio", issue["number"], "confirm", focus_only=True, task_count=3
                )
                assert ui["selected"] == [f"#{issue['number']} {TASKS[index][0]}"]
                siblings = [host.detail(item)["task_confirmation"] for item in issues]
                assert [s["status"] for s in siblings] == ["confirmed"] * (index + 1) + ["pending"] * (2 - index)
                confirmation = siblings[index]
                assert confirmation["confirmed_by"] == actor
                confirmations.append(dict(selected=ui["selected"], feedback=ui["feedback"], confirmation=confirmation))
            # Keep both tickets ready for the Node dispatch measured below.
            # An intervening native editor reopen would consume the first one.
            keys = [host.api("authorize", issue=issue["id"]).raise_for_status().json() for issue in issues[:2]]
            assert len(set(keys)) == 2
            operations.clear()
            first = dispatch(url, token)
            first_calls = dict(operations)
            operations.clear()
            replay = dispatch(url, token)
            replay_calls = dict(operations)
            for operation in ("reserve", "start", "execute", "verify-stage"):
                assert first_calls.get(operation) == 2 and not replay_calls.get(operation)
            assert not replay["results"] and not replay.get("stages")
            assert not any(
                first_calls.get(op) or replay_calls.get(op)
                for op in ("finish", "review", "publish", "complete", "integration-contribution", "integration-finish")
            )
            stages = {item["task"]: item for item in first["stages"]}
            workers = {item["ticket"]: item["receipt"] for item in first["results"]}
            starts = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            assert Counter(item["execution"] for item in starts) == Counter(keys)
            assert len(first["results"]) == len(first["stages"]) == len(keys)
            with workflow.worker.store._connection() as db:
                closures = {
                    r["execution"]: json.loads(r["payload"])
                    for r in db.execute("SELECT execution, payload FROM native_worker_process_closures")
                }
            assert set(closures) == set(stages) == set(workers) == set(keys)
            runs = [
                read_result(
                    host,
                    issue,
                    spec,
                    key,
                    workers[key],
                    stages[key],
                    next(s for s in starts if s["execution"] == key),
                    closures[key],
                )
                for issue, spec, key in zip(issues[:2], TASKS[:2], keys, strict=True)
            ]
            pending = host.detail(issues[2])
            denied = host.api("authorize", issue=pending["id"])
            assert denied.status_code == 409 and pending["execution_progress"] is None
            assert pending["task_confirmation"]["status"] == "pending" and pending["task_confirmation"]["revision"] == 0
            bound = domain.db.execute("SELECT issue,id FROM native_tasks").fetchall()
            assert sorted((r["issue"], r["id"]) for r in bound) == sorted(zip([i["id"] for i in issues[:2]], keys))
    # Record the actual private editor and its copied sidecars before removing the temporary installation.
    package = {}
    for path in editor.parent.iterdir():
        if path.is_file() and path.name != "_sc_":
            package[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(
        receiver=dict(
            platform=platform.system(),
            architecture=platform.machine(),
            python=platform.python_version(),
            editor_package=package,
        ),
        design=dict(id=host.doc, version=1),
        confirmations=confirmations,
        runs=runs,
        unsigned=dict(
            issue_id=pending["id"],
            number=pending["number"],
            target=pending["task_target"],
            confirmation=pending["task_confirmation"],
            authorization_status=denied.status_code,
            execution_progress=pending["execution_progress"],
            executions=0,
            physical_starts=0,
        ),
        dispatch_calls=first_calls,
        replay_calls=replay_calls,
        physical_starts=len(starts),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="workbench-k03-") as folder, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        result = exercise(Path(folder), binary)
    assert not Path(folder).exists()
    engine_name = (
        binary.name.removesuffix(".console.exe") + ".exe" if binary.name.endswith(".console.exe") else binary.name
    )
    report = dict(
        request_id="gonggong-ai-workbench-plan1-k03",
        issue_number=1715,
        passed=True,
        verified_at=datetime.now(timezone.utc).isoformat(),
        editor_sha256=result["receiver"]["editor_package"][engine_name],
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        tested_files={
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in [
                "tests/editor/run_workbench_k03_stage_acceptance.py",
                "tests/editor/workbench_task_confirmations.gd",
                "tests/editor/run_workbench_task_confirmations.py",
                "customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs",
                "customizations/components/tianxuan/sinan-workorders/native_workflow.py",
                "customizations/components/tianxuan/sinan-workorders/native_worker.py",
            ]
        },
        result=result,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
