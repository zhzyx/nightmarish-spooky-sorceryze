"""Select a single changed paragraph in native document history and persist its edit."""

import argparse
import hashlib
import json
import secrets
import tempfile
from contextlib import closing
from pathlib import Path

from run_workbench_issue_detail import NativeStore, Tianxuan, run_probe


def exercise(base, binary):
    db = str(base / "docs.db")
    store = Tianxuan(db)
    secret = secrets.token_urlsafe(24)
    before = "海岸\n\n白色灯塔\n保留灯光\n\n结尾"
    after = before.replace("白色", "蓝色")
    expected = after.replace("蓝色灯塔\n保留灯光", "海岸灯塔\n调高灯光")
    with closing(store.db):
        account = store.register("V02", "designer@example.invalid", secret)
        actor = account["user_id"]
        doc = store.create_doc(actor, "灯塔设计", before)["id"]
        store.update_doc(actor, doc, after, expected_version=1)
        requests = []

        def observe(request, response):
            if request.url.path.startswith("/api/v1/docs/" + doc):
                requests.append([request.method, request.url.path, str(request.url.query), response.status_code])
            return response

        report, _ = run_probe(
            base,
            binary,
            "workbench_changed_paragraph.gd",
            store,
            NativeStore(base / "native.db"),
            account["tenant_id"],
            store.issue_session(actor),
            "studio/game",
            {"V02_DOC": doc},
            secret,
            after_response=observe,
        )

    persisted = Tianxuan(db)
    with closing(persisted.db):
        assert [persisted.version(doc, version)["body_md"] for version in (1, 2, 3)] == [before, after, expected]
    assert report["reference"] == {"document_id": doc, "version": 2, "paragraph": 2}
    assert report["saved"] == expected and report["highlighted"]
    assert [row for row in requests if row[0] == "PATCH"] == [
        ["PATCH", "/api/v1/docs/" + doc, "project=studio%2Fgame", 200]
    ]
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(editor_sha256=digest, native=report, http=requests, persisted=[before, after, expected])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="v02-doc-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("Passed native highlight, editable selection and persisted single-paragraph revision")
