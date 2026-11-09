"""Trusted operator GitHub port for the approved Yanluo definition.

Run only from a trusted installation, never from an untrusted PR checkout.
The signed grant binds the task, acceptance evidence and exact candidate. Signing
uses the existing GONGGONG_HOST_KEY convention; this module cannot issue grants.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import issue_gate
import yanluo_progress

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "customizations/components/yanluo"))
from closure import REQUIRED, Candidate, finalize, require  # noqa: E402


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def pinned_json(repo, relative, digest):
    path = (repo / relative).resolve()
    path.relative_to(repo)
    content = path.read_bytes()
    require(sha(content) == digest, "Signed record drift: " + relative)
    return json.loads(content)


def verify_definition(repo, registration, payload):
    approval = pinned_json(repo, registration["approval"], payload["approval_sha256"])
    manifest = pinned_json(repo, approval["candidate_manifest"], payload["candidate_manifest_sha256"])
    digest = payload["definition_digest"]
    require(
        approval["decision"] == "approved"
        and approval["subject"] == registration["id"] == "yanluo"
        and approval["version"] == manifest["candidate_version"] == registration["version"]
        and approval["candidate_digest"] == registration["candidate_digest"] == manifest["candidate_digest"] == digest,
        "Yanluo definition has no matching approval",
    )
    records = manifest["files"]
    paths = [item["path"] for item in records]
    require(registration["definition"] in paths and len(set(paths)) == len(paths), "Invalid definition file inventory")
    aggregate = sha("".join(item["path"] + "\0" + item["sha256"] + "\n" for item in records).encode())
    require(aggregate == digest, "Definition manifest aggregate mismatch")
    for item in records:
        path = (repo / item["path"]).resolve()
        path.relative_to(repo)
        require(sha(path.read_bytes()) == item["sha256"], "Approved definition drift: " + item["path"])


def validate_grant(grant, key, candidate, repo):
    require(len(key) >= 32, "Trusted host key must be provisioned outside model context")
    p = grant["payload"]
    require(
        hmac.compare_digest(
            hmac.new(key.encode(), canonical(p).encode(), hashlib.sha256).hexdigest(), grant["signature"]
        ),
        "Invalid host signature",
    )
    require(p["expires_at"] > time.time(), "Expired host grant")
    require(p["candidate"] == asdict(candidate), "Grant candidate mismatch")
    require(Path(p["repo_root"]).resolve() == repo, "Grant repository mismatch")
    require(p["authority_ref"] and p["account_login"], "Missing authenticated host authority")
    require(p["target"] == "main" and p["mode"] == "fast_forward", "Unsupported publication mode")
    return p


class GithubHost:
    def __init__(self, repo, grant, gh="gh"):
        self.repo = Path(repo).resolve()
        self.grant = grant
        self.gh = gh
        self.fd = None
        self.payload = None
        common = Path(self.git("rev-parse", "--git-common-dir").strip())
        self.state_root = (self.repo / common).resolve() / "yanluo"
        self.state_root.mkdir(exist_ok=True)

    def command(self, args, input_value=None):
        env = dict(os.environ)
        env.pop("GONGGONG_HOST_KEY", None)
        result = subprocess.run(
            args,
            cwd=self.repo,
            input=input_value,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            env=env,
        )
        require(result.returncode == 0, "Command failed: " + Path(str(args[0])).name + ": " + result.stderr[-2000:])
        return result.stdout

    def git(self, *args):
        return self.command(["git", *args])

    def api(self, endpoint, method="GET", body=None):
        args = [self.gh, "api", endpoint, "--method", method]
        if body is not None:
            args += ["--input", "-"]
        output = self.command(args, None if body is None else canonical(body))
        return json.loads(output) if output.strip() else None

    def endpoint(self, c, suffix):
        return f"repos/{c.repository}/{suffix}"

    def authorize(self, c):
        require(re.fullmatch(r"[\w.-]+/[\w.-]+", c.repository), "Invalid repository")
        require(type(c.issue) is int and c.issue > 0, "Invalid Issue")
        for value in (c.commit, c.tree, c.expected_main):
            require(re.fullmatch("[0-9a-f]{40}", value), "Full Git object ID required")
        self.payload = validate_grant(self.grant, os.environ.get("GONGGONG_HOST_KEY", ""), c, self.repo)
        registry = pinned_json(self.repo, "customizations/host-agents.json", self.payload["host_registry_sha256"])
        registrations = [x for x in registry["agents"] if x["id"] == "yanluo"]
        require(
            len(registrations) == 1
            and registrations[0]["governance_root"] == "yuanheng"
            and registrations[0]["state"] == "approved_definition_host_authority_required"
            and registrations[0]["candidate_digest"] == self.payload["definition_digest"],
            "Yanluo is not registered for this host",
        )
        issue_gate.check_repository(self.repo, c.repository)
        settings = read_json(self.repo / "work-items.json")
        require(settings["repository"] == c.repository, "Wrong configured repository")
        require(self.api("user")["login"] == self.payload["account_login"], "GitHub identity changed")
        verify_definition(self.repo, registrations[0], self.payload)
        require(sha(Path(__file__).read_bytes()) == self.payload["adapter_sha256"], "Host implementation drift")
        trusted_files = [
            "customizations/components/issue-workorders/" + x
            for x in ("yanluo_host.py", "yanluo_progress.py", "issue_gate.py", "work_items.py")
        ]
        trusted_files += [
            "customizations/components/yanluo/closure.py",
            "tools/check_gonggong_distribution.py",
            "customizations/platforms/development/git/git_batch.py",
            "integrations/gonggong/frozen-distribution.json",
            "customizations/platforms/data-collection/git-files/storage/diting_files.py",
            "customizations/platforms/development/git/delivery/check_delivery.py",
        ]
        trusted_files += [
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "framework").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
        require(set(self.payload["trusted_files"]) == set(trusted_files), "Incomplete trusted implementation inventory")
        for relative in trusted_files:
            digest = sha((ROOT / relative).read_bytes())
            require(digest == self.payload["trusted_files"][relative], "Trusted installation drift: " + relative)
            if relative.startswith(("framework/", "customizations/platforms/")):
                require(
                    sha((self.repo / relative).read_bytes()) == digest,
                    "Candidate framework requires separate trusted installation review: " + relative,
                )
        for directory in (
            "customizations/platforms/data-collection/git-files/storage",
            "customizations/platforms/development/git/delivery",
        ):
            issue_gate.verify_platform_adapter(self.repo, directory, registration_root=ROOT)
        require(self.git("rev-parse", c.commit + "^{tree}").strip() == c.tree, "Candidate tree changed")
        require(
            self.git("merge-base", c.commit, c.expected_main).strip() == c.expected_main,
            "Candidate must descend from expected main",
        )
        self.c = c
        self.state_file = self.state_root / (sha(canonical(asdict(c)).encode()) + ".json")

    def acquire(self, c):
        # One lock per Git common directory, shared by every linked worktree.
        try:
            with open(self.state_root / "main.lock", "xb") as initial:
                initial.write(b"0")
        except FileExistsError:
            pass
        self.fd = open(self.state_root / "main.lock", "r+b")
        self.fd.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fd.close()
            self.fd = None
            raise ValueError("Another release owns main")
        return self.fd

    def release(self, lease):
        if self.fd is lease:
            lease.close()
            self.fd = None

    def saved(self):
        return read_json(self.state_file) if self.state_file.exists() else {}

    def save(self, value):
        temp = self.state_file.with_suffix(".pending")
        with open(temp, "w", encoding="utf-8", newline="\n") as f:
            f.write(canonical(value) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.state_file)

    def issue(self, c):
        value = self.api(self.endpoint(c, f"issues/{c.issue}"))
        require(
            "pull_request" not in value and issue_gate.request_ids(value.get("body")) == {c.request_id},
            "Issue identity changed",
        )
        require(sha((value.get("body") or "").encode()) == c.scope_digest, "Issue scope changed")
        labels = [v["name"] for v in value["labels"]]
        require(
            "workspace:gonggong" in labels and len([v for v in labels if v.startswith("type:")]) == 1,
            "Issue classification changed",
        )
        status = [v[7:] for v in labels if v.startswith("status:")]
        transition = self.saved().get("label_transition")
        if len(status) == 2 and transition and set(status) == {transition, "done"}:
            status = [transition]
        require(len(status) == 1, "Ambiguous Issue status")
        return value, status[0]

    def read_main(self, c):
        main = self.api(self.endpoint(c, "commits/main"))
        comparison = self.api(self.endpoint(c, f"compare/{c.commit}...{main['sha']}"))
        contained = comparison["status"] in {"identical", "ahead"}
        return dict(
            candidate=c, contained=contained, remote_commit=main["sha"], remote_tree=main["commit"]["tree"]["sha"]
        )

    def read(self, c):
        issue, status = self.issue(c)
        remote = self.read_main(c)
        proof = self.saved().get("verification")
        if proof:
            proof = dict(proof, candidate=Candidate(**proof["candidate"]))
        return dict(
            candidate=c,
            published=remote["contained"],
            closed=issue["state"] == "closed",
            status=status,
            main=remote["remote_commit"],
            revision=issue["updated_at"],
            verification=proof,
        )

    def verify(self, c):
        p = self.payload
        require(self.git("rev-parse", "HEAD").strip() == c.commit, "Verification needs exact checked-out candidate")
        require(not self.git("status", "--porcelain").strip(), "Candidate worktree must be clean")
        evidence = p["checks"]
        require(set(evidence) == REQUIRED, "Incomplete host acceptance inventory")
        for name, item in evidence.items():
            path = (self.repo / item["path"]).resolve()
            path.relative_to(self.repo)
            require(sha(path.read_bytes()) == item["sha256"], "Changed evidence: " + name)
            require(
                item["status"] == "passed" and item["candidate"] == asdict(c), "Unbound or failed evidence: " + name
            )
        self.command([
            sys.executable,
            str(ROOT / "customizations/components/issue-workorders/issue_gate.py"),
            "--repo",
            str(self.repo),
            "--issue",
            str(c.issue),
            "--request-id",
            c.request_id,
        ])
        self.command([
            sys.executable,
            "-I",
            str(ROOT / "customizations/platforms/data-collection/git-files/storage/diting_files.py"),
            "git-check",
            "--repo",
            str(self.repo),
            "--require-committed",
        ])
        # The host signs an already-run delivery manifest result among checks;
        # no arbitrary test commands from a PR or grant are ever executed.
        runs = self.api(self.endpoint(c, f"commits/{c.commit}/check-runs?per_page=100"))
        require(runs["total_count"] <= 100, "Paginate check inventory before authorizing")
        names = {}
        for run in runs["check_runs"]:
            if run["name"] not in names or run["id"] > names[run["name"]]["id"]:
                names[run["name"]] = run
        require(p["required_ci_names"], "Host must explicitly name required CI")
        for name in p["required_ci_names"]:
            require(
                name in names and names[name]["status"] == "completed" and names[name]["conclusion"] == "success",
                "Required CI not successful: " + name,
            )
        return dict.fromkeys(REQUIRED, True)

    def publish(self, c):
        validate_grant(self.grant, os.environ.get("GONGGONG_HOST_KEY", ""), c, self.repo)
        require(self.fd is not None, "Release lease missing")
        current = self.read(c)
        require(current["main"] == c.expected_main and not current["closed"], "Target advanced or Issue closed")
        require(self.api("user")["login"] == self.payload["account_login"], "Identity drift")
        # REST force=false rejects non-fast-forward changes and respects protection.
        # It never constructs a merge against a newer, untested main tree.
        result = self.api(self.endpoint(c, "git/refs/heads/main"), "PATCH", {"sha": c.commit, "force": False})
        require(result["object"]["sha"] == c.commit, "Unknown publication response")

    def record(self, c, phase, evidence):
        def serial(value):
            if isinstance(value, Candidate):
                return asdict(value)
            if isinstance(value, dict):
                return {k: serial(v) for k, v in value.items()}
            return value

        state = self.saved()
        entry = serial(evidence)
        if phase == "verified":
            state["verification"] = dict(candidate=asdict(c), checks=entry, receipt_id=sha(canonical(entry).encode()))
        state.setdefault("events", []).append(dict(phase=phase, evidence=entry, observed_at=time.time()))
        self.save(state)
        # Durable host journal is private execution state, not a Diting ingestion claim.
        # Expose completed publication and closure in the authoritative Issue timeline.
        if phase in {"release.completed", "issue.closed", "progress.reconciled"}:
            marker = f"<!-- yanluo:{c.event_id}:{c.commit}:{phase} -->"
            pages = json.loads(
                self.command([self.gh, "api", self.endpoint(c, f"issues/{c.issue}/comments"), "--paginate", "--slurp"])
            )
            if not any(marker in x["body"] for page in pages for x in page):
                self.api(
                    self.endpoint(c, f"issues/{c.issue}/comments"),
                    "POST",
                    {"body": marker + "\n\n阎罗：" + phase + "\n\n```json\n" + canonical(entry) + "\n```"},
                )

    def mark_done(self, c):
        require(self.read_main(c)["contained"], "Publication missing")
        progress = yanluo_progress.reconcile(self, c, self.payload["acceptance_items"])
        if not progress["complete"]:
            raise ValueError("Delivered scope recorded; overall Issue remains open; see remaining-work Issues")
        issue, status = self.issue(c)
        if status == "done":
            return
        require(issue["state"] == "open" and status in {"in-progress", "in-review"}, "Unexpected Issue state")
        # Preserve all non-status labels. Re-read before each limited mutation.
        state = self.saved()
        state["label_transition"] = status
        self.save(state)
        self.api(self.endpoint(c, f"issues/{c.issue}/labels"), "POST", {"labels": ["status:done"]})
        current, observed = self.issue(c)
        require(observed in {status, "done"}, "Concurrent status transition")
        if any(x["name"] == "status:" + status for x in current["labels"]):
            self.api(self.endpoint(c, f"issues/{c.issue}/labels/status:{status}"), "DELETE")
        updated, actual = self.issue(c)
        require(actual == "done", "Concurrent status mutation")

    def close(self, c):
        issue, status = self.issue(c)
        require(status == "done" and self.read_main(c)["contained"], "Not ready to close")
        if issue["state"] == "closed":
            require(issue["state_reason"] == "completed", "Issue closed for another reason")
            return
        self.api(self.endpoint(c, f"issues/{c.issue}"), "PATCH", {"state": "closed", "state_reason": "completed"})

    def reconcile(self, c):
        # Source adapter consumes the real Issue event; no parent is closed here.
        self.record(
            c,
            "sinan_source_available",
            {"source_ref": f"https://github.com/{c.repository}/issues/{c.issue}", "consumer_confirmation": None},
        )

    def issue_pages(self, c):
        return json.loads(
            self.command([self.gh, "api", self.endpoint(c, "issues?state=all&per_page=100"), "--paginate", "--slurp"])
        )

    def create_followup(self, c, work):
        return self.api(
            self.endpoint(c, "issues"),
            "POST",
            {
                "title": work["title"],
                "body": work["body"] + "\n<!-- gonggong-host-git:" + self.payload["account_login"] + " -->\n",
                "labels": ["type:development", "status:planned", "workspace:gonggong"],
            },
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--grant", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    grant = read_json(args.grant)
    candidate = Candidate(**grant["payload"]["candidate"])
    host = GithubHost(args.repo, grant, os.environ.get("GONGGONG_GH", "gh"))
    if args.apply:
        print(
            canonical({
                k: asdict(v) if isinstance(v, Candidate) else v
                for k, v in finalize(candidate, host).items()
                if k != "verification"
            })
        )
    else:
        host.authorize(candidate)
        print(canonical({"authorized": True, "apply": False, "issue": candidate.issue}))
