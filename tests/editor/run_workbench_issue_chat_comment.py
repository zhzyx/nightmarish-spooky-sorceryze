"""Verify U11 consultations and one explicitly authorized I05 comment on two same-title design tasks."""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from functools import partial
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_issue_consultation import CHATS, PROJECT, exercise


def prepare(store, actor, project):
    doc = store.create_doc(actor, "桥梁验收", "桥面\n\n栏杆")["id"]
    store.design_signoff(actor, doc, 1, "逐段核对")
    issues = store.split_design(
        actor,
        doc,
        1,
        project,
        [
            dict(title="审核桥梁", paragraph=i, module_id="default", acceptance=name)
            for i, name in [(1, "桥面"), (2, "栏杆")]
        ],
        "i16-split",
    )
    for issue in issues:
        store.set_task_target(actor, issue["id"], project, doc, 1, 0, "工单评论", "由负责人发表咨询草稿")
    issue = issues[0]["id"]
    revision = store.issue_snapshot(actor, issue)["revision"]
    store.set_task_confirmation(actor, issue, project, doc, 1, 1, revision, 0, "confirmed")
    return [store.read_issue(actor, item["id"]) for item in issues]


def verify(engine, project, env, store, actor, issues, consultation, *, trace):
    def persisted():
        with closing(sqlite3.connect(project.parent / "domain.db")) as db:
            return [
                db.execute("SELECT id,author,body FROM issue_comments WHERE issue_id=?", (issue["id"],)).fetchall()
                for issue in issues
            ]

    assert issues[0]["title"] == issues[1]["title"] and issues[0]["number"] != issues[1]["number"]
    assert persisted() == [[], []]
    records = consultation["records"]
    statuses = {}
    with httpx.Client(
        base_url=env["TIANXUAN_API"],
        headers={"Authorization": "Bearer " + env["TIANXUAN_TOKEN"]},
        params={"project": PROJECT},
        trust_env=False,
    ) as client:

        def draft(index):
            chat = client.get(CHATS + "/" + records[index]["chat"]).raise_for_status().json()
            turn = chat["turns"][-1]
            assert turn["answer"] and "issue_comment" not in turn
            return dict(
                expected_version=chat["version"],
                issue=turn["context_snapshot"]["references"][0],
                body=turn["answer"],
                turn_id=turn["id"],
                target_revision=1,
                confirmation_revision=1,
            )

        paths = [CHATS + "/" + r["chat"] + "/issue-comment" for r in records]
        first, second = draft(0), draft(1)
        assert first["body"] != second["body"]
        mutations = {
            "other_issue": {"issue": second["issue"]},
            "different_body": {"body": first["body"] + "!"},
            "stale_view": {"expected_version": first["expected_version"] - 1},
            "old_confirmation": {"confirmation_revision": 2},
        }
        for name, change in mutations.items():
            statuses[name] = client.post(paths[0], json=first | change).status_code
        statuses["pending_sibling"] = client.post(paths[1], json=second).status_code
        statuses["other_chat"] = client.post(paths[1], json=first).status_code
        assert set(statuses.values()) == {409}, statuses
        peer = store.add_member(actor, "i16@example.invalid", "fixture-secret")["user_id"]
        statuses["other_actor"] = client.post(
            paths[0], headers={"Authorization": "Bearer " + store.issue_session(peer)}, json=first
        ).status_code
        assert statuses["other_actor"] == 404 and persisted() == [[], []]

        selected, sibling = issues
        sibling_before = store.read_issue_detail(actor, PROJECT, sibling["number"])
        selected_id = selected["id"]
        revision = first["issue"]["revision"]
        doc = sibling_before["design_source"]["document_id"]
        store.set_task_confirmation(actor, selected_id, PROJECT, doc, 1, 1, revision, 1, "revoked")
        statuses["revoked"] = client.post(paths[0], json=first).status_code
        store.set_task_target(actor, selected_id, PROJECT, doc, 1, 1, "交付", "提交交付")
        store.set_task_confirmation(actor, selected_id, PROJECT, doc, 1, 2, revision, 2, "confirmed")
        statuses["wrong_stage"] = client.post(
            paths[0], json=first | {"target_revision": 2, "confirmation_revision": 3}
        ).status_code
        store.set_task_target(actor, selected_id, PROJECT, doc, 1, 2, "工单评论", "由负责人发表咨询草稿")
        store.set_task_confirmation(actor, selected_id, PROJECT, doc, 1, 3, revision, 3, "confirmed")
        statuses["reconfirmed_since_preview"] = client.post(paths[0], json=first).status_code
        assert (statuses["revoked"], statuses["wrong_stage"], statuses["reconfirmed_since_preview"]) == (409, 403, 409)
        assert persisted() == [[], []]
        first |= {"target_revision": 3, "confirmation_revision": 4}
        first_detail = store.read_issue_detail(actor, PROJECT, selected["number"])
        shutil.copyfile(Path(__file__).with_name("workbench_issue_consultation.gd"), project / "issue_consultation.gd")
        shutil.copyfile(Path(__file__).with_name("workbench_issue_chat_comment.gd"), project / "i16.gd")
        start = len(trace)
        run = subprocess.run(
            [str(engine), "--headless", "--editor", "--path", str(project), "--script", "res://i16.gd"],
            cwd=project.parent,
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = run.stdout + run.stderr
        assert env["TIANXUAN_TOKEN"] not in output
        markers = [line.removeprefix("I16_NATIVE=") for line in output.splitlines() if line.startswith("I16_NATIVE=")]
        assert run.returncode == 0 and len(markers) == 1 and "SCRIPT ERROR" not in output, output[-7000:]
        native = json.loads(markers[0])
        native_posts = [call for call in trace[start:] if call[1].endswith("/issue-comment")]
        assert native_posts == [("POST", paths[0], 200)], native_posts
        row = native["selected_comment"]
        thread = [
            client.get(f"/api/v1/issues/{i['id']}/comments").raise_for_status().json()["comments"] for i in issues
        ]
        assert thread == [[row], []] and row["body"] == first["body"] == native["preview"]
        assert row["author"] == actor and row["issue_id"] == first["issue"]["object_id"]
        assert client.post(paths[0], json=first).raise_for_status().json()["comment"] == row
        assert persisted() == [[(row["id"], actor, row["body"])], []]
        assert store.read_issue_detail(actor, PROJECT, sibling["number"]) == sibling_before
        return {
            "unchanged_sibling": sibling_before["task_confirmation"],
            "title": issues[0]["title"],
            "consultation_counts": [0, 0],
            "drafts": [first, second],
            "denied": statuses,
            "confirmed_stage": first_detail["task_confirmation"],
            "native": native,
            "native_publications": native_posts,
            "http_threads": thread,
            "independent_sqlite": persisted(),
            "retry_comment": row["id"],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    with patch.dict(os.environ, {"GONGGONG_WORKSPACE": ""}), tempfile.TemporaryDirectory(prefix="i16-") as directory:
        trace: list[tuple[str, str, int]] = []
        result = exercise(
            Path(directory),
            args.godot.resolve(strict=True),
            partial(verify, trace=trace),
            prepare_issues=prepare,
            http_trace=trace,
        )
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Passed I16 native consultation, stage authorization and persisted comment readback")
