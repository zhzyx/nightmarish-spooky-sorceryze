import hashlib
import hmac
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from yanluo_host import Candidate, GithubHost, canonical, validate_grant
from yanluo_progress import assess, reconcile


class HostTests(unittest.TestCase):
    def test_grant_binds_candidate_repository_and_expiry(self):
        from dataclasses import asdict

        c = Candidate("o/r", 1, "r", "a" * 40, "b" * 40, "c" * 40, "scope", "event")
        root = Path.cwd().resolve()
        p = dict(
            candidate=asdict(c),
            repo_root=str(root),
            expires_at=time.time() + 60,
            authority_ref="test-only",
            account_login="operator",
            target="main",
            mode="fast_forward",
        )
        key = "test-only-secret-not-a-production-key"
        grant = {"payload": p, "signature": hmac.new(key.encode(), canonical(p).encode(), hashlib.sha256).hexdigest()}
        self.assertEqual(validate_grant(grant, key, c, root), p)
        p2 = dict(p, mode="pull_request_merge", pull_request_number=42)
        grant2 = {
            "payload": p2,
            "signature": hmac.new(key.encode(), canonical(p2).encode(), hashlib.sha256).hexdigest(),
        }
        self.assertEqual(validate_grant(grant2, key, c, root), p2)
        for field, value in [
            ("target", "other"),
            ("expires_at", 0),
            ("account_login", "intruder"),
            ("mode", "pull_request_merge"),
        ]:
            changed = dict(grant, payload=dict(p, **{field: value}))
            with self.assertRaises(ValueError):
                validate_grant(changed, key, c, root)

    def test_pull_request_merge_mode_allows_zero_overlap_main_advance_and_rejects_overlap(self):
        c = Candidate("o/r", 1, "req", "a" * 40, "b" * 40, "c" * 40, "scope", "event")
        h = object.__new__(GithubHost)
        h.payload = {"mode": "pull_request_merge", "pull_request_number": 77, "account_login": "operator"}
        h.endpoint = lambda cand, suffix: suffix
        h.git = lambda *args: "src/mine.py\0"

        def api_disjoint(endpoint, method="GET", body=None):
            if endpoint.startswith("compare/"):
                return {"status": "ahead", "files": [{"filename": "apps/other.tsx"}]}
            return None

        h.api = api_disjoint
        self.assertEqual(h._effective_main_for_read(c, "d" * 40), c.expected_main)

        def api_overlap(endpoint, method="GET", body=None):
            if endpoint.startswith("compare/"):
                return {"status": "ahead", "files": [{"filename": "src/mine.py"}]}
            return None

        h.api = api_overlap
        self.assertEqual(h._effective_main_for_read(c, "d" * 40), "d" * 40)

    def test_two_worktrees_share_release_lock(self):
        with tempfile.TemporaryDirectory() as d:

            def host():
                h = object.__new__(GithubHost)
                h.state_root = Path(d)
                h.fd = None
                return h

            first, second = host(), host()
            lease = first.acquire(None)
            try:
                with self.assertRaises(ValueError):
                    second.acquire(None)
            finally:
                first.release(lease)
            second.release(second.acquire(None))

    def test_git_api_empty_success_is_supported(self):
        h = object.__new__(GithubHost)
        h.gh = "gh"
        with patch.object(h, "command", return_value=""):
            self.assertIsNone(h.api("example", "DELETE"))

    def test_subprocess_never_receives_host_signing_key(self):
        h = object.__new__(GithubHost)
        h.repo = Path.cwd()
        with patch.dict(os.environ, {"GONGGONG_HOST_KEY": "private-test-value"}):
            with patch("yanluo_host.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = ""
                run.return_value.stderr = ""
                h.command(["test-only"])
                self.assertNotIn("GONGGONG_HOST_KEY", run.call_args.kwargs["env"])

    def test_status_update_preserves_concurrent_business_label(self):
        h = object.__new__(GithubHost)
        labels = ["type:development", "workspace:gonggong", "status:in-progress"]
        h.payload = {"acceptance_items": []}
        saved = {}
        calls = []
        h.saved = lambda: dict(saved)
        h.save = lambda x: saved.update(x)
        h.read_main = lambda c: {"contained": True}
        h.issue = lambda c: (
            {"state": "open", "labels": [{"name": v} for v in labels]},
            "in-progress" if "status:in-progress" in labels else "done",
        )
        h.endpoint = lambda c, s: s

        def api(endpoint, method="GET", body=None):
            calls.append(method)
            if method == "POST":
                labels.extend(["status:done", "business:concurrent"])
            if method == "DELETE":
                labels.remove("status:in-progress")

        h.api = api
        with patch("yanluo_host.yanluo_progress.reconcile", return_value={"complete": True}):
            h.mark_done(Candidate("o/r", 1, "r", "c", "t", "b", "s", "e"))
        self.assertIn("business:concurrent", labels)
        self.assertEqual(calls, ["POST", "DELETE"])


def item(i, state, module):
    return dict(id=str(i), state=state, module=module, acceptance="observable acceptance", evidence="receipt:" + str(i))


class ProgressTests(unittest.TestCase):
    def test_unknown_does_not_invent_progress_or_split(self):
        result = assess([item(1, "done", "a"), item(2, "done", "b"), item(3, "unknown", "c")])
        self.assertFalse(result["complete"])
        self.assertFalse(result["split"])

    def test_majority_splits_known_remaining_work(self):
        result = assess([item(1, "done", "a"), item(2, "done", "b"), item(3, "remaining", "c")])
        self.assertTrue(result["split"])
        self.assertEqual(result["counts"]["done"], 2)

    def test_small_module_tail_splits_even_with_many_acceptance_items(self):
        result = assess([item(1, "done", "a"), item(2, "remaining", "b"), item(3, "remaining", "b")])
        self.assertTrue(result["split"])

    def test_early_work_stays_on_original_issue(self):
        result = assess([item(1, "remaining", "a"), item(2, "remaining", "b")])
        self.assertFalse(result["split"])

    def test_all_complete_no_followup(self):
        result = assess([item(1, "done", "a")])
        self.assertTrue(result["complete"])
        self.assertFalse(result["split"])

    def test_retry_reuses_open_followup_and_rejects_closed_conflict(self):
        class Host:
            def __init__(self):
                self.issues = []
                self.created = 0

            def read_main(self, c):
                return {"contained": True, "remote_commit": "main"}

            def issue_pages(self, c):
                return [self.issues]

            def create_followup(self, c, work):
                self.created += 1
                value = {"body": work["body"], "html_url": "https://example.test/issues/2", "state": "open"}
                self.issues.append(value)
                return value

            def record(self, *args):
                pass

        c = Candidate("o/r", 1, "req", "c", "t", "b", "scope", "event")
        h = Host()
        items = [item(1, "done", "a"), item(2, "done", "b"), item(3, "remaining", "c")]
        self.assertEqual(reconcile(h, c, items)["followups"], reconcile(h, c, items)["followups"])
        self.assertEqual(h.created, 1)
        h.issues[0]["state"] = "closed"
        with self.assertRaises(ValueError):
            reconcile(h, c, items)
        self.assertEqual(h.created, 1)

    def test_unmerged_candidate_cannot_create_followup(self):
        class Host:
            def read_main(self, c):
                return {"contained": False}

        with self.assertRaises(ValueError):
            reconcile(Host(), None, [item(1, "done", "a")])


if __name__ == "__main__":
    unittest.main()
