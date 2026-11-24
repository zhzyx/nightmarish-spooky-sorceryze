"""Verify handoff, comparison and version-bound creative decisions in compiled editor sessions."""

import argparse
import hashlib
import io
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

import httpx
from PIL import Image
from run_workbench_issue_detail import NativeStore, Tianxuan, copy_editor, create_app, sanitized_environment
from run_workbench_offline_document import serve, wait_for_marker


def exercise(base, binary):
    database = str(base / "domain.db")
    domain = Tianxuan(database)
    native = NativeStore(base / "native.db")
    domain.work_native_store = native
    project = "studio/judgments"
    routes = []
    signed_requests = []
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
        digests = []
        for i, (creator, ticket) in enumerate([(owner, issue), (owner, issue), (artist, other)]):
            buffer = io.BytesIO()
            Image.new("RGB", (8, 8), [(255, 0, 0), (0, 0, 255), (0, 255, 0)][i]).save(buffer, format="PNG")
            content = buffer.getvalue()
            digests.append(hashlib.sha256(content).hexdigest())
            rev = native.submit(
                tenant,
                creator,
                f"publish-{i}",
                [dict(module="art", base=revs[-1] if revs else None, reads=None, edits={"hero.png": content})],
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
                signed = await request.json() if request.url.path.endswith("/work/decide") else None
                response = await call_next(request)
                if signed and response.status_code == 200:
                    signed_requests.append(signed)
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
                        JUDGMENT_EXPORT=str(directory),
                        JUDGMENT_FIXTURE=json.dumps(
                            dict(
                                target=artist,
                                revisions=revs[:2],
                                digests=digests[:2],
                                count=1 if mode == "return" else 2,
                                index=0,
                                revision=revs[1] if mode == "return" else revs[0],
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
                        encoding="utf-8",
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
                    return {**report, "editor_exit": result.returncode}

                with ThreadPoolExecutor(max_workers=1) as pool:
                    old = pool.submit(window, "stale", owner, domain.issue_session(owner))
                    wait_for_marker(ready, old)
                    sender = window("transfer", owner, domain.issue_session(owner))
                    transferred.touch()
                    stale = old.result()
                recipient = window("recipient", artist, domain.issue_session(artist))
                returned = window("return", owner, domain.issue_session(owner))
                approved_request, returned_request = signed_requests
                assert approved_request["submission_version"] == 1 and returned_request["submission_version"] == 2
                assert returned["receipt"].startswith("提交 v2 已退回") and owner in returned["receipt"]
                assert recipient["receipt"].startswith("提交 v1 已采纳") and artist in recipient["receipt"]
                assert owner in recipient["other"] and artist in returned["other"] and revs[0] in returned["other"]
                actor_headers = {"Authorization": "Bearer " + domain.issue_session(artist)}
                owner_headers = {"Authorization": "Bearer " + domain.issue_session(owner)}
                url = f"/api/v1/issues/{issue['id']}/work"
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", params={"project": project}) as http:
                    # C is generated after A was signed and B was returned.
                    new_revision = native.submit(
                        tenant,
                        owner,
                        "after-signature",
                        [dict(module="art", base=revs[-1], reads=None, edits={"hero.png": b"new draft"})],
                    )["revisions"]["art"]
                    binding = dict(kind="concept", module="art", path="hero.png", revision=new_revision)
                    latest = (
                        http
                        .post(
                            url + "/submit_asset",
                            headers=owner_headers,
                            json={
                                **binding,
                                "expected_version": 5,
                                "call_id": "new-candidate",
                            },
                        )
                        .raise_for_status()
                        .json()
                    )
                    repeated = http.post(url + "/decide", headers=actor_headers, json=approved_request)
                    repeated.raise_for_status()
                    replay = repeated.json()
                    assert replay["version"] == 4 and replay["history"][-1]["revision"] == revs[0]
                    assert [item["decision"] for item in replay["creative_judgments"]] == ["approved", "pending"]
                    new_decision = dict(**binding, decision="approved", expected_version=6, submission_version=6)
                    altered = http.post(
                        url + "/decide",
                        headers=actor_headers,
                        json={
                            **new_decision,
                            "call_id": approved_request["call_id"],
                        },
                    )
                    wrong_actor = http.post(
                        url + "/decide",
                        headers=actor_headers,
                        json={
                            **new_decision,
                            "call_id": "wrong-responsible",
                        },
                    )
                    ai = http.post(
                        "/api/v1/tools",
                        headers=owner_headers,
                        json={
                            "name": "work.decide",
                            "payload": dict(new_decision, issue_id=issue["id"]),
                            "call_id": "ai",
                        },
                    )
                    unsigned = http.get(url + "/approved-asset", headers=owner_headers, params=binding)
                    assert (altered.status_code, wrong_actor.status_code, ai.status_code, unsigned.status_code) == (
                        409,
                        403,
                        400,
                        409,
                    )
                    assert ai.json()["detail"] == "unknown tool"
                    assert http.get(url, headers=owner_headers).raise_for_status().json() == latest
                    checks = dict(
                        replay_version=replay["version"],
                        judgments_after_first_signature=[item["decision"] for item in replay["creative_judgments"]],
                        repeat_same_call_status=repeated.status_code,
                        repeat_changed_target_status=altered.status_code,
                        wrong_responsible_status=wrong_actor.status_code,
                        ai_tool_status=ai.status_code,
                        ai_tool_result=ai.json(),
                        new_unsigned_status=unsigned.status_code,
                    )

        assert [card["color"] for card in sender["comparison"]] == ["ff0000", "0000ff"]
        for index, card in enumerate(sender["comparison"]):
            assert revs[index] in card["field"] and digests[index] in card["field"]
            assert "hero.png" in card["original"] and doc in card["design"]
        assert revs[1] in sender["switched"] and "v2" in sender["switched"]
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
        assert operations == [
            ("transfer", 200),
            ("decide", 409),
            ("decide", 200),
            ("decide", 200),
            ("submit_asset", 200),
            ("decide", 200),
            ("decide", 409),
            ("decide", 403),
        ], operations
    saved = Tianxuan(database)
    with closing(saved.db):
        result = saved.dispatch_tool(artist, "work.read", {"issue_id": issue["id"]})
    assert [row["decision"] for row in result["creative_judgments"]] == ["approved", "changes_requested", "pending"]
    assert result["history"][2]["previous_responsible"] == owner and result["history"][2]["responsible"] == artist
    assert (
        result["creative_judgments"][0]["note"] == "采纳原始轮廓"
        and result["creative_judgments"][1]["note"] == "请调整对比度"
    )
    assert [item["revision"] for item in result["creative_judgments"]] == [*revs[:2], new_revision]
    # On Windows the console executable is a launcher for the sibling GUI engine.
    engine = binary.with_name(binary.name.replace(".console.exe", ".exe"))
    with engine.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        engine_sha256=digest,
        sender=sender,
        stale=stale,
        recipient=recipient,
        returned=returned,
        checks=checks,
        http=routes,
        history=result["history"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="judgments-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed native H02–H05 handoff, comparison and version-bound signatures")
