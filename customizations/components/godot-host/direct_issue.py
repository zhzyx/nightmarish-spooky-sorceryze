"""A user-confirmed Daqian draft creates one GitHub Issue and signals Sinan."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tempfile

from daqian.repository_access import collaborator


def save(path, value):
    # The per-draft lock owns this temporary file, including after a process crash.
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def check_text(request):
    text = request["title"] + "\n" + request["outcome"]
    if re.search(
        r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_\w+)"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])"
        r"|<!--\s*(?:gonggong|olympus)-|^### 稳定需求 ID\s*$|[\x00-\x08\x0b\x0c\x0e-\x1f]",
        text, re.IGNORECASE | re.MULTILINE,
    ):
        raise ValueError("请先移除凭据、私人路径或宿主保留的工单标记")


def existing(work, repository, request_id):
    pages = json.loads(work.gh("api", f"repos/{repository}/issues?state=all&per_page=100", "--paginate", "--slurp"))
    matches = [row for page in pages for row in page
               if "pull_request" not in row and request_id in work.request_ids(row.get("body"))]
    if len(matches) != 1:
        raise ValueError("发布回执待核实，请按稳定需求 ID 对账；当前不会再次建单")
    return matches[0]["html_url"]


def readback(work, url, plan, principal):
    repository = plan["repository"]
    match = re.fullmatch(r"https://github\.com/" + re.escape(repository) + r"/issues/([1-9][0-9]*)", url)
    if not match:
        raise ValueError("来源返回的工单地址与仓库不匹配")
    number = int(match[1])
    row = json.loads(work.gh("api", f"repos/{repository}/issues/{number}"))
    body = (row.get("body") or "").replace("\r\n", "\n")
    expected = plan["body"] + "\n\n<!-- gonggong-host-git:" + principal["login"] + " -->"
    labels = [item["name"] for item in row["labels"]]
    statuses = [name[7:] for name in labels if name.startswith("status:")]
    if (row.get("html_url") != url or row.get("number") != number or row.get("state") != "open"
            or "pull_request" in row or str(row["user"]["id"]) != principal["user_id"]
            or row["title"] != plan["title"] or body.rstrip("\n") != expected
            or work.request_ids(body) != {plan["request_id"]} or "workspace:gonggong" not in labels
            or [name for name in labels if name.startswith("type:")] != [plan["labels"][0]]
            or len(statuses) != 1 or statuses[0] not in {"in-progress", "in-review", "blocked", "needs-decision", "planned"}
            or not row.get("updated_at") or not row.get("created_at")):
        raise ValueError("工单来源、创建者、原文或当前状态不符，请按原工单核对")
    if work.gh("api", "user", "--jq", ".id").strip() != principal["user_id"]:
        raise ValueError("发布期间 GitHub 账号已切换，请切回原账号核对")
    return ({"number": number, "url": url, "request_id": plan["request_id"], "status": statuses[0],
             "revision": row["updated_at"]}, row)


def write_requirement(path, raw, saved):
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("不能通过链接写入需求文档")
    if path.exists():
        previous = path.read_bytes()
        if previous == raw:
            return
        if saved.get("pending") or hashlib.sha256(previous).hexdigest() != saved.get("digest"):
            raise ValueError("已有同标识的不同需求文档，请核对来源")
    path.parent.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stage:
        stage.write(raw)
        stage.flush()
        os.fsync(stage.fileno())
    try:
        os.replace(stage.name, path)
    finally:
        Path(stage.name).unlink(missing_ok=True)


def refresh(root, result, row, allowed_types, repository, node_runtime, bridge):
    env = bridge.host_environment(root)
    node = bridge.discover_node(root, env)
    if not node:
        path = Path(node_runtime or "")
        if not (path.is_absolute() and path.name.lower() in {"node", "node.exe"}
                and path.is_file() and os.access(path, os.X_OK)):
            raise ValueError("工单已回读；请配置可执行的 Node.js，再用原草稿刷新司南")
        node = str(path)
    command = [node, str(Path(__file__).with_name("direct_event.mjs"))]
    payload = {"result": result, "issue": row, "allowedCategories": allowed_types, "repository": repository}
    process = subprocess.run(command, cwd=root, env=env, input=json.dumps(payload), capture_output=True,
                             text=True, encoding="utf-8", timeout=30)
    if process.returncode:
        raise ValueError("工单已回读；司南事件未取得匹配的来源回执，请按原草稿重试")
    receipt = json.loads(process.stdout)
    source = receipt["sourceSnapshot"]
    if (receipt["event"] != {"type": "request.created", "reference": result["url"]}
            or source["authority"] != result["url"] or source["requestId"] != result["request_id"]
            or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) or receipt["revision"] != result["revision"]
            or receipt["execution"] != "not_dispatched"):
        raise ValueError("司南刷新回执待核实")
    return receipt


def publish(work, issue_args, plan, expected_user, journal, saved):
    key = plan["request_id"]
    if saved.get("pending"):
        url = existing(work, plan["repository"], key)
        if saved.get("url", url) != url:
            raise ValueError("已发布工单的稳定身份发生变化")
    else:
        saved.update(pending=False)
        save(journal, saved)
        # The original source owns deduplication and creation. Journal only the mutating
        # call so a failed read-only lookup never freezes an unpublished draft.
        gh = work.gh

        def guarded_gh(*args):
            if args[:2] != ("issue", "create"):
                response = gh(*args)
                if args[:2] == ("api", f"repos/{plan['repository']}/issues?state=all&per_page=100"):
                    if any(key in work.request_ids(row.get("body")) for page in json.loads(response)
                           for row in page if "pull_request" not in row):
                        saved["pending"] = True
                        save(journal, saved)
                return response
            if gh("api", "user", "--jq", ".id") != expected_user:
                raise ValueError("建单前账号已切换")
            saved["pending"] = True
            save(journal, saved)
            try:
                return gh(*args)
            except work.GitHubCommandError as error:
                if error.http_status in {400, 401, 403, 404, 405, 410, 422}:
                    saved["pending"] = False
                    save(journal, saved)
                raise

        work.gh = guarded_gh
        try:
            publication = work.issue(*issue_args, apply=True, planned=True)
        finally:
            work.gh = gh
        url = publication["url"]
        saved.update(pending=True, url=url)
        save(journal, saved)
    return url


def create_locked(root, request, bridge, journal, saved):
    expected_user = request.get("expected_user")
    if not isinstance(expected_user, str) or not re.fullmatch(r"[1-9][0-9]*", expected_user):
        raise ValueError("请先验证仓库协作者身份")
    key = journal.parent.name
    work, settings, fields = bridge.guide_fields(root, {**request, "request_id": key})
    check_text(request)
    _, auth_error = bridge.gh_state(root)
    if auth_error:
        raise ValueError(auth_error)
    principal = collaborator(root)
    if principal["user_id"] != expected_user or principal["repo"] != settings["repository"]:
        raise ValueError("当前仓库协作者与草稿账号不匹配")
    content = (f"# {fields['title']}\n\n<!-- gonggong-intake:daqian-direct -->\n\n"
               f"需求 ID：`{key}`\n\n类别：`type:{fields['category']}`\n\n"
               f"来源：Godot 大千草稿 `{request['draft_id']}`，GitHub 用户 ID `{expected_user}`。\n\n"
               "## 原始需求\n\n" + request["outcome"] + "\n")
    digest = hashlib.sha256(content.encode()).hexdigest()
    document = root / fields["document"]
    if saved.get("pending") and saved["digest"] != digest:
        raise ValueError("请用原草稿及原账号核对发布回执")
    write_requirement(document, content.encode(), saved)
    args = (root, fields["document"], fields["title"], fields["category"], key)
    plan = work.issue(*args, planned=True)
    saved["digest"] = digest
    url = publish(work, args, plan, expected_user, journal, saved)
    result, row = readback(work, url, plan, principal)
    if "event" not in saved:
        saved["event"] = {
            "schema_version": 1, "event_id": key + "-created", "tenant_id": settings["tenant_id"],
            "request_id": key, "kind": "request", "occurred_at": row["created_at"], "source_ref": url,
            "agent": {"id": "godot-daqian", "version": "1", "origin": "external-authorized-host",
                      "definition_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            "payload": {"event": "request.created", "draft_id": request["draft_id"], "actor_id": expected_user,
                        "document": fields["document"], "document_sha256": digest, "path_base": "repository_root",
                        "status": result["status"], "revision": result["revision"], "execution": "not_dispatched"},
            "evidence_refs": [],
        }
        save(journal, saved)
    bridge.enqueue(root, saved["event"])
    bridge.flush(root)
    if "coordination" not in saved:
        _, definitions = work.config(root)
        saved["coordination"] = refresh(root, result, row, [label["name"] for label in definitions],
                                        settings["repository"], request.get("node_runtime"), bridge)
        save(journal, saved)
    return {"ok": True, **result, "coordination": saved["coordination"], "execution": "not_dispatched"}


def create(root, request, bridge):
    saved = {}
    uncertain = False
    try:
        draft = request.get("draft_id")
        if not isinstance(draft, str) or not re.fullmatch(r"draft_[a-f0-9]{20}", draft):
            raise ValueError("无效的大千草稿标识")
        key = "daqian-direct-" + draft[6:]
        common = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                text=True, capture_output=True, check=True, timeout=15).stdout.strip()
        folder = Path(common).parent / "data-collection/receipts/daqian-direct" / key
        journal = folder / "state.json"
        uncertain = True  # An occupied lock or unreadable journal can represent an in-flight create.
        with bridge.outbox_lock(folder, time.monotonic() + 3):
            if journal.exists():
                saved = json.loads(journal.read_text(encoding="utf-8"))
            uncertain = False
            return create_locked(root, request, bridge, journal, saved)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": str(error), "reconcile_required": uncertain or saved.get("pending", False),
                "execution": "not_dispatched"}
