"""Verify H02/H03 in three compiled Godot editor windows using two business accounts."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from run_workbench_issue_detail import NativeStore, Tianxuan, copy_editor, create_app, sanitized_environment
from run_workbench_offline_document import serve, wait_for_marker


def exercise(base, binary):
    database = str(base / "domain.db")
    domain = Tianxuan(database)
    native = NativeStore(base / "native.db")
    domain.work_native_store = native
    project = "studio/judgments"
    routes = []
    with closing(domain.db):
        account = domain.register("Review", "owner@example.invalid", secrets.token_urlsafe())
        owner, tenant = account["user_id"], account["tenant_id"]
        artist = domain.add_member(owner, "artist@example.invalid", secrets.token_urlsafe(), name="B")["user_id"]
        doc = domain.create_doc(owner, "Design", "Original silhouette")["id"]
        domain.design_signoff(owner, doc, 1, "Compare silhouette")
        module = domain.create_business_module(owner, project, "Character", call_id="create")
        (issue,) = domain.split_design(
            owner,
            doc,
            1,
            project,
            [dict(paragraph=1, module_id=module["id"], title="创意修订", acceptance="轮廓可辨认")],
            "split",
        )
        domain.add_issue_comment(owner, issue["id"], "保留剪影轮廓")
        other = domain.create_issue(artist, "B's separate item", project=project)
        revs = []
        for i, (creator, ticket) in enumerate([(owner, issue), (owner, issue), (artist, other)]):
            rev = native.submit(
                tenant,
                creator,
                f"publish-{i}",
                [dict(module="art", base=revs[-1] if revs else None, reads=None, edits={"hero.png": bytes([i])})],
            )["revisions"]["art"]
            revs.append(rev)
            domain.dispatch_tool(
                creator,
                "work.submit_asset",
                dict(
                    issue_id=ticket["id"],
                    expected_version=1 if i == 1 else 0,
                    kind="concept",
                    module="art",
                    path="hero.png",
                    revision=rev,
                ),
                call_id=f"asset-{i}",
            )
        auth = {
            "TIANXUAN_AUTH_MODE": "accounts",
            "TIANXUAN_TENANT_ID": tenant,
            "GONGGONG_WORKSPACE": "",
            "TIANXUAN_PUBLIC_ORIGIN": "https://fixture.invalid",
        }
        with patch.dict(os.environ, auth):
            app = create_app(domain, native_store=native, native_only=True)

            @app.middleware("http")
            async def observe(request, call_next):
                response = await call_next(request)
                if "/work/" in request.url.path or request.url.path.endswith("/issue-context"):
                    routes.append([request.method, request.url.path, response.status_code])
                return response

            with serve(app, 0) as port:
                ready, transferred = base / "old-open", base / "transferred"

                def window(mode, actor, token):
                    directory = base / mode
                    directory.mkdir()
                    engine = copy_editor(binary, directory / "engine")
                    folder = directory / "project"
                    folder.mkdir()
                    (folder / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Review"\n')
                    for script in ("workbench_issue_detail.gd", "workbench_creative_judgments.gd"):
                        shutil.copyfile(Path(__file__).with_name(script), folder / script)
                    env = sanitized_environment(directory) | dict(
                        TIANXUAN_API=f"http://127.0.0.1:{port}",
                        TIANXUAN_PROJECT=project,
                        TIANXUAN_TOKEN=token,
                        JUDGMENT_MODE=mode,
                        JUDGMENT_FIXTURE=json.dumps(
                            dict(
                                target=artist,
                                count=2,
                                index=0,
                                revision=revs[0],
                                ready=str(ready),
                                transferred=str(transferred),
                            )
                        ),
                    )
                    result = subprocess.run(
                        [
                            str(engine),
                            "--headless",
                            "--editor",
                            "--path",
                            str(folder),
                            "--script",
                            "res://workbench_creative_judgments.gd",
                        ],
                        cwd=directory,
                        env=env,
                        capture_output=True,
                        text=True,
                        errors="replace",
                        timeout=90,
                    )
                    output = result.stdout + result.stderr
                    if token in output:
                        raise AssertionError("Credential in editor output")
                    records = [
                        line.split("=", 1)[1] for line in output.splitlines() if line.startswith("WORKBENCH_REPORT=")
                    ]
                    if result.returncode or len(records) != 1 or "SCRIPT ERROR" in output:
                        raise AssertionError(output[-5000:])
                    report = json.loads(records[0])
                    assert report["actor"] == actor
                    return report

                with ThreadPoolExecutor(max_workers=1) as pool:
                    old = pool.submit(window, "stale", owner, domain.issue_session(owner))
                    wait_for_marker(ready, old)
                    sender = window("transfer", owner, domain.issue_session(owner))
                    transferred.touch()
                    stale = old.result()
                recipient = window("recipient", artist, domain.issue_session(artist))
        assert sender["list"] == stale["list"] == ["art @ " + rev for rev in revs[:2]]
        assert recipient["list"] == ["art @ " + revs[0], "art @ " + revs[2]]
        assert sender["after"] == sender["list"][1] and recipient["after"] == recipient["list"][1]
        assert all(
            record["item"]["revision"] == revs[0]
            and record["item"]["submission_version"] == 1
            and record["comment"] == "保留剪影轮廓"
            and record["design"]["document_id"] == doc
            and record["design"]["version"] == 1
            for record in [sender, stale, recipient]
        )
        assert "请检查旧修订轮廓" in recipient["handoff"]
        operations = [(path.split("/")[-1], code) for method, path, code in routes if method == "POST"]
        assert operations == [("transfer", 200), ("decide", 409), ("decide", 200)], operations
    saved = Tianxuan(database)
    with closing(saved.db):
        result = saved.dispatch_tool(artist, "work.read", {"issue_id": issue["id"]})
    assert [row["decision"] for row in result["creative_judgments"]] == ["approved", "pending"]
    assert result["history"][2]["previous_responsible"] == owner and result["history"][2]["responsible"] == artist
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        engine_sha256=digest, sender=sender, stale=stale, recipient=recipient, http=routes, history=result["history"]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="judgments-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native H02 / H03 handoff and personal revision lists")
