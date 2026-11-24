"""Read the signed bridge design through its module roadmap, child issue and document history."""

import argparse
import difflib
import hashlib
import json
import secrets
import tempfile
from contextlib import closing
from pathlib import Path

from run_workbench_issue_detail import NativeStore, Tianxuan, run_probe

PROJECT = "studio/bridge"
ORIGINAL = "Program the lever.\nHandle repeated pulls.\n\nAnimate the bridge opening."
UPDATED = ORIGINAL.replace("opening.", "closing.")
TASKS = [
    dict(paragraph=1, title="操作拉杆", acceptance="拉杆触发一次开桥事件"),
    dict(paragraph=2, title="桥面展开", acceptance="桥面动画播放至展开状态"),
]


def exercise(base, binary):
    password = secrets.token_urlsafe(32)
    database = str(base / "domain.db")
    store = Tianxuan(database)
    with closing(store.db):
        account = store.register("Q13", "designer@example.invalid", password)
        owner = account["user_id"]
        module = store.create_business_module(owner, PROJECT, "桥梁", call_id="bridge")
        doc_id = store.create_doc(owner, "Bridge", ORIGINAL)["id"]
        signoff = store.design_signoff(owner, doc_id, 1, "拉杆触发开桥，桥面完成展开")
        parent = store.create_issue(owner, "桥梁交付", project=PROJECT, module_id=module["id"])
        items = [dict(**item, module_id=module["id"]) for item in TASKS]
        upstream, child = store.split_design(owner, doc_id, 1, PROJECT, items, "split-bridge")
        for issue in (upstream, child):
            store.set_issue_parent(owner, issue["id"], PROJECT, parent["number"], None)
        store.set_issue_assignee(owner, child["id"], PROJECT, owner, None)
        store.dispatch_tool(
            owner,
            "flow.dependencies",
            {"issue_id": child["id"], "expected_version": 0, "dependencies": [upstream["id"]]},
            call_id="link-lever",
        )
        comment = store.add_issue_comment(owner, child["id"], "按已签认的第 2 段验收桥面展开。")
        store.update_doc(owner, doc_id, UPDATED, expected_version=1)
        path = [module["name"], "未设置里程碑（项目共 3 单）"]
        path.extend(f"#{issue['number']} · {issue['title']}" for issue in (parent, child))
        fixture = dict(path=path, parent=parent, child=child)
        routes = []

        def observe(request, response):
            if request.url.path.startswith(("/api/v1/issues/", "/api/v1/docs/", "/api/v1/work/roadmap")):
                routes.append((request.method, request.url.path, response.status_code))
            return response

        trace, _ = run_probe(
            base,
            binary,
            "workbench_issue_design_trace.gd",
            store,
            NativeStore(base / "native.db"),
            account["tenant_id"],
            store.issue_session(owner),
            PROJECT,
            {"Q13_FIXTURE": json.dumps(fixture)},
            password,
            after_response=observe,
        )

    saved = Tianxuan(database)
    with closing(saved.db):
        actual = saved.read_issue_detail(owner, PROJECT, child["number"])
        assert trace["detail"] == actual
        assert trace["fields"] == (
            f"标题　{actual['title']}\n负责人　{actual['assignee']['name']}\n状态　{actual['status']}"
            f"\n内容版本　{actual['revision']}\n拆单验收　{TASKS[1]['acceptance']}"
        )
        assert actual["assignee"]["id"] == owner and actual["module_id"] == module["id"]
        source = child["design_source"]
        assert actual["design_source"] == source and source == dict(
            project=PROJECT,
            document_id=doc_id,
            version=1,
            module_id=module["id"],
            paragraph=2,
            acceptance=TASKS[1]["acceptance"],
        )
        assert trace["parent_id"] == parent["id"]
        hierarchy = saved.issue_hierarchy(owner, parent["id"], PROJECT)
        assert {c["id"] for c in hierarchy["children"]} == {upstream["id"], child["id"]}
        for c in hierarchy["children"]:
            assert f"#{c['number']} {c['title']}" in trace["parent_hierarchy"]
        assert trace["child_hierarchy"] == f"父工单　#{parent['number']} {parent['title']}\n子工单　无"
        assert saved.issue_hierarchy(owner, child["id"], PROJECT)["parent"]["id"] == parent["id"]
        (dep,) = saved.dispatch_tool(owner, "flow.read", {"issue_id": child["id"]})["dependencies"]
        assert dep["id"] == upstream["id"] and dep["accepted"] is False
        assert trace["dependency"] == dict(id=dep["id"], label=f"{dep['title']}　{dep['status']}　未验收，阻塞推进")
        assert trace["comment"] == comment and saved.list_issue_comments(owner, child["id"]) == [comment]
        assert trace["comment_body"] == comment["body"]
        assert trace["reference"] == dict(document_id=doc_id, version=1, paragraph=2)
        assert trace["body"] == saved.version(doc_id, 1)["body_md"] == ORIGINAL
        assert saved.get_doc(doc_id)["body_md"] == UPDATED
        assert saved.design_signoff(owner, doc_id, 1) == signoff and not saved.design_signoff(owner, doc_id, 2)
        delta = "\n".join(
            difflib.unified_diff(ORIGINAL.splitlines(), UPDATED.splitlines(), fromfile="v1", tofile="v2", lineterm="")
        )
        assert trace["history"] == {"document_id": doc_id, "from": 1, "to": 2, "diff": delta}

    relevant = [
        "/api/v1/work/roadmap",
        f"/api/v1/issues/by-number/{parent['number']}/detail",
        f"/api/v1/issues/{parent['id']}/hierarchy",
        f"/api/v1/issues/by-number/{child['number']}/detail",
        f"/api/v1/issues/{child['id']}/hierarchy",
        f"/api/v1/issues/{child['id']}/work/flow",
        f"/api/v1/issues/{child['id']}/comments",
        f"/api/v1/docs/{doc_id}/versions/1",
        f"/api/v1/docs/{doc_id}/versions",
        f"/api/v1/docs/{doc_id}/diff",
    ]
    assert all(("GET", route, 200) in routes for route in relevant)
    assert all(method == "GET" for method, _, _ in routes)
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        state="passed",
        editor_sha256=digest,
        module_path=path,
        signed_version=signoff,
        native=trace,
        relevant_http=[r for r in routes if r[1] in relevant],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="q13-design-") as directory:
        report = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
