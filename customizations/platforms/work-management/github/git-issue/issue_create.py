"""Optional GitHub issue intake. Host authorization is external, never inferred."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

_RUNTIME_PATH = Path(__file__).resolve().parents[4] / "components/issue-workorders/github_runtime.py"
_RUNTIME_SHA = hashlib.sha256(_RUNTIME_PATH.read_bytes()).hexdigest()
_runtime_spec = importlib.util.spec_from_file_location("git_issue_github_runtime", _RUNTIME_PATH)
if _runtime_spec is None or _runtime_spec.loader is None:
    raise ImportError("Cannot load installed GitHub runtime")
github_runtime = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(github_runtime)


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def digest(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def adapter_digest():
    if hashlib.sha256(_RUNTIME_PATH.read_bytes()).hexdigest() != _RUNTIME_SHA:
        raise ValueError("Installed GitHub runtime changed; restart before selecting or executing a plan")
    return digest({"adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "github_runtime": _RUNTIME_SHA})


def plan(request, workspace):
    for field in ("request_id", "title", "body", "owner", "acceptance", "authority_ref"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise ValueError("Required: " + field)
        if "<!--" in request[field]:
            raise ValueError("Identity comment injection in " + field)
    if not re.fullmatch("[a-z0-9][a-z0-9-]{2,100}", request["request_id"]):
        raise ValueError("Invalid request_id")
    if not re.fullmatch("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", workspace["repository"]):
        raise ValueError("Invalid repository")
    if request.get("type") not in (
        "design",
        "requirement",
        "development",
        "bug",
        "test",
        "research",
        "documentation",
        "maintenance",
    ):
        raise ValueError("Invalid type")
    marker = "<!-- gonggong-request:" + request["request_id"] + " -->"
    if "<!--" in request["body"] or "<!--" in request["title"]:
        raise ValueError("Body/title cannot inject identity markers")
    result = {
        "repository": workspace["repository"],
        "workspace": workspace["workspace_id"],
        "request_id": request["request_id"],
        "marker": marker,
        "title": request["title"],
        "body": marker
        + "\n\n"
        + request["body"]
        + "\n\n责任人："
        + request["owner"]
        + "\n验收："
        + request["acceptance"]
        + "\n授权来源："
        + request["authority_ref"],
        "labels": ["type:" + request["type"], "status:needs-decision", workspace["workspace_label"]],
        "authority_ref": request["authority_ref"],
    }
    result["adapter_sha256"] = adapter_digest()
    result["plan_sha256"] = digest(result)
    return result


class GitHub:
    def __init__(self, executable):
        self.executable = executable

    def call(self, *args):
        # Keep this adapter's explicit CLI and original single-request/write budget.
        # Native REST pagination uses the installed shared operation policy.
        timeout = None if github_runtime.read_only_pagination(args) else 90
        return github_runtime.run_gh(*args, env={**os.environ, "GONGGONG_GH": self.executable}, timeout=timeout)

    def actor(self):
        return json.loads(self.call("api", "user"))["login"]

    def find(self, p):
        pages = json.loads(
            self.call("api", "--paginate", "--slurp", f"repos/{p['repository']}/issues?state=all&per_page=100")
        )
        return [x for page in pages for x in page if not x.get("pull_request") and p["marker"] in (x.get("body") or "")]

    def create(self, p, body):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "body.md"
            f.write_text(body, encoding="utf-8")
            args = ["issue", "create", "--repo", p["repository"], "--title", p["title"], "--body-file", str(f)]
            for label in p["labels"]:
                args += ["--label", label]
            return self.call(*args)

    def get(self, p, url):
        prefix = "https://github.com/" + p["repository"] + "/issues/"
        if not url.startswith(prefix) or not url[len(prefix) :].isdigit():
            raise ValueError("Wrong repository issue URL")
        return json.loads(self.call("api", f"repos/{p['repository']}/issues/{url[len(prefix) :]}"))


def execute(p, settings, root, api, report):
    """report(event)->True means shared Diting delivered; injected by actual host."""
    if settings.get("enabled") is not True:
        raise ValueError("Module disabled; select it explicitly")
    if settings.get("approved_plan_sha256") != p["plan_sha256"]:
        raise ValueError("Plan not selected/authorized")
    if p.get("adapter_sha256") != adapter_digest():
        raise ValueError("Select a plan for the current adapter")
    bare = {k: v for k, v in p.items() if k != "plan_sha256"}
    if digest(bare) != p["plan_sha256"]:
        raise ValueError("Plan changed")
    authority = (root / p["authority_ref"]).resolve()
    authority.relative_to(root.resolve())
    if not authority.is_file():
        raise ValueError("Missing authority reference")
    root = root.resolve()
    state = root / "data-collection/git-issue"
    for target in (root / "data-collection", state):
        if target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
            raise ValueError("Reparse storage path rejected")
        target.resolve().relative_to(root)
    state.mkdir(parents=True, exist_ok=True)
    key = digest([p["repository"], p["request_id"]])
    claim = state / (key + ".json")
    lock = state / (key + ".lock")
    for target in (claim, lock):
        if target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
            raise ValueError("Reparse claim rejected")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        actor = api.actor()
        if not re.fullmatch("[A-Za-z0-9-]+", actor):
            raise ValueError("Invalid authenticated actor")
        matches = api.find(p)
        if len(matches) > 1:
            raise ValueError("Duplicate remote identity; reconcile before proceeding")
        if matches:
            issue = api.get(p, matches[0]["html_url"])
            action = "reused"
        else:
            if claim.exists():
                raise ValueError("Prior create may have executed; reconcile, never blind retry")
            if not report({"phase": "before_create", "actor": actor, "plan": p}):
                raise ValueError("Reporting not delivered; remote create not attempted")
            # Persist before the first remote effect; even unknown network outcomes retain claim.
            claim.write_text(
                json.dumps({"status": "creation_claimed", "actor": actor, "plan_sha256": p["plan_sha256"]}),
                encoding="utf-8",
            )
            body = p["body"] + "\n\n<!-- host-git-account:" + actor + " -->\n宿主 GitHub 账号：" + actor
            url = api.create(p, body)
            issue = api.get(p, url)
            action = "created"
        body = issue.get("body") or ""
        markers = re.findall(r"<!-- gonggong-request:[^>]*-->", body)
        if body.splitlines()[0:1] != [p["marker"]] or markers != [p["marker"]]:
            raise ValueError("Readback identity mismatch")
        result = {
            "action": action,
            "issue_url": issue["html_url"],
            "issue_number": issue["number"],
            "authenticated_actor": actor,
            "issue_author": issue.get("user", {}).get("login"),
            "updated_at": issue.get("updated_at"),
            "body_sha256": digest(issue.get("body")),
            "plan_sha256": p["plan_sha256"],
            "global_atomicity": False,
        }
        claim.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        result["reporting_delivered"] = report({"phase": "readback", "result": result}) is True
        return result
    finally:
        os.close(fd)
        lock.unlink()


def main():
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("--workspace", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--settings")
    p.add_argument("--session")
    p.add_argument("--gh", default="gh")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    workspace = Path(a.workspace).resolve()
    root = workspace.parent
    planned = plan(read(a.request), read(workspace))
    if not a.apply:
        print(json.dumps(planned, ensure_ascii=False, indent=2))
        return
    import runpy

    if not a.settings or not a.session:
        raise ValueError("Selected settings and real reporting session required")
    host = runpy.run_path(str(root / "framework/tools/diting-host.py"))
    session = read(a.session)

    def report(event):
        key = "git-issue:" + digest(event)
        rid = session["request_ref"] + ":" + key
        stamp = host["now"]()
        r = {
            "schema_version": 2,
            "record_id": rid,
            "tenant_id": session["tenant_id"],
            "kind": "feedback",
            "created_at": stamp,
            "evidence_refs": [session["source_ref"]],
            "context": session["context"],
            "payload": {
                "source_key": session["source_key"],
                "external_id": key,
                "source_revision": "1",
                "occurred_at": stamp,
                "collected_at": stamp,
                "batch_id": key,
                "content": json.dumps(event, ensure_ascii=False),
                "original_ref": planned["authority_ref"],
                "context": {"module": "git-issue", "plan_sha256": planned["plan_sha256"]},
            },
        }
        envelope = {
            k: session[k] for k in ("tenant_id", "source_ref", "agent_snapshot_ref", "request_ref", "authority_ref")
        }
        envelope.update(batch_key=key, records=[r])
        # Recover exact payload on replay, including its original timestamps.
        catalog = root / "data-collection/catalog.json"
        catalog_root, catalog_config = host["config"](catalog)
        identity = host["sha"](host["canonical"]([session["tenant_id"], key]).encode())
        saved = host["resolve"](catalog_root, catalog_config["inbox"]) / (identity + ".json")
        if saved.exists():
            envelope = read(saved)
        return host["submit"](root / "data-collection/catalog.json", envelope)["delivered"]

    result = execute(planned, read(a.settings), root, GitHub(a.gh), report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["reporting_delivered"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
