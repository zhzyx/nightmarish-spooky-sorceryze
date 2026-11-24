"""Exercise E09 local asset preservation and version choices through the headless editor."""

import argparse
import hashlib
import json
import os
import secrets
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image
from run_workbench_issue_detail import ROOT, NativeStore, Tianxuan, run_probe


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def produce(folder, same_view=False):
    Image.new("RGB", (16, 4) if same_view else (8, 8), (0, 0, 255)).save(folder / "hero.png")
    data = (ROOT / "tests/data/models/suzanne.glb").read_bytes()
    size = struct.unpack_from("<I", data, 12)[0]
    model = json.loads(data[20 : 20 + size])
    model["nodes"][0]["scale"] = [2, 1, 1]
    header = json.dumps(model, separators=(",", ":")).encode()
    header += b" " * (-len(header) % 4)
    chunks = struct.pack("<I4s", len(header), b"JSON") + header + data[20 + size :]
    (folder / "hero.glb").write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks)
    print(json.dumps({"pid": os.getpid(), "parent_pid": os.getppid(), "outputs": ["hero.png", "hero.glb"]}))


def exercise(base, binary, *, same_view=False):
    work = base / "producer"
    work.mkdir()
    command = [sys.executable, str(Path(__file__).resolve()), "--produce", str(work)]
    if same_view:
        command.append("--same-view")
    worker = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        output, errors = worker.communicate(timeout=45)
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait()
    assert worker.returncode == 0, errors
    terminal = json.loads(output)
    # On Windows the venv launcher waits for a separate interpreter process.
    assert worker.pid in (terminal["pid"], terminal["parent_pid"]) and terminal["outputs"] == ["hero.png", "hero.glb"]
    domain = Tianxuan(str(base / "domain.db"))
    native = NativeStore(base / "native.db")
    domain.work_native_store = native
    password = secrets.token_urlsafe(24)
    account = domain.register("Studio", "owner@example.invalid", password)
    actor, tenant = account["user_id"], account["tenant_id"]
    scope = "studio/game"
    changed_during_download = []
    try:
        issue = domain.create_issue(actor, "资产候选", project=scope)
        original = base / "artist"
        original.mkdir()
        image = original / "hero.png"
        Image.new("RGB", (8, 8), (255, 0, 0)).save(image)
        human_bytes = image.read_bytes()
        human_digest = sha(image)
        # The transport starts with another local version. A person saves the red texture while the download runs.
        Image.new("RGB", (8, 8), (0, 255, 0)).save(image)
        prior = sha(image)
        assert prior != human_digest
        model = original / "hero.glb"
        model.write_bytes((ROOT / "tests/data/models/suzanne.glb").read_bytes())
        cases = []
        revision = None
        for i, (kind, path, digest) in enumerate([("concept", image, human_digest), ("model", model, sha(model))]):
            source = work / path.name
            revision = native.submit(
                tenant,
                actor,
                f"produce-{i}",
                [dict(module="art", base=revision, reads=None, edits={path.name: source.read_bytes()})],
            )["revisions"]["art"]
            domain.dispatch_tool(
                actor,
                "work.submit_asset",
                dict(
                    issue_id=issue["id"], expected_version=i, kind=kind, module="art", revision=revision, path=path.name
                ),
                call_id=f"submit-{i}",
            )
            cases.append(
                dict(kind=kind, name=path.name, original=str(path), human_digest=digest, candidate_digest=sha(source))
            )
        route = f"/api/v1/issues/by-number/{issue['number']}/artifacts/1"
        occupied = original / f"candidate-{cases[1]['candidate_digest']}.glb"
        occupied.write_bytes(b"artist's other edited candidate")
        malformed = base / "invalid.glb"
        header = b'{"buffers":[{"byteLength":4}],"accessors":[{"count":{}}]}'
        header += b" " * (-len(header) % 4)
        chunks = struct.pack("<I4s", len(header), b"JSON") + header + struct.pack("<I4s4x", 4, b"BIN\0")
        malformed.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks)

        def save_during_download(request, response):
            if request.url.path == route and not changed_during_download:
                assert request.method == "GET" and response.status_code == 200
                image.write_bytes(human_bytes)
                changed_during_download.append(dict(before=prior, saved=sha(image)))
            return response

        fixture = dict(number=issue["number"], cases=cases, malformed=str(malformed), reopen=same_view)
        observed, http = run_probe(
            base,
            binary,
            "workbench_asset_candidates.gd",
            domain,
            native,
            tenant,
            domain.issue_session(actor),
            scope,
            {"E09_FIXTURE": json.dumps(fixture)},
            password,
            after_response=save_during_download,
            followup_scripts=("workbench_asset_viewport.gd",) * 2 if same_view else (),
        )
    finally:
        domain.db.close()
    assert changed_during_download == [dict(before=prior, saved=human_digest)]
    reopen_reports = []
    if same_view:
        observed, *reopen_reports = observed
        assert len(reopen_reports) == 2 and reopen_reports[0]["pid"] != reopen_reports[1]["pid"]
        assert reopen_reports[0]["comparisons"] == reopen_reports[1]["comparisons"]
    assert len(observed) == 2
    for case, record in zip(cases, observed, strict=True):
        assert record["original_sha256"] == case["human_digest"] != record["candidate_sha256"]
        assert sha(original / record["candidate_filename"]) == record["candidate_sha256"] == case["candidate_digest"]
        assert record["reopened_choice"] == case["candidate_digest"]
        assert [choice["selection"] for choice in record["previews_and_choices"]] == [
            case["human_digest"],
            case["candidate_digest"],
        ]
        if case["kind"] == "concept":
            assert [choice["pixel"] for choice in record["previews_and_choices"]] == ["ff0000", "0000ff"]
            assert record["stale_rejection_exercised"]
            assert image.read_bytes() == (human_bytes if same_view else bytes([1, 2, 3]))
        else:
            assert [choice["mesh_scale"] for choice in record["previews_and_choices"]] == [1, 2]
            assert sha(model) == case["human_digest"]
    metadata = next((base / "project").rglob("project_metadata.cfg")).read_text(encoding="utf-8")
    assert "[workbench_asset_candidates]" in metadata
    for case in cases:
        assert case["candidate_digest"] in metadata
    assert not list(original.glob(".gonggong-*.tmp"))
    assert occupied.read_bytes() == b"artist's other edited candidate"
    return dict(
        editor_sha256=sha(binary.with_name(binary.name.removesuffix(".console.exe") + ".exe"))
        if binary.name.endswith(".console.exe")
        else sha(binary),
        launcher_sha256=sha(binary),
        producer={
            "mode": "deterministic fixture subprocess",
            "launcher_pid": worker.pid,
            **terminal,
            "exit_code": worker.returncode,
        },
        changed_during_download=changed_during_download,
        http=http,
        comparisons=observed,
        **({"project_reopens": reopen_reports} if same_view else {}),
        selection_persisted=True,
        occupied_candidate_preserved=True,
        malformed_model_preview_rejected=True,
        temporary_downloads_remaining=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--same-view", action="store_true", help="Verify A/B references across project reopens.")
    parser.add_argument("--produce", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.produce:
        produce(args.produce, args.same_view)
    else:
        if args.godot is None or args.report is None:
            parser.error("--godot and --report are required")
        with tempfile.TemporaryDirectory(prefix="workbench-e09-") as directory:
            report = exercise(Path(directory), args.godot.resolve(strict=True), same_view=args.same_view)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Passed local texture and model candidate preservation, previews and choices")
