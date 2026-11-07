"""Read local execution evidence for rows already verified by the issue board."""
import json
from pathlib import Path
import re
import hashlib
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import issue_route
from daqian.repository_access import work_items


def receipt_root(root):
    path = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        text=True, timeout=15,
    ).strip()
    return Path(path).parent / "data-collection/receipts"


def read_object(path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def route_for_row(root, receipts, actor, row, item):
    key = item["request"]
    if not re.fullmatch(r"daqian-direct-[a-f0-9]{20}", key) or item["closed"]:
        return {}
    try:
        binding, _, _, status, _ = issue_route.source_from_row(
            work_items, {"repository": actor["repo"]}, item["number"], key, row)
        binding["actor"] = actor["user_id"]
        item["source_sha256"] = binding["source_sha256"]
        folder = receipts / "daqian-direct" / key
        if status == "planned":
            state = read_object(folder / ("route-" + issue_route.digest(binding) + ".json"))
            if state.get("binding") != binding:
                return {}
            for call in state.get("calls", {}).values():
                attempts = call.get("attempts", [])
                if attempts and "outcome" not in attempts[-1] and attempts[-1].get("agent") in ("sinan", "yanshi"):
                    item["judgment_attempt"] = {k: attempts[-1][k] for k in ("agent", "pid")}
            result = state.get("result", {})
            if state.get("candidates") != issue_route.registered_candidates(root, result["route"]):
                return {}
        else:
            state = read_object(folder / "start.json")
            result = state.get("result", {})
            binding["revision"] = state["binding"]["revision"]
        if result.get("route") not in ("sinan", "yanshi") or state.get("binding") != binding or not isinstance(result.get("ready"), bool):
            return {}
        fields = ("route", "reason", "scope", "acceptance", "questions")
        decision = {field: result[field] for field in fields}
        issue_route.decision(json.dumps(decision), result["route"], "")
        if result["ready"] != (not result["questions"]):
            return {}
        return {**decision, **{k: binding[k] for k in ("number", "request_id", "url", "revision")}, "ready": result["ready"],
                "clarification_history": state.get("answers" if status == "planned" else "clarifications", [])}
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return {}


def dispatch_revision(row):
    # Match issueSnapshot in issue-workorders/github_source.mjs (ordered JSON.stringify).
    def js_hash(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    body = row.get("body") or ""
    dependencies = sorted({int(n) for n in re.findall(r"<!--\s*gonggong-depends-on:#([1-9][0-9]*)\s*-->", body)})
    return js_hash(dict(number=row["number"], state=row["state"], updated_at=row["updated_at"],
                        body_sha256=js_hash(body), title=row["title"], labels=sorted(l["name"] for l in row["labels"]),
                        assignees=sorted(a["login"] for a in row["assignees"]), dependencies=dependencies))


def workers_for_row(receipts, repo, row, item):
    if not item["request"] or item["closed"]:
        return []
    ticket = f"github:{repo}#{item['number']}"
    prefix = issue_route.digest(ticket)
    folder = receipts / "codex-dispatch/sources"
    workers = []
    for path in sorted(folder.glob(prefix + "-*.worker.json")):
        key = path.name[len(prefix) + 1:].removesuffix(".worker.json")
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            continue
        stem = prefix + "-" + key
        if (folder / (stem + ".terminal.json")).exists():
            continue
        assignment = read_object(folder / (stem + ".claim.json")).get("assignment", {})
        packet = read_object(path)
        receipt = packet.get("receipt", {})
        source = assignment.get("sourceSnapshot", {})
        if (packet.get("key") == key == assignment.get("key") and assignment.get("ticket") == ticket
                and source.get("requestId") == item["request"] and source.get("authority") == item["url"]
                and source.get("sha256") == dispatch_revision(row)
                and receipt.get("setupPending") is False and isinstance(receipt.get("workerId"), str)
                and receipt["workerId"]):
            workers.append(receipt["workerId"])
    return workers
