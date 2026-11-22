"""Verify four internal accounts on one project's native workbench and private issue."""

import argparse
import hashlib
import json
import secrets
import tempfile
from contextlib import closing
from pathlib import Path

from PIL import Image
from run_workbench_issue_detail import NativeStore, Tianxuan, run_probe


def exercise(base, binary):
    scope = "studio/icons"
    database = str(base / "tianxuan.db")
    store = Tianxuan(database)
    native = NativeStore(base / "duobao.db")
    password = secrets.token_urlsafe(32)
    project_roles = {"artist": "美术", "planner": "策划", "programmer": "程序", "excluded": "未授权成员"}
    with closing(store.db):
        account = store.register("Q02", "admin@example.invalid", secrets.token_urlsafe(32))
        admin = account["user_id"]
        actors = {
            role: store.add_member(admin, role + "@example.invalid", password, name=name, role="editor")["user_id"]
            for role, name in project_roles.items()
        }
        requirement = store.create_requirement(admin, "icons", "界面图标", "图标原件", "图标", "确认轮廓")["id"]
        store.set_visibility(admin, requirement, "private")
        for role in ("planner", "programmer", "artist"):
            store.share_doc(admin, requirement, actors[role], "write")
        issue = store.create_issue(actors["planner"], "核对图标原件", project=scope, requirement_id=requirement)
        source = base / "icon.png"
        Image.new("RGB", (8, 8), "coral").save(source)
        original = source.read_bytes()
        number, issue_id = issue["number"], issue["id"]
        issue_route = f"/api/v1/issues/{issue_id}"
        detail_route = f"/api/v1/issues/by-number/{number}/detail"
        upload_route = f"/api/v1/issues/by-number/{number}/artifacts"
        http = []

        def observe(request, response):
            path = request.url.path
            if path in (
                detail_route,
                upload_route,
                issue_route + "/work/submit_asset",
                issue_route + "/work/transfer",
                issue_route + "/work/decide",
                issue_route + "/work/approved-asset",
                issue_route + "/comments",
            ):
                token = request.headers.get("authorization", "").removeprefix("Bearer ")
                http.append(
                    dict(
                        actor=store.user_for_token(token),
                        method=request.method,
                        path=path,
                        project=request.query_params.get("project"),
                        status=response.status_code,
                    )
                )
            return response

        ui, _ = run_probe(
            base,
            binary,
            "workbench_cross_functional.gd",
            store,
            native,
            account["tenant_id"],
            "",
            scope,
            {
                "Q02_PASSWORD": password,
                "Q02_FIXTURE": json.dumps(dict(number=number, issue=issue_id, actors=actors, source=str(source))),
            },
            password,
            after_response=observe,
        )

    reopened = Tianxuan(database)
    with closing(reopened.db):
        work = reopened.dispatch_tool(actors["planner"], "work.read", {"issue_id": issue_id})
        comments = reopened.list_issue_comments(actors["planner"], issue_id)
    attached, submission, transfer, signature = work["history"]
    assert [row["action"] for row in work["history"]] == [
        "work.submit_asset",
        "work.submit_asset",
        "work.transfer",
        "work.decide",
    ]
    assert [row["version"] for row in work["history"]] == [1, 2, 3, 4]
    assert attached["decision"] == "attached" and attached["actor"] == actors["artist"]
    assert ui["submission"] == submission and submission["actor"] == actors["artist"]
    assert (
        submission["revision"] == ui["attachment"]["revision"]
        and submission["digest"] == hashlib.sha256(original).hexdigest()
    )
    assert (
        NativeStore(base / "duobao.db").read(
            account["tenant_id"], attached["module"], attached["revision"], attached["path"]
        )
        == original
    )
    assert all(event["initiator"] == actors["planner"] for event in [submission, transfer, signature])
    assert submission["responsible"] == transfer["actor"] == transfer["previous_responsible"] == actors["planner"]
    assert transfer["responsible"] == signature["actor"] == signature["responsible"] == actors["artist"]
    assert transfer["note"] == "请美术核对图标轮廓"
    assert f"{actors['planner']} → {actors['artist']}  {transfer['note']}" in ui["handoff"]
    assert signature["decision"] == "approved" and signature["note"] == "已核对图标轮廓，采纳此版本"
    assert all(value in ui["signature"] for value in (signature["actor"], signature["revision"], signature["note"]))
    assert transfer["submission_version"] == signature["submission_version"] == submission["version"]
    assert all(event["revision"] == submission["revision"] for event in work["history"])
    assert all(event["digest"] == ui["consumed"]["sha256"] for event in work["history"])
    assert comments == [ui["comment"]] and comments[0]["author"] == actors["programmer"]
    assert comments[0]["body"] == "程序已读取签认原件并核对像素"
    assert [identity["id"] for identity in ui["sessions"]] == [
        actors[role] for role in ("artist", "planner", "artist", "programmer", "excluded")
    ]
    assert all(identity["project"] == scope and identity["role"] == "editor" for identity in ui["sessions"])
    assert all(row["project"] == scope for row in http)
    assert {(row["actor"], row["status"]) for row in http if row["path"] == detail_route} == {
        (actor, 403 if role == "excluded" else 200) for role, actor in actors.items()
    }
    operations = [(row["actor"], row["path"], row["status"]) for row in http if row["method"] == "POST"]
    assert operations == [
        (actors["artist"], upload_route, 200),
        (actors["artist"], issue_route + "/work/submit_asset", 200),
        (actors["planner"], issue_route + "/work/transfer", 200),
        (actors["artist"], issue_route + "/work/decide", 200),
        (actors["programmer"], issue_route + "/comments", 200),
        (actors["excluded"], issue_route + "/comments", 403),
    ], operations
    assert any(
        row["actor"] == actors["programmer"]
        and row["path"] == issue_route + "/work/approved-asset"
        and row["status"] == 200
        for row in http
    )
    engine = binary.with_name(binary.name.replace(".console.exe", ".exe"))
    with engine.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        editor_sha256=digest,
        project=scope,
        requirement=requirement,
        issue_id=issue_id,
        issue_number=number,
        accounts=actors,
        ui=ui,
        http=http,
        reopened_history=work["history"],
        reopened_comments=comments,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-q02-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed four-account native workbench acceptance")
