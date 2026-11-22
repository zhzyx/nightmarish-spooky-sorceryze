"""Exercise the compiled task panel, local owned workers and durable Tianxuan readback."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_confirmed_native_stage import StageHost, copy_editor, create_app, fixture, install_stage_probe, serve
from run_workbench_design_tasks import sanitized_environment


def panel(root, engine, client, issue, key, operation):
    with tempfile.TemporaryDirectory(dir=root) as directory:
        project = Path(directory)
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="S10"\n', encoding="utf-8")
        shutil.copyfile(Path(__file__).with_name("workbench_task_controls.gd"), project / "probe.gd")
        env = {k: v for k, v in sanitized_environment(project).items() if not k.startswith("TIANXUAN_")}
        env.update(
            TIANXUAN_API=str(client.base_url),
            TIANXUAN_TOKEN=client.headers["Authorization"].split()[1],
            TIANXUAN_PROJECT="studio",
            S10_TASK=json.dumps(dict(number=issue["number"], key=key, operation=operation)),
        )
        result = subprocess.run(
            [engine, "--headless", "--single-window", "--editor", "--path", directory, "--script", "res://probe.gd"],
            cwd=directory,
            env=env,
            capture_output=True,
            timeout=65,
        )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        assert env["TIANXUAN_TOKEN"] not in output
        lines = [line.removeprefix("S10_NATIVE=") for line in output.splitlines() if line.startswith("S10_NATIVE=")]
        if result.returncode or len(lines) != 1 or "SCRIPT ERROR" in output:
            raise RuntimeError(output[-6000:])
        return json.loads(lines[0])


def exercise(root, executable):
    engine = copy_editor(executable, root / "engine")
    with contextmanager(fixture.__wrapped__)(root) as (workflow, actor, tenant, _, initial, folder):
        domain = workflow.domain
        host = StageHost()
        host.doc = domain.create_doc(actor, "Signed controls", "Alpha\n\nBeta\n\nGamma")["id"]
        domain.design_signoff(actor, host.doc, 1, "Observe each original")
        issues = domain.split_design(
            actor,
            host.doc,
            1,
            "studio",
            [
                dict(title=module, paragraph=i, module_id="default", acceptance="individual output")
                for i, module in enumerate("abc", 1)
            ],
            "s10-split",
        )
        _, plan = install_stage_probe(workflow, initial, folder, stage="preview")
        modules = {issue["id"]: module for issue, module in zip(issues, "abc", strict=True)}
        workflow.installed_plan = lambda _, issue: dict(
            plan,
            selected={modules[issue]: initial[modules[issue]]},
            writes={modules[issue]: ["output"]},
            stage_criteria="individual output",
        )
        profile = workflow.worker.profiles["local"]
        profile["timeout"] = 180
        profile["env"]["GATES"] = str(folder)
        Path(profile["argv"][1]).write_text(
            "import json, os, pathlib, time\n"
            "context = pathlib.Path(os.environ['NATIVE_CONTEXT'])\n"
            "module = json.loads(context.read_text(encoding='utf-8'))['title']\n"
            "gates = pathlib.Path(os.environ['GATES'])\n"
            "with (gates / (module + '.starts')).open('a', encoding='utf-8') as f:\n"
            "    print(json.dumps(dict(key=context.parent.name,pid=os.getpid())), file=f)\n"
            "while not (gates / (module + '.go')).exists(): time.sleep(.02)\n"
            "(pathlib.Path(module) / 'output').write_text(module + ' produced')\n",
            encoding="utf-8",
        )
        modes = dict(
            TIANXUAN_AUTH_MODE="accounts", TIANXUAN_TENANT_ID=tenant, TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid"
        )
        with patch.dict(os.environ, modes):
            app = create_app(domain, native_store=workflow.worker.store, native_workflow=workflow)
        requests = Counter()

        @app.middleware("http")
        async def observe(request, next_handler):
            response = await next_handler(request)
            operation = request.url.path.rsplit("/", 1)[-1]
            if operation in {"pause", "resume", "cancel"}:
                requests[operation, response.status_code] += 1
            return response

        with (
            patch.dict(os.environ, modes),
            serve(app, 0) as port,
            httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                headers={"Authorization": "Bearer " + domain.issue_session(actor)},
                trust_env=False,
                timeout=200,
            ) as host.client,
        ):
            result = run_controls(root, engine, host, workflow, issues, folder)
            assert all(requests[operation, 200] == 2 for operation in ("pause", "resume", "cancel"))
            result["http_control_requests"] = [
                dict(operation=op, status=status, count=count) for (op, status), count in sorted(requests.items())
            ]
    result["editor_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
    return result


def run_controls(root, engine, host, workflow, issues, folder):
    keys = []
    for issue in issues:
        host.target(issue, "preview", "individual output")
        host.confirm(issue).raise_for_status()
        keys.append(host.api("authorize", issue=issue["id"]).raise_for_status().json())

    def call(operation, i, **kwargs):
        return host.api(operation, key=keys[i], **kwargs).raise_for_status().json()

    def progress(i):
        return host.detail(issues[i])["execution_progress"]

    def wait_start(name):
        start = folder / (name + ".starts")
        deadline = time.monotonic() + 15
        while not start.exists() or not start.read_bytes().endswith(b"\n"):
            if time.monotonic() > deadline:
                raise TimeoutError(name + " failed to record process start")
            time.sleep(0.02)

    def control(i, operation):
        receipt = panel(root, engine, host.client, issues[i], keys[i], operation)
        expected = int(receipt["before"]["control"]["revision"])
        repeated = call(operation, i, issue=issues[i]["id"], expected=expected)
        events = [e for e in repeated["events"] if e["step"] == "control." + operation]
        assert len(events) == 1 and events[0]["details"]["reviewed_sequence"] == expected
        return dict(expected=expected, readback=receipt["after"]["control"], replayed_sequence=events[0]["sequence"])

    with ThreadPoolExecutor(2) as pool:
        try:
            for i in (0, 1):
                assert host.reserve(keys[i]).raise_for_status().json()
            a, b = [pool.submit(call, "execute", i) for i in (0, 1)]
            wait_start("a")
            wait_start("b")
            pause = control(0, "pause")
            assert progress(0)["control"]["state"] == "pausing" and progress(1)["state"] == "running"
            (folder / "a.go").touch()
            assert a.result(10)["state"] == "paused"
            paused = progress(0)
            assert paused["candidate"] and paused["state"] == "paused" and progress(1)["state"] == "running"
            assert host.api("verify-stage", key=keys[0]).status_code == 409
            expected = paused["control"]["revision"]
            payload = dict(key=keys[0], issue=issues[0]["id"], expected=expected)
            assert host.api("resume", **dict(payload, issue=issues[1]["id"])).status_code != 200
            assert host.api("resume", **dict(payload, expected=expected - 1)).status_code == 409
            authority = workflow.authorize
            try:
                workflow.authorize = lambda actor, issue, action: (
                    action != "execute" and authority(actor, issue, action)
                )
                denied = host.api("resume", **payload)
                assert denied.status_code == 403 and progress(0)["state"] == "paused"
            finally:
                workflow.authorize = authority
            resume = control(0, "resume")
            assert paused["candidate"] == progress(0)["candidate"] and progress(0)["state"] == "produced"
            stage = call("verify-stage", 0)
            assert stage["state"] == "stage-reached" and stage["candidate"] == paused["candidate"]
            (folder / "b.go").touch()
            peer = b.result(10)
            assert peer["state"] == "produced" and peer["exit_code"] == 0
            peer_stage = call("verify-stage", 1)
            assert peer_stage["state"] == "stage-reached" and peer_stage["candidate"] == peer["candidate"]
            assert host.reserve(keys[2]).raise_for_status().json()
            c = pool.submit(call, "execute", 2)
            wait_start("c")
            cancel = control(2, "cancel")
            assert c.result(10)["state"] == "cancelled"
            reopened = panel(root, engine, host.client, issues[2], keys[2], "read")
            assert reopened["before"]["control"]["state"] == "cancelled"
            assert reopened["after"]["control"]["actions"] == []
            assert call("execute", 2)["state"] == "cancelled"
            assert host.api("authorize", issue=issues[2]["id"]).json() == keys[2]
            assert not host.reserve(keys[2]).raise_for_status().json()
            assert not host.api("inspect").json()["snapshot"]["ready"]
        finally:
            for name in "abc":
                (folder / (name + ".go")).touch(exist_ok=True)
    launches = [json.loads(line) for name in "abc" for line in (folder / (name + ".starts")).read_text().splitlines()]
    assert Counter(row["key"] for row in launches) == Counter(keys)
    with workflow.worker.store._connection() as db:
        closures = {
            row["execution"]: json.loads(row["payload"])
            for row in db.execute("SELECT * FROM native_worker_process_closures")
        }
    assert set(closures) == set(keys) and closures[keys[2]]["exit_code"] is None
    return dict(
        passed=True,
        runs=keys,
        starts=launches,
        closures=closures,
        pause=pause,
        resume=resume,
        cancel=cancel,
        pause_checkpoint=paused,
        resumed=stage,
        peer=peer_stage,
        reopened=reopened["after"],
        authorization_denied=denied.status_code,
        cancelled_replay_starts=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="s10-native-") as directory, patch.dict(os.environ, GONGGONG_WORKSPACE=""):
        result = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
