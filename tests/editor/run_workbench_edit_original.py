"""Edit an SVG concept through Godot's native text editor and reread both immutable originals."""

import argparse
import hashlib
import json
import secrets
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from xml.etree import ElementTree

from run_workbench_issue_detail import NativeStore, Tianxuan, run_probe
from work_management import my_judgments, read_issue_artifact


def exercise(base, engine):
    store = Tianxuan(str(base / "issue.db"))
    native = NativeStore(base / "native.db")
    store.work_native_store = native
    original = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="4" fill="#ff0000"/></svg>\n'
    with closing(store.db):
        password = secrets.token_urlsafe()
        account = store.register("Art", "review@example.invalid", password)
        owner, tenant = account["user_id"], account["tenant_id"]
        project = "studio/original"
        issue = store.create_issue(owner, "确认徽章颜色", project=project)
        path, module = "badge.svg", "studio-art"
        rev = native.submit(
            tenant, owner, "initial", [dict(module=module, base=None, reads=None, edits={path: original})]
        )["revisions"][module]
        store.dispatch_tool(
            owner,
            "work.submit_asset",
            dict(issue_id=issue["id"], expected_version=0, kind="concept", module=module, revision=rev, path=path),
            call_id="initial",
        )
        report, _ = run_probe(
            base,
            engine,
            "workbench_edit_original.gd",
            store,
            native,
            tenant,
            store.issue_session(owner),
            project,
            {},
            password,
            graphical=True,
        )
    persisted = Tianxuan(str(base / "issue.db"))
    persisted.work_native_store = native
    with closing(persisted.db):
        (item,) = my_judgments(persisted, owner, project)["items"]
        if sys.platform == "darwin":
            assert report["display_server"] == "macOS"
        assert report["before"]["revision"] == rev and report["after"] == item
        assert item["revision"] != rev and item["path"] == path and item["module"] == module
        old, new = [
            read_issue_artifact(persisted, owner, project, issue["number"], version)
            for version in (1, item["submission_version"])
        ]
        assert old == original and new == report["saved_source"].encode()
        assert ElementTree.fromstring(old)[0].get("fill") == "#ff0000"
        assert ElementTree.fromstring(new)[0].get("fill") == "#0000ff"
        assert native.read(tenant, module, item["revision"], path) == new
        with engine.open("rb") as binary:
            engine_sha = hashlib.file_digest(binary, "sha256").hexdigest()
        return {
            **report,
            "original_sha256": hashlib.sha256(old).hexdigest(),
            "edited_sha256": hashlib.sha256(new).hexdigest(),
            "engine_sha256": engine_sha,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="judgment-edit-") as directory:
        result = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Passed original SVG, native editor save, pending judgment return and persisted revision readback")
