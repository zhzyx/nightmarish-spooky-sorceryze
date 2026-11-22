"""Sign and split one design, then reopen its sources and consultations on the same issue numbers."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from run_workbench_design_tasks import run_editor
from run_workbench_issue_consultation import ROOT, Tianxuan, exercise
from run_workbench_issue_design_trace import ORIGINAL, TASKS
from tianshu_bridge import historical_issue

sys.path.insert(0, str(ROOT / "customizations/components/tianxuan/migration"))

# isort: split
from importer import canonical, digest, import_inventory  # noqa: E402
from migration_status import publish_import  # noqa: E402

REPO = "zhzyx/nightmarish-spooky-sorceryze"
Q13 = "data-collection/gonggong-ai-workbench-plan1-q13.json"
SOURCE_FILES = (
    "tests/editor/run_workbench_design_milestone.py",
    "tests/editor/run_workbench_design_tasks.py",
    "tests/editor/workbench_design_tasks.gd",
    "tests/editor/run_workbench_issue_consultation.py",
    "tests/editor/workbench_issue_consultation.gd",
    "design-docs/gonggong-ai-workbench-k02.md",
)


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, encoding="utf-8").strip()


def original_issue():
    fields = "number,title,state,stateReason,body,url,updatedAt"
    result = json.loads(command("gh", "issue", "view", "1723", "--repo", REPO, "--json", fields))
    assert result["stateReason"] == "COMPLETED"
    return result


def archive_issue(root, tenant, actor, project, issue):
    source_id = f"github:{REPO}/issue/{issue['number']}"
    record = dict(kind="issue", source_id=source_id, mode="record_only", relations=[], content=issue)
    data = canonical(dict(**record, sha256=digest(canonical(issue)))) + b"\n"
    (root / "records.jsonl").write_bytes(data)
    manifest = root / "manifest.json"
    manifest.write_bytes(
        canonical(
            dict(
                source=REPO,
                revision=issue["updatedAt"],
                counts={"issue": 1},
                records_sha256=digest(data),
                historical_policy="record_only",
            )
        )
    )
    db = root / "native.db"
    receipt = import_inventory(manifest, db, tenant, actor)
    publish_import(db, tenant, project, actor, receipt["module"], receipt["revision"])
    return source_id


def milestone(root, binary):
    original = original_issue()
    body = ORIGINAL + "\n旧单来源 " + original["url"]
    calls = []
    sample = {}

    def split(store, actor, project, origin, token):
        source_id = archive_issue(root, store.actor_context(actor)["tenant"], actor, project, original)
        args = argparse.Namespace(api=origin, token=token, actor=None, project=project, source_id=original["url"])
        before = historical_issue(args)
        assert before["source_id"] == source_id and before["body"] == original["body"]
        assert before["title"] == original["title"] and before["state"] == original["state"]
        assert not store.list_issues(actor)
        module = store.create_business_module(actor, project, "桥梁", call_id="module-bridge")
        doc = store.create_doc(actor, "桥梁设计", body)
        items = [dict(**task, module_id=module["id"]) for task in TASKS]
        phase = root / "design"
        phase.mkdir()
        first = len(calls)
        criteria = "拉杆触发开桥，桥面完成展开"
        ui = run_editor(phase, binary, origin, token, items, project_scope=project, signoff=criteria, retry=False)
        doc_id = doc["id"]
        route = f"/api/v1/docs/{doc_id}/versions/1"
        writes = [row for row in calls[first:] if row[0] == "POST"]
        assert writes == [("POST", route + "/signoff", 200), ("POST", route + "/tasks", 200)], writes
        signoff = store.design_signoff(actor, doc_id, 1)
        assert signoff["acceptance"] == criteria and signoff["document_id"] == doc_id and signoff["version"] == 1
        assert not store.design_signoff(actor, doc_id, 2) and not store.design_tasks(actor, doc_id, 2, project)
        assert store.get_doc(doc_id)["version"] == 2 and store.get_doc(doc_id)["body_md"] != body
        links = store.design_tasks(actor, doc_id, 1, project)
        issues = []
        for opened, link, task in zip(ui["opened"], links, items, strict=True):
            expected = dict(document_id=doc_id, version=1, paragraph=task["paragraph"])
            assert opened == dict(number=link["number"], reference=expected, body=body)
            assert ("GET", f"/api/v1/issues/by-number/{link['number']}/detail", 200) in calls[first:]
            assert original["url"] in opened["body"].split("\n\n")[1]
            detail = store.read_issue_detail(actor, project, link["number"])
            assert detail["id"] == link["id"] and detail["title"] == task["title"]
            assert detail["design_source"] == dict(
                **expected, module_id=module["id"], project=project, acceptance=task["acceptance"]
            )
            issues.append(detail)
        assert len({i["number"] for i in issues}) == len({i["id"] for i in issues}) == 2
        assert original["number"] not in {i["number"] for i in issues}
        sample.update(signed=signoff, tasks=links, opened=ui["opened"], head=2, writes=writes, archive_before=before)
        return issues

    def check_archive(engine, project_dir, env, store, actor, issues, native):
        source = historical_issue(
            argparse.Namespace(
                api=env["TIANXUAN_API"],
                token=env["TIANXUAN_TOKEN"],
                actor=None,
                project=env["TIANXUAN_PROJECT"],
                source_id=original["url"],
            )
        )
        assert source == sample.pop("archive_before")
        assert {i["id"] for i in store.list_issues(actor)} == {i["id"] for i in issues}
        reread = original_issue()
        assert reread == original
        sample["source"] = dict(
            url=original["url"],
            source_id=source["source_id"],
            state=source["state"],
            title=source["title"],
            updated_at=original["updatedAt"],
            body_sha256=digest(source["body"].encode()),
            archive_revision=source["revision"],
            original_sha256_before_after=[digest(canonical(original)), digest(canonical(reread))],
        )
        return {"original_reread": True}

    result = exercise(root, binary, check_archive, prepare_native_issues=split, http_trace=calls)
    assert result["native"]["reopened_first"] and result["stored_executions"] == 0
    for task, record, saved in zip(sample["tasks"], result["native"]["records"], result["turns"], strict=True):
        assert record["issue"] == task["id"] and record["chat"] == saved["conversation"]
        assert record["turn"] == saved["turn"]["id"] and saved["turn"]["state"] == "answered"
        assert saved["turn"]["context_snapshot"]["issue_id"] == task["id"]
    reopened = Tianxuan(str(root / "domain.db"))
    with closing(reopened.db):
        actor = result["native"]["identity"]["id"]
        doc_id = sample["signed"]["document_id"]
        assert reopened.design_signoff(actor, doc_id, 1) == sample["signed"]
        assert reopened.design_tasks(actor, doc_id, 1, result["native"]["identity"]["project"]) == sample["tasks"]
    sample["consultation"] = dict(
        records=result["native"]["records"],
        reopened_first=result["native"]["reopened_first"],
        answered=[
            {"turn": t["turn"]["id"], "state": t["turn"]["state"], "context_snapshot": t["turn"]["context_snapshot"]}
            for t in result["turns"]
        ],
        stored_executions=result["stored_executions"],
        stale_status=result["stale_status"],
        model_transport=result["model_transport"],
    )
    return sample


def receipts(main):
    q13 = json.loads((ROOT / Q13).read_bytes())
    rows = q13["issue_capabilities"]
    assert [r["capability"] for r in rows] == [f"I{i:02}" for i in range(1, 19)]
    inventory = q13["inventory"]
    history = subprocess.check_output(["git", "show", inventory["received_at"] + ":" + inventory["path"]], cwd=ROOT)
    assert command("git", "rev-parse", inventory["received_at"] + ":" + inventory["path"]) == inventory["blob"]
    archived = json.loads(history)
    assert archived["baseline"] == inventory["snapshot_main"]
    for previous, current in zip(archived["capabilities"], rows, strict=True):
        assert previous == dict(
            capability=current["capability"],
            issue=current["issue"],
            state=current["mac_state"],
            evidence=current["mac_evidence"],
        )
    fields = "state stateReason url comments(last:100){nodes{url body}}"
    prereqs = dict(K01=1717, Q13=1723, U10=1760, U14=1761)
    numbers = [r["issue"] for r in rows] + list(prereqs.values())
    select = " ".join(f"n{i}:issue(number:{i}){{{fields}}}" for i in numbers)
    query = 'query{repository(owner:"zhzyx",name:"nightmarish-spooky-sorceryze"){' + select + "}}"
    states = json.loads(command("gh", "api", "graphql", "-f", "query=" + query))["data"]["repository"]
    for n in numbers:
        state = states[f"n{n}"]
        assert (state["state"], state["stateReason"]) == ("CLOSED", "COMPLETED")
    for row in rows:
        remote = states[f"n{row['issue']}"]
        if row["completion_receipt"] not in {x["url"] for x in remote["comments"]["nodes"]}:
            comment_id = row["completion_receipt"].split("#issuecomment-")[1]
            exact = json.loads(command("gh", "api", f"repos/{REPO}/issues/comments/{comment_id}"))
            assert exact["html_url"] == row["completion_receipt"] and exact["issue_url"].endswith(f"/{row['issue']}")
        command("git", "merge-base", "--is-ancestor", row["accepted_main"], main)
        assert (
            command("git", "rev-parse", row["accepted_main"] + ":" + row["candidate_receipt"]) == row["candidate_blob"]
        )
    dependencies = {}
    for card, number in prereqs.items():
        remote = states[f"n{number}"]
        receipt = next(
            c for c in remote["comments"]["nodes"] if f"已逐项验收 {card}" in c["body"] and "主线接收修订" in c["body"]
        )
        revision = re.search(r"主线接收修订 `([0-9a-f]{40})`", receipt["body"])[1]
        command("git", "merge-base", "--is-ancestor", revision, main)
        dependencies[card] = dict(
            issue=number, url=receipt["url"], state_reason=remote["stateReason"], accepted_main=revision
        )
    return dict(
        q13=Q13, historical_inventory=inventory, issue_capabilities=rows, accepted_main=main, prerequisites=dependencies
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary = args.godot.resolve(strict=True)
    base = command("git", "rev-parse", "HEAD")
    target = command("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    accepted = receipts(target)
    with patch.dict(os.environ, GONGGONG_WORKSPACE=""), tempfile.TemporaryDirectory(prefix="k02-design-") as temp:
        native = milestone(Path(temp), binary)
    with binary.open("rb") as stream:
        editor = hashlib.file_digest(stream, "sha256").hexdigest()
    report = dict(
        schema_version=1,
        request_id="gonggong-ai-workbench-plan1-k02",
        issue_number=1716,
        issue_url=f"https://github.com/{REPO}/issues/1716",
        verified_at=datetime.now(timezone.utc).isoformat(),
        state="passed",
        source_base=base,
        editor_sha256=editor,
        source_git_blob={p: command("git", "hash-object", "--", p) for p in SOURCE_FILES},
        native_sample=native,
        **accepted,
    )
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Passed native signed design, issue, historical source, consultation and 18 main receipts")


if __name__ == "__main__":
    main()
