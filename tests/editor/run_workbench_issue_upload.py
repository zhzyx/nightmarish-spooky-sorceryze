"""Exercise local file selection, replay and byte-for-byte save in the compiled I18 workbench."""

import argparse
import hashlib
import json
import secrets
import tempfile
from pathlib import Path

from fastapi.responses import Response
from fastapi.testclient import TestClient
from run_workbench_issue_detail import NativeStore, Tianxuan, create_app, run_probe
from work_management import list_issue_artifacts


def exercise(base, binary):
    database = str(base / "domain.db")
    store = Tianxuan(database)
    native = NativeStore(base / "native.db")
    password = secrets.token_urlsafe(32)
    account = store.register("I18", "owner@example.invalid", password)
    actor = account["user_id"]
    token = store.issue_session(actor)
    scope = "studio/game"
    issue = store.create_issue(actor, "附件上传", project=scope)
    other = store.create_issue(actor, "隔离项目", project="other")
    route = f"/api/v1/issues/by-number/{issue['number']}/artifacts"
    name = "角色.bin"
    contents = (bytes(range(256)) + b"first\0", b"second\0\xff")
    for directory, content in zip(("first", "second"), contents, strict=True):
        (base / directory).mkdir()
        (base / directory / name).write_bytes(content)
    after_commit = []

    def observe_upload(request, response):
        if request.method == "POST" and request.url.path == route and response.status_code == 200:
            persisted = Tianxuan(database)
            try:
                refs = list_issue_artifacts(persisted, actor, scope, issue["number"])
                after_commit.append([ref["version"] for ref in refs])
            finally:
                persisted.db.close()
            if len(after_commit) == 1:
                # Simulate the transport losing the success receipt after both stores committed.
                return Response(status_code=503)
        return response

    try:
        observed, reads = run_probe(
            base,
            binary,
            "workbench_issue_upload.gd",
            store,
            native,
            account["tenant_id"],
            token,
            scope,
            {"I18_NUMBER": str(issue["number"]), "I18_BASE": str(base)},
            password,
            after_response=observe_upload,
        )
    finally:
        store.db.close()

    assert after_commit == [[1], [1], [1], [2, 1], [2, 1]], after_commit
    assert [row["version"] for row in observed["selections"]] == [1, 1, 2, 1], observed
    assert [row["version"] for row in observed["downloads"]] == [2, 1], observed
    assert [route, scope, 503] in reads and all(item[1] == scope for item in reads), reads
    domain = Tianxuan(database)
    reopened = NativeStore(native.database)
    saved_digests = []
    try:
        refs = list_issue_artifacts(domain, actor, scope, issue["number"])
        assert [r["version"] for r in refs] == [2, 1] and refs[0]["revision"] != refs[1]["revision"]
        assert observed["selections"] == [refs[1], refs[1], refs[0], refs[1]]
        for ref, expected in zip(reversed(refs), contents, strict=True):
            local = (base / f"saved-{ref['version']}.bin").read_bytes()
            assert local == reopened.read(account["tenant_id"], ref["module"], ref["revision"], name) == expected
            digest = hashlib.sha256(local).hexdigest()
            assert ref["digest"] == digest and ref["path"] == name and ref["kind"] == "attachment"
            saved_digests.append(digest)
        with reopened._connection() as db:
            revisions = db.execute("SELECT count(*) FROM native_revisions").fetchone()[0]
        assert revisions == 2
        with TestClient(create_app(domain, native_store=reopened, native_only=True)) as client:
            options = {"headers": {"Authorization": "Bearer " + token}, "params": {"project": "other"}}
            wrong_project = {
                "list": client.get(route, **options).status_code,
                "download": client.get(route + "/1", **options).status_code,
                "upload": client.post(route, json={"name": name, "content": ""}, **options).status_code,
            }
            assert wrong_project == {"list": 404, "download": 404, "upload": 404}, wrong_project
            assert list_issue_artifacts(domain, actor, "other", other["number"]) == []
    finally:
        domain.db.close()
    with binary.open("rb") as stream:
        engine_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "engine_sha256": engine_digest,
        "native_controls": observed,
        "http": reads,
        "storage_versions_after_each_post": after_commit,
        "native_revision_count": revisions,
        "saved_sha256": saved_digests,
        "wrong_project_http": wrong_project,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-i18-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I18 native chooser, replay and versioned download")
