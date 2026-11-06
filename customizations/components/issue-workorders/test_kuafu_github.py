"""GitHub event verification, attempt evidence and safe replay."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kuafu_github import BOT, DISPATCH_ACTIONS, OWN_WORKFLOW, ROOT, GitHubCommandError, record_evidence, route


class Host:
    repo = "example/repository"

    def __init__(self):
        self.repo_ref = {"full_name": self.repo}
        self.issue = {
            "number": 7,
            "state": "open",
            "updated_at": "2026-11-07T00:00:01Z",
            "body": "<!-- gonggong-request:abc -->",
            "labels": [{"name": name} for name in ("type:development", "workspace:gonggong", "status:blocked")],
        }
        self.run = {
            "repository": self.repo_ref,
            "id": 18,
            "run_attempt": 2,
            "workflow_id": 90,
            "event": "push",
            "head_sha": "a" * 40,
            "path": ".github/workflows/runner.yml",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "startup_failure",
            "pull_requests": [],
        }
        self.pr = {
            "number": 12,
            "head": {"repo": self.repo_ref, "sha": "b" * 40},
            "base": {"repo": self.repo_ref, "ref": "main"},
            "merged": True,
            "merge_commit_sha": "a" * 40,
            "author_association": "COLLABORATOR",
            "body": "GongGong-Issue: #7\nGongGong-Request: abc",
        }
        self.bugs, self.comments, self.jobs = [], [], []
        self.lose_receipt = False

    def get(self, path):
        return {"issues/7": self.issue, "pulls/12": self.pr, "actions/runs/18/attempts/2": self.run}[path]

    def pages(self, path, field=None):
        return {
            f"commits/{'a' * 40}/pulls": [self.pr],
            "actions/runs/18/attempts/2/jobs": self.jobs,
            "issues?state=all&creator=github-actions%5Bbot%5D": self.bugs,
            "issues/7/comments": self.comments,
        }[path]

    def post(self, path, body):
        record = {**body, "user": {"login": BOT}}
        if path == "issues":
            record["number"] = 99
            self.bugs.append(record)
            if self.lose_receipt:
                self.lose_receipt = False
                raise RuntimeError("receipt unknown")
        elif path == "issues/7/comments":
            self.comments.append(record)
        else:
            raise AssertionError(path)
        return record

    def route(self, name="workflow_run", **override):
        event = {"repository": self.repo_ref, "workflow_run": self.run.copy(), "action": "completed"}
        if name == "issues":
            event.update(issue=self.issue, action="labeled", label={"name": "status:blocked"})
        event.update(override)
        return route(self, name, event, context=lambda key, report: "e" * 64)


class KuafuGitHubTests(unittest.TestCase):
    def setUp(self):
        self.api = Host()

    def test_startup_failure_without_job_and_merged_pr_identity(self):
        result = self.api.route()
        self.assertEqual(result["failed_jobs"], [])
        self.assertEqual(result["original_issue"], 7)
        self.assertEqual(result["bug_number"], 99)
        self.assertIsNone(result["root_cause"])
        self.assertEqual(len(self.api.comments), 1)

    def test_recover_after_ambiguous_issue_create(self):
        self.api.lose_receipt = True
        with self.assertRaises(RuntimeError):
            self.api.route()
        self.api.route()
        self.api.route()
        self.assertEqual(len(self.api.bugs), 1)
        self.assertEqual(len(self.api.comments), 1)

    def test_no_attribution_from_untrusted_pr_or_stale_sha(self):
        self.api.pr["head"]["repo"] = {"full_name": "fork/example"}
        self.assertIsNone(self.api.route()["original_issue"])
        self.api.pr["head"]["repo"] = self.api.repo_ref
        self.api.pr["merge_commit_sha"] = "5" * 40
        self.assertIsNone(self.api.route()["original_issue"])
        self.assertEqual(self.api.comments, [])

    def test_failed_step_numbers_without_untrusted_names(self):
        self.api.run["conclusion"] = "failure"
        self.api.jobs = [
            {
                "id": 44,
                "conclusion": "failure",
                "name": "@everyone",
                "steps": [{"number": 3, "name": "INJECT!", "conclusion": "failure"}],
            }
        ]
        result = self.api.route()
        self.assertEqual(result["failed_jobs"][0]["failed_steps"], [3])
        self.assertNotIn("INJECT!", json.dumps(result))
        self.assertNotIn("@everyone", self.api.bugs[0]["body"])

    def test_only_current_workspace_blocked_issues_and_reuse_original_bug(self):
        self.api.issue["labels"][0]["name"] = "type:bug"
        self.api.route("issues")
        self.api.route("issues")
        self.assertEqual(len(self.api.comments), 1)
        self.assertEqual(self.api.bugs, [])
        self.api.issue["labels"].pop()
        self.assertIsNone(self.api.route("issues"))

    def test_closed_original_bug_receives_link_to_open_incident(self):
        self.api.issue.update(state="closed")
        self.api.issue["labels"][0]["name"] = "type:bug"
        self.assertEqual(self.api.route()["bug_number"], 99)
        self.assertIn("#99", self.api.comments[0]["body"])

    def test_later_blocked_transition_is_a_new_observation(self):
        first = self.api.route("issues")
        self.api.issue["updated_at"] = "2026-11-08T00:00:01Z"
        later = self.api.route("issues")
        self.assertNotEqual(first["incident_key"], later["incident_key"])

    def successful_retry(self, before, after, old_conclusion="failure", *, successor=False):
        self.api.jobs = before
        self.api.run["updated_at"] = "2026-11-06T00:00:00Z"
        self.api.run["conclusion"] = old_conclusion
        self.api.route()
        failed = self.api.run.copy()
        self.api.run.update(run_attempt=3, conclusion="success", updated_at="2026-11-07T01:00:00Z")
        success = self.api.run
        if successor:
            failed["updated_at"] = "2026-11-06T00:00:00Z"
            success.update(id=22, run_attempt=1, head_sha="f" * 40, run_started_at="2026-11-07T00:00:00Z")
            self.api.pr["head"]["sha"] = success["head_sha"]
        path = f"actions/runs/{success['id']}/attempts/{success['run_attempt']}"
        bug_comments = []
        api_get, api_pages, api_post = self.api.get, self.api.pages, self.api.post

        def get(url):
            if url.startswith("compare/"):
                return {"status": "ahead"}
            options = {"issues/99": self.api.bugs[0], path: success, "actions/runs/18/attempts/2": failed}
            return options[url] if url in options else api_get(url)

        def pages(url, field=None):
            options = {
                path + "/jobs": after,
                "actions/runs/18/attempts/2/jobs": before,
                "issues/99/comments": bug_comments,
                f"commits/{success['head_sha']}/pulls": [self.api.pr],
            }
            return options[url] if url in options else api_pages(url, field)

        def post(url, body):
            if url == "issues/99/comments":
                bug_comments.append({"user": {"login": BOT}, **body})
            else:
                return api_post(url, body)

        self.api.get, self.api.pages, self.api.post = get, pages, post
        return bug_comments

    def test_successful_retry_covers_failed_job_and_step_once(self):
        old = [
            {
                "id": 18,
                "name": "build",
                "conclusion": "failure",
                "steps": [{"number": 2, "name": "compile", "conclusion": "failure"}],
            }
        ]
        new = [
            {
                "id": 23,
                "name": "build",
                "conclusion": "success",
                "steps": [{"number": 2, "name": "compile", "conclusion": "success"}],
            }
        ]
        comments = self.successful_retry(old, new)
        proof = self.api.route()["reverification"][0]
        self.assertEqual(proof["state"], "operation_reverified")
        self.assertEqual(proof["first_failure_at"], "2026-11-06T00:00:00Z")
        self.assertEqual(proof["reverified_at"], "2026-11-07T01:00:00Z")
        self.assertIsNone(proof["condition_observed_at"])
        self.assertEqual(proof["jobs"], [{"failed_job": 18, "successful_job": 23, "steps": [2]}])
        self.assertIsNone(self.api.route())
        self.assertEqual(len(comments), 1)
        self.assertEqual(len(self.api.bugs), 1)
        self.assertEqual(len(self.api.comments), 2)

    def test_successful_descendant_can_only_be_a_recovery_candidate(self):
        self.successful_retry([], [{"id": 23, "conclusion": "success"}], "startup_failure", successor=True)
        proof = self.api.route()["reverification"][0]
        self.assertEqual(proof["state"], "recovery_candidate")
        self.assertEqual(proof["jobs"], [{"started_job": 23}])
        self.assertIsNone(proof["reverified_at"])
        # A legacy candidate receipt must not hide the still unverified original operation.
        from kuafu_github import prior_reports

        self.api.comments[-1]["body"] = self.api.comments[-1]["body"].replace(
            self.api.comments[-1]["body"].splitlines()[0], "<!-- kuafu-recovery:run-18-attempt-2 -->"
        )
        self.assertEqual(len(list(prior_reports(self.api, self.api.issue))), 1)

    def test_pr_target_successes_on_same_base_bind_distinct_pr_heads(self):
        self.api.run.update(event="pull_request_target", pull_requests=[self.api.pr])
        comments = self.successful_retry([], [{"id": 23, "conclusion": "success"}], "startup_failure")
        for letter in ("c", "d", "d"):
            self.api.pr["head"]["sha"] = letter * 40
            proof = self.api.route()["reverification"][0]
            self.assertEqual(proof["old_pr_head"], "b" * 40)
            self.assertEqual(proof["new_pr_head"], letter * 40)
            self.assertEqual(proof["new_candidate"], proof["old_candidate"])
            self.assertEqual(proof["state"], "recovery_candidate")
        self.assertEqual(len(comments), 2)

    def test_green_workflow_with_skipped_failed_step_keeps_pending(self):
        old = [
            {
                "id": 18,
                "name": "build",
                "conclusion": "failure",
                "steps": [{"number": 2, "name": "compile", "conclusion": "failure"}],
            }
        ]
        new = [
            {
                "id": 23,
                "name": "build",
                "conclusion": "success",
                "steps": [{"number": 2, "name": "compile", "conclusion": "skipped"}],
            }
        ]
        comments = self.successful_retry(old, new)
        self.assertIsNone(self.api.route())
        self.assertEqual(comments, [])

    def test_success_without_intake_avoids_jobs_context_and_writes(self):
        self.api.run["conclusion"] = "success"
        event = {"workflow_run": self.api.run, "action": "completed", "repository": self.api.repo_ref}
        with patch.object(self.api, "pages", wraps=self.api.pages) as reads:
            self.assertIsNone(route(self.api, "workflow_run", event, context=lambda *args: self.fail("loaded context")))
        self.assertFalse(any("/jobs" in call.args[0] for call in reads.call_args_list))
        self.assertFalse(self.api.bugs or self.api.comments)

    def test_different_workflow_or_no_started_job_is_not_restoration(self):
        comments = self.successful_retry([], [{"id": 23, "conclusion": "skipped"}], "startup_failure")
        self.assertIsNone(self.api.route())
        self.api.run["workflow_id"] = 999
        self.assertIsNone(self.api.route())
        self.assertFalse(comments)

    def local_dispatch(
        self, *, permission="write", event_updates=None, input_updates=None, env_updates=None, missing_commit=False
    ):
        head = "a" * 40
        env = {
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW_REF": f"{self.api.repo}/{OWN_WORKFLOW}@refs/heads/main",
            "GITHUB_ACTOR": "writer",
            "GITHUB_TRIGGERING_ACTOR": "writer",
            "GITHUB_RUN_ID": "122",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        env.update(env_updates or {})
        event = {
            "repository": self.api.repo_ref,
            "ref": "main",
            "sender": {"login": "writer"},
            "inputs": {
                "source_issue": "7",
                "request_id": "abc",
                "action": "validation",
                "incident": "c" * 64,
                "head": head,
            },
        }
        event["inputs"].update(input_updates or {})
        event.update(event_updates or {})
        source_get = self.api.get

        def get(path):
            if path == "":
                return {"default_branch": "main"}
            if path.startswith("collaborators/"):
                return {"user": {"login": path.split("/")[1]}, "permission": permission}
            if path == f"commits/{head}":
                if missing_commit:
                    raise GitHubCommandError(404)
                return {"sha": head}
            return source_get(path)

        with patch.dict(os.environ, env), patch.object(self.api, "get", get):
            return route(self.api, "workflow_dispatch", event, context=lambda *args: "d" * 64)

    def test_dispatch_reads_real_bindings_and_replays_without_duplicate(self):
        result = self.local_dispatch()
        self.assertEqual(result["remote_head"], "a" * 40)
        self.assertFalse(result["local_evidence_observed_by_runner"])
        self.assertIsNone(result["root_cause"])
        self.assertEqual(result["source"], "https://github.com/example/repository/issues/7")
        self.assertEqual(result["host_attempt"], "https://github.com/example/repository/actions/runs/122/attempts/1")
        self.local_dispatch()
        self.assertEqual((len(self.api.bugs), len(self.api.comments)), (1, 1))

    def test_dispatch_requires_current_default_branch_writer_and_open_issue(self):
        for args in [
            {"permission": "read"},
            {"event_updates": {"ref": "feature"}},
            {"env_updates": {"GITHUB_REF": "refs/tags/main"}},
            {"env_updates": {"GITHUB_WORKFLOW_REF": "other/repo@refs/heads/main"}},
            {"event_updates": {"sender": {"login": "someone-else"}}},
            {"input_updates": {"request_id": "different"}},
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.local_dispatch(**args)
        self.api.issue["state"] = "closed"
        with self.assertRaises(ValueError):
            self.local_dispatch()
        self.assertFalse(self.api.comments or self.api.bugs)

    def test_dispatch_rejects_unstructured_or_malformed_inputs(self):
        for bad in [
            {"source_issue": "01"},
            {"incident": "abc"},
            {"head": "HEAD"},
            {"action": "$(do-stuff)"},
            {"message": "secret"},
            {"request_id": "@all"},
            {"source_issue": 7},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.local_dispatch(input_updates=bad)
        self.assertFalse(self.api.comments or self.api.bugs)

    def test_dispatch_preserves_local_only_candidate_and_supported_actions(self):
        for idx, action in enumerate(sorted(DISPATCH_ACTIONS)):
            with self.subTest(action=action):
                result = self.local_dispatch(
                    input_updates={"action": action, "incident": f"{idx:064x}"}, missing_commit=True
                )
                self.assertIsNone(result["remote_head"])
                self.assertEqual(result["action"], action)

    def test_record_and_retain_quality_issue_without_claiming_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            for name in (
                "work-items.json",
                "CURRENT_FRAMEWORK.json",
                "gonggong-diting-data/dataset.json",
                "framework/tools/git_batch.py",
                "framework/extensions/diting-files/diting_files.py",
            ):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, root / name)
            with patch("kuafu_github.ROOT", root), patch.dict(os.environ, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1"):
                receipt = record_evidence(root / "artifact", "issue-7", {"source": "https://github.com/a/b/issues/7"})
                replay = record_evidence(root / "artifact", "issue-7", {"source": "https://github.com/a/b/issues/7"})
            self.assertEqual(replay, receipt)
            replay_receipt = json.loads((root / "artifact/record_receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(replay_receipt["idempotent"])
            self.assertTrue(Path(replay_receipt["path"]).exists())
            self.assertEqual(receipt["state"], "recorded_file")
            self.assertIsNone(receipt["consumption"])
            event = json.loads((root / "artifact/quality_issue.json").read_text(encoding="utf-8"))
            self.assertEqual(event["sha256"], receipt["sha256"])
            self.assertEqual(event["agent"]["id"], "kuafu-github-host")

    def test_reject_wrong_repo_attempt_and_ignore_self(self):
        with self.assertRaises(ValueError):
            self.api.route(repository={"full_name": "incorrect/repository"})
        with self.assertRaises(ValueError):
            self.api.route(workflow_run={**self.api.run, "head_sha": "1" * 40})
        self.api.run["path"] = OWN_WORKFLOW
        self.assertIsNone(self.api.route())
        self.assertEqual(self.api.bugs, [])


if __name__ == "__main__":
    unittest.main()
