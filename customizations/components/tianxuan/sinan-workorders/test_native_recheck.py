"""Save a retimed scene, run its installed check, and read back the object receipts over authenticated HTTP."""

import base64
import json
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import test_native_stage_stop
import uvicorn

fixture = test_native_stage_stop.fixture
host = test_native_stage_stop.host

SCENE = """[gd_scene load_steps=3 format=3]

[sub_resource type="Animation" id="Animation_move"]
resource_name = "move"
length = {duration}.0

[sub_resource type="AnimationLibrary" id="AnimationLibrary_main"]
_data = {{&"move": SubResource("Animation_move")}}

[node name="Scene" type="Node"]

[node name="Player" type="AnimationPlayer" parent="."]
libraries = {{&"": SubResource("AnimationLibrary_main")}}
"""


def edit(h, base, **files):
    change = dict(
        module="a",
        base=base,
        reads=None,
        edits={path: base64.b64encode(content.encode()).decode() for path, content in files.items()},
    )

    return (
        h.client
        .post("/api/v1/native/batches", json=dict(request_key=uuid4().hex, changes=[change]))
        .raise_for_status()
        .json()["revisions"]["a"]
    )


@pytest.fixture
def live_host(host):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        server = uvicorn.Server(uvicorn.Config(host.client.app, log_level="error", ws="none"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            with httpx.Client(
                base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
                headers={"Authorization": host.client.headers["Authorization"]},
                timeout=45,
                trust_env=False,
            ) as client:
                host.client = client
                yield host
        finally:
            server.should_exit = True
            thread.join(10)
            assert not thread.is_alive()


@pytest.fixture
def scene(live_host, tmp_path):
    h = live_host
    issue = test_native_stage_stop.install_preview(h)
    runner = h.workflow.runner
    runner.cache.policies["check"]["reads"] = {"a": ["preview.svg"]}
    runner.cache.policies["motion"] = dict(version="1", reads={"a": ["scene.tscn"]}, max_age_seconds=3600)
    spec = runner._registry["motion"] = deepcopy(runner._registry["check"])
    godot = os.environ.get("GONGGONG_V10_GODOT")
    if godot:
        # The installed check receives a bounded environment, including its own editor settings and cache.
        for name in (
            "APPDATA",
            "LOCALAPPDATA",
            "USERPROFILE",
            "HOME",
            "TEMP",
            "TMP",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "XDG_DATA_HOME",
        ):
            folder = tmp_path / name
            folder.mkdir()
            spec["env"][name] = str(folder)
        probe = tmp_path / "read_scene.gd"
        probe.write_text(
            "extends SceneTree\nfunc _initialize():\n"
            '\tvar scene = load(OS.get_environment("DUOBAO_INPUT").path_join("a/scene.tscn")).instantiate()\n'
            '\tvar duration = scene.get_node("Player").get_animation("move").length\n'
            '\tprint("duration=", duration)\n\tscene.free()\n\tquit(0 if duration <= 20 else 1)\n'
        )
        spec["argv"] = [
            godot,
            "--headless",
            "--path",
            "{output}",
            "--log-file",
            "{output}/godot.log",
            "--script",
            str(probe),
        ]
        spec["timeout"] = 25
    else:
        spec["argv"][2] = (
            "import os,pathlib,re; scene=(pathlib.Path(os.environ['DUOBAO_INPUT'])/'a/scene.tscn').read_text(); "
            "duration=float(re.search(r'(?m)^length = ([0-9.]+)$',scene)[1]); print(duration); assert duration<=20"
        )
    h.plan.update(checks=["check", "motion"], writes={"a": ["preview.svg", "scene.tscn"]})
    initial = edit(
        h,
        h.plan["selected"]["a"],
        **{"scene.tscn": SCENE.format(duration=12), "preview.svg": test_native_stage_stop.PREVIEW},
    )
    h.plan["selected"]["a"] = initial
    key = test_native_stage_stop.signed(h, issue)
    h.reserve(key).raise_for_status()
    terminal = h.api("execute", key=key).raise_for_status().json()
    assert terminal["state"] == "produced" and terminal["exit_code"] == 0
    stage = h.api("verify-stage", key=key).raise_for_status().json()
    assert stage["state"] == "stage-reached", stage
    url = f"/api/v1/native/workflow/tasks/{key}/validation/a/"
    return h, issue, key, initial, url, stage


def physical(h):
    with h.workflow.runner.store._connection() as db:
        rows = db.execute("SELECT payload FROM native_check_runs ORDER BY rowid").fetchall()
    return [
        dict(
            tool=r["check"],
            candidate=r["candidate"],
            state=r["state"],
            code=r["exit_code"],
            evidence=r["evidence"],
            log=json.loads(r["log"])["output_base64"],
        )
        for record in rows
        if (r := json.loads(record["payload"]))["state"] == "complete" and Path(r["workspace"], "process.log").is_file()
    ]


@pytest.mark.parametrize("duration,outcome", [(17, "passed"), (25, "failed")])
def test_targeted_scene_recheck(scene, duration, outcome, record_property):
    h, _, key, initial, url, stage = scene
    target = url + "scene.tscn"
    asset = url + "preview.svg"
    original = h.client.get(target).raise_for_status().json()
    untouched = h.client.get(asset).raise_for_status().json()
    edited = edit(h, initial, **{"scene.tscn": SCENE.format(duration=duration)})
    pending = h.client.get(target).raise_for_status().json()
    assert pending["current"]["checks"] == {"motion": "pending"}
    assert pending["recheck"] == dict(revision=edited, checks=["motion"])
    body = dict(revision=edited)
    before_runs = physical(h)
    assert [r["tool"] for r in before_runs] == ["check", "motion"]
    assert h.client.post(target, json=dict(revision=initial)).status_code == 409
    assert h.client.post(target, json=dict(**body, checks=["check"])).status_code == 422
    assert h.client.post(url + "outside", json=body).status_code == 403
    assert h.client.post(target, json=body, headers={"Authorization": ""}).status_code == 401
    foreign = h.workflow.domain.register("foreign", "foreign@example.invalid", "password")["user_id"]
    foreign_header = {"Authorization": "Bearer " + h.workflow.domain.issue_session(foreign)}
    assert h.client.post(target, json=body, headers=foreign_header).status_code in {403, 404}
    assert h.client.post(asset, json=body).raise_for_status().json()["recheck"] is None
    assert physical(h) == before_runs
    settled = h.client.post(target, json=body).raise_for_status().json()
    assert settled["current"]["checks"] == {"motion": outcome}
    assert settled["receipts"][:-1] == original["receipts"]
    receipt = settled["receipts"][-1]
    assert receipt["revision"] == edited and receipt["candidate"] != stage["candidate"]
    assert receipt["sha256"] == settled["current"]["sha256"] and receipt["outcome"] == outcome
    assert h.client.post(target, json=body).raise_for_status().json() == settled
    assert h.client.get(target).raise_for_status().json() == settled
    saved_asset = h.client.get(asset).raise_for_status().json()
    assert saved_asset["current"]["revision"] == edited
    assert saved_asset["current"]["checks"] == {"check": "passed"} and saved_asset["receipts"] == untouched["receipts"]
    runs = physical(h)
    assert runs[:-1] == before_runs and runs[-1]["tool"] == "motion"
    assert (
        runs[-1]["candidate"] == receipt["candidate"] and runs[-1]["evidence"] == receipt["result_location"]["evidence"]
    )
    assert runs[-1]["code"] == (0 if outcome == "passed" else 1)
    if os.environ.get("GONGGONG_V10_GODOT"):
        for fact, seconds in zip((runs[1], runs[-1]), (12, duration), strict=True):
            output = base64.b64decode(fact["log"]).decode()
            assert f"duration={seconds}.0" in output and "ERROR:" not in output, output
    assert h.api("status", key=key).json()["stage_result"] == stage
    with h.workflow.worker.store._connection() as db:
        (closure,) = db.execute("SELECT payload FROM native_worker_process_closures WHERE execution=?", (key,))
    assert len(h.observations()) == 1 and json.loads(closure[0])["exit_code"] == 0
    record_property(
        "targeted",
        json.dumps(
            dict(
                duration=duration,
                original=original,
                pending=pending,
                receiver=settled,
                retained_asset=saved_asset,
                producer=dict(starts=len(h.observations()), exit_code=0, task=key),
                check_runs=runs,
                original_stage=stage,
            )
        ),
    )


@pytest.mark.parametrize("interruption", ["save", "revocation", "duplicate"])
def test_recheck_overlap(scene, monkeypatch, interruption, record_property):
    h, issue, _, initial, url, _ = scene
    target = url + "scene.tscn"
    edited = edit(h, initial, **{"scene.tscn": SCENE.format(duration=17)})
    body = dict(revision=edited)
    completed, resume = threading.Event(), threading.Event()
    runner = h.workflow.runner
    execute = runner.execute

    def overlapping(*args):
        fact = execute(*args)
        if not completed.is_set():
            completed.set()
            assert resume.wait(15)
        return fact

    monkeypatch.setattr(runner, "execute", overlapping)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(h.client.post, target, json=body)
        try:
            assert completed.wait(15)
            if interruption == "save":
                newer = edit(h, edited, **{"scene.tscn": SCENE.format(duration=18)})
            elif interruption == "revocation":
                h.confirm(issue, "revoked").raise_for_status()
            else:
                second = h.client.post(target, json=body).raise_for_status().json()
        finally:
            resume.set()
        result = pending.result()
    if interruption == "duplicate":
        assert result.raise_for_status().json() == second and len(second["receipts"]) == 2
    else:
        assert result.status_code in {409, 422}
        view = h.client.get(target).raise_for_status().json()
        assert view["current"]["state"] == "pending" and len(view["receipts"]) == 1
        if interruption == "save":
            assert view["current"]["revision"] == newer
        else:
            assert h.client.post(target, json=body).status_code in {409, 422}
    assert [r["tool"] for r in physical(h)] == ["check", "motion", "motion"]
    record_property(
        "overlap",
        json.dumps(
            dict(
                interruption=interruption,
                post_status=result.status_code,
                current=h.client.get(target).raise_for_status().json(),
                physical_checks=[r["tool"] for r in physical(h)],
            )
        ),
    )
    if interruption == "save":
        retried = h.client.post(target, json=dict(revision=newer)).raise_for_status().json()
        assert retried["current"]["state"] == "passed" and retried["receipts"][-1]["revision"] == newer
        assert all(fact["revision"] != edited for fact in retried["receipts"])


def test_original_check_authority_and_policy_required(scene, monkeypatch):
    h, _, _, initial, url, _ = scene
    target = url + "scene.tscn"
    body = dict(revision=edit(h, initial, **{"scene.tscn": SCENE.format(duration=17)}))
    with monkeypatch.context() as denied:
        denied.setattr(h.workflow, "authorize", lambda actor, issue, action: action != "check")
        assert h.client.post(target, json=body).status_code == 403
    policy = h.workflow.runner.cache.policies["motion"]
    policy["reads"] = {"a": ["scene.tscn", "preview.svg"]}
    assert h.client.post(target, json=body).status_code == 409
    assert [r["tool"] for r in physical(h)] == ["check", "motion"]
