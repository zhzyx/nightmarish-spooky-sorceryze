"""Exercise source-loaded native controllers with an isolated real Tianxuan service.

This proves the GDScript controller contract, not that a new editor binary contains it.
The compiled dock integration is verified separately against the candidate editor.
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn
from editor_test_isolation import copy_editor
from fastapi import Request
from run_unified_settings_native import sanitized_environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/server"))
from api import create_app  # noqa: E402
from git_service import GitService  # noqa: E402
from merge_queue import MergeQueue  # noqa: E402
from native_store import NativeStore  # noqa: E402
from tianxuan_core import Tianxuan  # noqa: E402


def publish_archive(directory, database, store, owner, repo):
    from importer import canonical, import_inventory
    from migration_status import publish_import

    archive = directory / "archive"
    archive.mkdir()
    records = []
    for kind, identifier, content, relations in [
        ("issue", "14", {"number": 14, "title": "原生归档工单", "body": "只读历史，不触发任务执行。"}, []),
        (
            "issue_comment",
            "22",
            {"issue_url": "https://api.github.com/repos/fixture/repo/issues/14", "body": "归档评论"},
            ["github:fixture/repo/issue/14"],
        ),
        ("attachment", "42", {"url": "https://fixture.invalid/original.bin"}, ["github:fixture/repo/issue/14"]),
    ]:
        records.append(
            canonical(
                dict(
                    kind=kind,
                    source_id=f"github:fixture/repo/{kind}/{identifier}",
                    content=content,
                    relations=relations,
                    mode="record_only",
                    sha256=hashlib.sha256(canonical(content)).hexdigest(),
                )
            )
            + b"\n"
        )
    stream = b"".join(records)
    (archive / "records.jsonl").write_bytes(stream)
    revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "main"], text=True).strip()
    report = archive / "report.json"
    report.write_bytes(
        canonical(
            dict(
                source="fixture/repo",
                revision=revision,
                counts={"issue": 1, "issue_comment": 1, "attachment": 1},
                historical_policy="record_only",
                records_sha256=hashlib.sha256(stream).hexdigest(),
            )
        )
    )
    original = archive / "original.bin"
    original.write_bytes(b"Native archive attachment\n")
    bundle = archive / "history.bundle"
    subprocess.run(["git", "-C", str(repo), "bundle", "create", str(bundle), "--all"], check=True, capture_output=True)
    receipt = import_inventory(
        report,
        database,
        owner["tenant_id"],
        owner["user_id"],
        artifacts={
            "github:fixture/repo/attachment/42": (original, hashlib.sha256(original.read_bytes()).hexdigest()),
            "github:fixture/repo/history.bundle": (bundle, hashlib.sha256(bundle.read_bytes()).hexdigest()),
        },
    )
    publish_import(database, owner["tenant_id"], "workspace", owner["user_id"], receipt["module"], receipt["revision"])


def deterministic_entry(directory, store, native, node):
    for component in ("duobao", "sinan-workorders"):
        sys.path.insert(0, str(ROOT / "customizations/components/tianxuan" / component))
    from native_entry_factory import OrdinaryEntry
    from native_model_host import executable_sha256
    from test_native_entry_normal import PROGRAM

    program = directory / "deterministic_installation.py"
    program.write_text(
        PROGRAM.replace("deadline=time.monotonic()+20", "deadline=time.monotonic()+90"), encoding="utf-8"
    )
    python = str(Path(sys.executable).resolve())
    driver = str(ROOT / "customizations/components/tianxuan/sinan-workorders/native_entry_driver.mjs")
    files = {path: executable_sha256(path) for path in (python, str(node), str(program), driver)}
    environment = {key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR"}}
    commands = {
        role: dict(argv=[python, "-X", "utf8", str(program), role], env=environment)
        for role in ("planner", "producer", "checker", "reviewer")
    }
    commands["dispatcher"] = dict(argv=[str(node), driver], env=environment)
    spec = dict(
        version=2,
        mode="deterministic-test",
        identity="native-ui-deterministic-entry-fixture",
        files=files,
        commands=commands,
        principals=dict(
            producer="test-producer", checker="test-checker", reviewer="test-reviewer", publisher="test-publisher"
        ),
        scopes={"text": {"outputs": ["text/output"]}},
        complexity={"simple": ["text"]},
        catalog=[dict(id="installed", available=True, targets=["agent"], capabilities=["text"])],
    )
    manifest = directory / "installation.json"
    manifest.write_text(json.dumps(spec), encoding="utf-8")
    entry = OrdinaryEntry(
        store, native, manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(), directory / "execution-state"
    )
    return entry


def model_fixture(directory):
    positions = (-1, -1, 0, 1, -1, 0, 0, 1, 0)
    geometry = struct.pack("<18f", *positions, *(0, 0, 1) * 3)
    definition = dict(
        asset={"version": "2.0"},
        buffers=[{"byteLength": len(geometry)}],
        bufferViews=[
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 36},
        ],
        accessors=[
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [-1, -1, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
        ],
        meshes=[{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "mode": 4, "material": 0}]}],
        materials=[{"pbrMetallicRoughness": {"baseColorFactor": [0.2, 0.8, 0.7, 1]}, "doubleSided": True}],
        nodes=[{"mesh": 0}],
        scenes=[{"nodes": [0]}],
        scene=0,
    )

    def write(name, value):
        document = json.dumps(value, separators=(",", ":")).encode()
        document += b" " * (-len(document) % 4)
        glb = struct.pack("<5I", 0x46546C67, 2, 28 + len(document) + len(geometry), len(document), 0x4E4F534A)
        glb += document + struct.pack("<2I", len(geometry), 0x004E4942) + geometry
        path = directory / name
        path.write_bytes(glb)
        return path

    valid = write("native-triangle.glb", definition)
    definition["extensionsUsed"] = ["KHR_materials_unlit"]
    definition["extensionsRequired"] = ["KHR_materials_unlit"]
    definition["materials"][0]["extensions"] = {"KHR_materials_unlit": {}}
    write("unlit-model.glb", definition)
    del definition["extensionsUsed"], definition["extensionsRequired"], definition["materials"][0]["extensions"]
    definition["buffers"][0]["uri"] = "https://fixture.invalid/never-read.bin"
    write("external-model.glb", definition)
    del definition["buffers"][0]["uri"]
    definition["nodes"][0]["children"] = [0]
    write("cyclic-model.glb", definition)
    return valid


def exercise(
    directory, binary, native_shell=False, execution=False, node=None, layout=False, controls=False, races=False
):
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Native Tianxuan controller"\n'
    )
    (project / "linked.gd").write_text("extends Node2D\n\nvar fixture_value := 1\n")
    (project / "fixture.tscn").write_text(
        '[gd_scene format=3]\n\n[node name="Fixture" type="Node2D"]\nposition = Vector2(4, 7)\n'
    )
    import_source = directory / "import-source.tres"
    import_source.write_text(
        '[gd_resource type="Resource" format=3]\n\n[resource]\nresource_name = "Native import fixture"\n'
    )
    model_source = model_fixture(directory)
    probe = (
        "tianxuan_races.gd"
        if races
        else "tianxuan_execution_controls.gd"
        if controls
        else "tianxuan_layout.gd"
        if layout
        else "tianxuan_execution.gd"
        if execution
        else "tianxuan_native_shell.gd"
        if native_shell
        else "tianxuan_controller.gd"
    )
    (project / "probe.gd").write_bytes(Path(__file__).with_name(probe).read_bytes())
    store = Tianxuan(str(directory / "domain.sqlite"))
    password = secrets.token_urlsafe(32)
    owner = store.register("Isolated studio", "first@example.invalid", password)
    module = store.create_business_module(
        owner["user_id"], "workspace", "原生界面测试", call_id="native-ui-fixture-module"
    )
    viewer = store.add_member(owner["user_id"], "second@example.invalid", password, role="viewer")
    key = store.issue_access_key(owner["user_id"], viewer["user_id"], "Native fixture")["key"]
    repo_root = directory / "repos"
    repo_root.mkdir()
    git = GitService()
    fixture_repo = git.create_repo(repo_root, "fixture", "main")
    git.commit(
        fixture_repo,
        "main",
        "Create isolated fixture",
        {"README.md": "原生仓库测试\n", "scripts/main.gd": "extends Node\n"},
        "Native fixture",
        "fixture@example.invalid",
    )
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}):
        editor = copy_editor(binary, directory / "engine")
    modes = {key: value for key, value in os.environ.items() if not key.startswith("TIANXUAN_")}
    modes.update(
        GONGGONG_WORKSPACE="",
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_REQUIRE_KEYS="0",
        TIANXUAN_TENANT_ID=owner["tenant_id"],
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_REPO_ROOT=str(repo_root),
        TIANXUAN_IMPORT_ALLOW_LOCAL="1",
    )
    with patch.dict(os.environ, modes, clear=True), socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        api = "http://127.0.0.1:" + str(sock.getsockname()[1])
        queue = MergeQueue(str(directory / "queue.sqlite"), git, role_resolver=store.role_of)
        native = NativeStore(directory / "native.sqlite")
        entry = deterministic_entry(directory, store, native, node) if execution else None
        app = create_app(
            store,
            native_store=native,
            merge_queue=queue,
            native_entry=entry,
            native_workflow=entry.workflow if entry else None,
        )
        publish_archive(directory, directory / "native.sqlite", store, owner, fixture_repo)

        @app.get("/api/v1/native-test/delayed")
        async def delayed(request: Request):
            actor = request.state.verified_actor
            await asyncio.sleep(0.15)
            return {"actor": actor}

        if races:
            armed_titles = set()

            @app.post("/api/v1/native-test/title-race/{doc_id}")
            async def arm_title_race(doc_id: str):
                armed_titles.add(doc_id)
                return {"armed": True}

            @app.middleware("http")
            async def controlled_interleavings(request: Request, call_next):
                route = request.url.path
                if route.endswith("/merge/preview"):
                    doc_id = route.split("/")[-3]
                    if doc_id in armed_titles:
                        armed_titles.remove(doc_id)
                        head = store.get_doc(doc_id)
                        store.update_doc(
                            owner["user_id"], doc_id, head["body_md"], head["version"], title="Remote title C"
                        )
                if (
                    request.method == "GET"
                    and route.startswith("/api/v1/game-config/projects/")
                    and route.count("/") == 5
                ):
                    await asyncio.sleep(0.4)
                response = await call_next(request)
                if request.method == "POST" and route.startswith("/api/v1/docs/") and route.endswith("/comments"):
                    await asyncio.sleep(0.4)
                return response

        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Isolated service did not start")
                time.sleep(0.03)
            env = {k: v for k, v in sanitized_environment(directory).items() if not k.startswith(("TIANXUAN_", "TX_"))}
            env.update(
                TX_SOURCE=str(ROOT),
                TX_API=api,
                TX_PASSWORD=password,
                TX_VIEWER_KEY=key,
                TX_DRAFTS=str(directory / "drafts"),
                TIANXUAN_API=api,
                TX_IMPORT_SOURCE=str(import_source),
                TX_MODULE=module["id"],
                TX_NATIVE_SHELL="1" if native_shell else "0",
            )
            env["TX_IMPORT_REPOSITORY"] = str(fixture_repo)
            env["TX_MODEL_SOURCE"] = str(model_source)
            env["TX_EXECUTION_WORKERS"] = str(directory / "execution-state/workers")
            command = [
                str(editor),
                "--headless",
                *(["--editor"] if native_shell else []),
                "--path",
                str(project),
                "--script",
                "res://probe.gd",
            ]
            result = subprocess.run(
                command,
                env=env,
                cwd=directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300 if controls else 180 if execution else 90,
            )
            output = result.stdout + result.stderr
            for credential in (password, key):
                if credential in output:
                    raise AssertionError("A fixture credential appeared in process output")
            if result.returncode or "SCRIPT ERROR" in output:
                raise AssertionError(output[-12000:])
            reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
            report = next((value for value in reports if value.get("passed") is True), None)
            if report is None:
                raise AssertionError("Missing native controller completion receipt:\n" + output[-12000:])
            report["process_diagnostics"] = [
                line for line in result.stderr.splitlines() if line.startswith(("ERROR:", "WARNING:"))
            ]
            report["display_boundary"] = (
                "Headless controls and geometry only; no display pixels, native window or IME acceptance. Renderer/ObjectDB shutdown diagnostics are retained separately."
            )
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in {".json", ".cfg", ".godot", ".gd"}:
                    content = path.read_bytes()
                    assert password.encode() not in content and key.encode() not in content, (
                        "Credential persisted in private state"
                    )
            with editor.open("rb") as copied_binary:
                report["binary_sha256"] = hashlib.file_digest(copied_binary, "sha256").hexdigest()
            if execution:
                report["runtime_mode"] = "deterministic-test"
                report["runtime_inputs_sha256"] = {
                    Path(path).name: digest for path, digest in entry.installation.spec["files"].items()
                }
            return report
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            queue.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--native-shell", action="store_true")
    parser.add_argument(
        "--layout", action="store_true", help="Exercise compiled native views at narrow and wide viewport sizes"
    )
    parser.add_argument(
        "--execution",
        action="store_true",
        help="Use actual entry coordination with explicitly deterministic installed role programs",
    )
    parser.add_argument("--node", type=Path)
    parser.add_argument(
        "--controls",
        action="store_true",
        help="Verify compiled execution launch, target confirmation and workflow controls",
    )
    parser.add_argument(
        "--races",
        action="store_true",
        help="Reproduce focused merge, comment acknowledgement and initial configuration races",
    )
    args = parser.parse_args()
    if args.layout or args.races:
        args.native_shell = True
    if args.races and (args.layout or args.execution or args.controls):
        parser.error("--races selects its own probe")
    if args.controls:
        args.native_shell = args.execution = True
    if args.layout and args.execution:
        parser.error("--layout and --execution select different probes")
    if args.execution and (args.node is None or not args.node.is_file()):
        parser.error("--execution requires an installed --node executable")
    files = [
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "editor/docks/tianxuan").glob("*"))
        if path.is_file() and not path.name.endswith(".gen.h")
    ]
    files += [
        "editor/docks/workbench/business_session.gd",
        "tests/editor/tianxuan_controller.gd",
        "tests/editor/tianxuan_native_shell.gd",
        "tests/editor/run_tianxuan_controller.py",
    ]
    files += [
        "editor/SCsub",
        "editor/docks/SCsub",
        "editor/editor_node.cpp",
        "editor/editor_builders.py",
        "editor/docks/workbench/AIWorkbenchSidebar.cpp",
    ]
    if args.layout:
        files += ["tests/editor/tianxuan_layout.gd"]
    if args.execution:
        files += [
            "tests/editor/tianxuan_execution.gd",
            "customizations/components/tianxuan/server/test_native_entry_normal.py",
        ]
    if args.controls:
        files += ["tests/editor/tianxuan_execution_controls.gd"]
    if args.races:
        files += ["tests/editor/tianxuan_races.gd"]
    fingerprints = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
    with tempfile.TemporaryDirectory(prefix="tianxuan-native-controller-") as temporary:
        report = exercise(
            Path(temporary).resolve(),
            args.godot.resolve(),
            args.native_shell,
            args.execution,
            args.node.resolve() if args.node else None,
            args.layout,
            args.controls,
            args.races,
        )
    if any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != fingerprints[p] for p in files):
        raise AssertionError("Candidate source changed during validation; rerun the affected check")
    level = (
        "compiled_native_shell_real_isolated_service_headless"
        if args.native_shell
        else "source_loaded_controllers_real_isolated_service"
    )
    report.update(evidence_level=level, input_sha256=fingerprints)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({
            "passed": report["passed"],
            "checks": len(report["checks"]),
            "evidence_level": report["evidence_level"],
        })
    )


if __name__ == "__main__":
    main()
