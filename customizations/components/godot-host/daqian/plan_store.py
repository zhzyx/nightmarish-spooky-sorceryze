"""Versioned plans for one bound installation. Execution authority stays with the host."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

from board import source_plan, work_items

PUBLIC_KINDS = {"text", "image", "question", "task", "join"}
LOCKED = {"reserved", "dispatched", "running", "completed", "failed", "cancelled", "reconcile_required"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def check_plan(original, draft, context):
    if not isinstance(draft, dict) or set(draft) != {"nodes", "edges"}:
        raise ValueError("图格式无效")
    nodes, edges = draft["nodes"], draft["edges"]
    if not isinstance(nodes, dict) or not isinstance(edges, list) or len(nodes) > 4096 or len(edges) > 32768:
        raise ValueError("单个工单图的节点或连线数量无效")
    locked = set(context["protected_nodes"])
    active = {key for key, state in context.get("states", {}).items() if state in LOCKED}
    for key in locked | active:
        if original["nodes"].get(key) != nodes.get(key):
            raise ValueError(f"节点 {key} 已受保护")
    for key, node in nodes.items():
        if not isinstance(key, str) or not key.isascii() or not key.isidentifier() or not isinstance(node, dict):
            raise ValueError("节点标识无效")
        if key in locked:
            continue
        if set(node) - {"kind", "title", "value", "model"} or not all(isinstance(v, str) for v in node.values()):
            raise ValueError("节点字段无效")
        if node.get("kind") not in PUBLIC_KINDS or not node.get("title", "").strip():
            raise ValueError("节点类型或标题无效")
        if key in original["nodes"] and original["nodes"][key]["kind"] != node["kind"]:
            raise ValueError("已有节点不能改变类型")
        if node.get("model") and node["model"] not in context.get("models", {}):
            raise ValueError("指定型号缺少宿主能力证据")

    def identity(e):
        if not isinstance(e, dict) or set(e) != {"from", "to", "kind"} or not all(isinstance(v, str) for v in e.values()):
            raise ValueError("连线格式无效")
        return e["from"], e["to"], e["kind"]

    given = {identity(e) for e in edges}
    if len(given) != len(edges):
        raise ValueError("重复连线")
    if not {identity(e) for e in context["protected_edges"]} <= given:
        raise ValueError("框架要求的连线已改变")
    previous = {identity(e) for e in original["edges"]}
    if any(target in active for _, target, _ in previous ^ given):
        raise ValueError("已运行节点的输入已锁定")
    incoming = dict.fromkeys(nodes, 0)
    outgoing = {key: [] for key in nodes}
    data_targets = set()
    for source, target, kind in given:
        if source not in nodes or target not in nodes or source == target or kind not in {"data", "after"}:
            raise ValueError("无效的端点或连线类型")
        if kind == "data":
            receiver = nodes[target]
            if receiver["kind"] not in {"task", "join"}:
                raise ValueError("目标不接收数据")
            model = receiver.get("model")
            if model and nodes[source]["kind"] == "image" and "image" not in context["models"].get(model, []):
                raise ValueError("此模型不接收图片")
            data_targets.add(target)
        outgoing[source].append(target)
        incoming[target] += 1
    frontier = [k for k in nodes if not incoming[k]]
    seen = 0
    while frontier:
        current = frontier.pop()
        seen += 1
        for key in outgoing[current]:
            incoming[key] -= 1
            if not incoming[key]:
                frontier.append(key)
    if seen != len(nodes):
        raise ValueError("存在循环等待")
    for key, node in nodes.items():
        if key in locked or key in data_targets:
            continue
        if node["kind"] == "join" or (node["kind"] in {"task", "text", "image"} and not node.get("value", "").strip()):
            raise ValueError("节点缺少输入：" + node["title"])


@contextmanager
def connect(root):
    common = Path(subprocess.check_output(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True).strip())
    folder = common.parent / "data-collection"
    folder.mkdir(exist_ok=True)
    db = sqlite3.connect(folder / "daqian.sqlite", timeout=8)
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS plans(issue TEXT PRIMARY KEY, source_revision TEXT NOT NULL,
                plan_json TEXT NOT NULL, plan_revision TEXT NOT NULL, actor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS node_runs(issue TEXT NOT NULL, node TEXT NOT NULL,
                run_id TEXT PRIMARY KEY, state TEXT NOT NULL, receipt TEXT);
            CREATE TABLE IF NOT EXISTS plan_events(issue TEXT NOT NULL, revision TEXT NOT NULL,
                source_revision TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(issue, revision));
        """)
        yield db
    finally:
        db.close()


def read_source(root, number):
    import issue_gate
    settings, _ = work_items.config(root)
    repo = settings["repository"]
    issue_gate.check_repository(root, repo)
    obj = json.loads(work_items.gh("api", f"repos/{repo}/issues/{number}"))
    ids = work_items.request_ids(obj.get("body"))
    if len(ids) != 1:
        raise ValueError("工单没有唯一共工需求标识")
    req = next(iter(ids))
    _, definitions = work_items.config(root)
    issue_gate.check_issue(obj, repo, number, req, {x["name"] for x in definitions})
    actor = json.loads(work_items.gh("api", "user"))["login"]
    access = json.loads(work_items.gh("api", f"repos/{repo}"))["permissions"]
    projection = source_plan(obj, req)
    return {"issue":obj["html_url"], "source_revision":digest([req,projection]),
            "issue_revision":obj["updated_at"], "base":projection["plan"], "sources":projection["sources"], "actor":actor,
            "can_edit":bool(access.get("push"))}


def snapshot(db, source):
    issue = source["issue"]
    row = db.execute("SELECT source_revision,plan_json,plan_revision FROM plans WHERE issue=?", (issue,)).fetchone()
    states = dict(db.execute("SELECT node,state FROM node_runs WHERE issue=? ORDER BY rowid", (issue,)))
    context = {"protected_nodes":list(source["base"]["nodes"]), "protected_edges":source["base"]["edges"],
               "states":states, "sources":source["sources"], "models":{}}
    # A changed upstream design needs explicit reconciliation before editing this version.
    return {"plan":json.loads(row[1]) if row else source["base"],
            "revision":digest([row[2] if row else None,source["source_revision"]]),
            "execution_revision":digest([states,source.get("issue_revision")]), "context":context,
            "can_edit":source["can_edit"] and (not row or row[0] == source["source_revision"])}


def apply(db, source, req):
    db.execute("BEGIN IMMEDIATE")
    try:
        fresh = snapshot(db, source)
        if not fresh["can_edit"]:
            raise ValueError("源设计修订或工单编辑权限已变更")
        if req["revision"] != fresh["revision"] or req["execution_revision"] != fresh["execution_revision"]:
            raise ValueError("工单版本或执行状态已变化，草稿已保留")
        check_plan(fresh["plan"], req["plan"], fresh["context"])
        if fresh["plan"] != req["plan"]:
            version = digest([fresh["revision"],req["plan"]])
            args = (source["issue"],source["source_revision"],json.dumps(req["plan"],ensure_ascii=False),version,source["actor"])
            db.execute("INSERT OR REPLACE INTO plans VALUES(?,?,?,?,?)", args)
            db.execute("INSERT INTO plan_events(issue,revision,source_revision,actor) VALUES(?,?,?,?)",
                       (source["issue"], version, source["source_revision"], source["actor"]))
        result = snapshot(db, source)
        db.commit()
        return dict(result, ok=True)
    except BaseException:
        db.rollback()
        raise
