"""Compare the bytes saved by the embedded I14 selector with two immutable Duobao revisions."""

import argparse
import hashlib
import json
import secrets
import tempfile
from pathlib import Path

from run_workbench_issue_detail import NativeStore, Tianxuan, run_probe


def exercise(base, binary):
    store = Tianxuan(str(base / "domain.db"))
    native = NativeStore(base / "native.db")
    store.work_native_store = native
    password = secrets.token_urlsafe(32)
    owner = store.register("I14", "owner@example.invalid", password)
    reader = store.add_member(owner["user_id"], "reader@example.invalid", password, name="Reader", role="viewer")
    scope = "studio/game"
    issue = store.create_issue(owner["user_id"], "Character sheet", project=scope)
    contents = (b"original\x00\xfa", b"revised\x00\xfb", b"retired")
    revisions = []
    path = "characters/hero.bin"
    try:
        for index, data in enumerate(contents):
            revision = native.submit(
                owner["tenant_id"],
                owner["user_id"],
                f"publish-{index}",
                [dict(module="art", base=revisions[-1] if revisions else None, reads=None, edits={path: data})],
            )["revisions"]["art"]
            store.dispatch_tool(
                owner["user_id"],
                "work.submit_asset",
                dict(
                    issue_id=issue["id"],
                    kind="attachment" if index < 2 else "model",
                    module="art",
                    revision=revision,
                    path=path,
                    expected_version=index,
                ),
                call_id=f"bind-{index}",
            )
            revisions.append(revision)
        with native._connection(write=True) as db:
            db.execute(
                "DELETE FROM native_blobs WHERE tenant=? AND digest=?",
                (owner["tenant_id"], hashlib.sha256(contents[2]).hexdigest()),
            )
        records, reads = run_probe(
            base,
            binary,
            "workbench_issue_artifacts.gd",
            store,
            native,
            owner["tenant_id"],
            store.issue_session(reader["user_id"]),
            scope,
            {"I14_NUMBER": str(issue["number"]), "I14_OUTPUT": str(base)},
            password,
        )
    finally:
        store.db.close()
    assert len(records) == len(revisions)
    assert not list(base.glob(".gonggong-*.tmp"))
    for index, record in enumerate(records):
        assert record["reference"]["revision"] == revisions[index] and record["reference"]["path"] == path, record
        assert revisions[index][:12] in record["label"]
        destination = base / f"selected-{2 - index}.bin"
        if index < 2:
            assert record["message"].startswith("已保存所选版本") and destination.read_bytes() == contents[index], (
                record
            )
        else:
            assert record["message"].startswith("引用已失效") and not destination.exists(), record
    route = f"/api/v1/issues/by-number/{issue['number']}"
    assert reads == [
        [route + suffix, scope, code]
        for suffix, code in [
            ("/detail", 200),
            ("/artifacts", 200),
            ("/artifacts/1", 200),
            ("/artifacts/2", 200),
            ("/artifacts/3", 409),
        ]
    ]
    with binary.open("rb") as stream:
        engine = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "engine_sha256": engine,
        "http_readback": reads,
        "native_selection": records,
        "saved_sha256": [
            hashlib.sha256((base / name).read_bytes()).hexdigest() for name in ("selected-2.bin", "selected-1.bin")
        ],
        "stale_destination_created": False,
        "logout_cleared_references": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i14-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I14 native revision selection and save")
