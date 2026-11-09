import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import method_learning as learning


class LearningTests(unittest.TestCase):
    def setUp(self):
        learning.bind_host(learning.ROOT)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.scope = "handoff"
        self.tenant = "team-a"
        data = self.repo / "gonggong-diting-data"
        write = learning.DITING["atomic_new"]
        write(data / "dataset.json", {"origin_framework": "gonggong", "storage": "immutable_event_json"})
        self.origin = "gonggong-diting-data/events/team-a/task/correction.json"
        self.time = "2026-11-09T00:00:00Z"
        write(self.repo / self.origin, learning.DITING["event"]({
            "tenant_id": self.tenant, "request_id": "task", "schema_version": 1,
            "event_id": "correction", "kind": "correction", "occurred_at": self.time,
            "payload": {}, "agent": {"id": "fixture", "version": "1", "origin": "fixture",
                                    "definition_sha256": "0" * 64},
            "source_ref": "fixture-task", "evidence_refs": [],
        }))
        (self.repo / "receipt").write_bytes(b"result")
        self.proof = [{"path": "receipt", "sha256": hashlib.sha256(b"result").hexdigest()}]
        self.method = {"method": "Read candidate before handoff", "when": "dependency completes",
                       "counterexample": "consultation only", "trial_plan": "compare fixture outcomes"}

    def entry(self, action, details, revision, head):
        return {"origin": self.origin, "occurred_at": self.time, "scope": self.scope, "lesson": "bind",
                "previous": head, "revision": revision, "action": action, "details": details,
                "evidence": self.proof}

    def record(self, entry):
        return learning.append(self.repo, self.tenant, entry)

    def lookup(self, tenant=None, scope=None):
        return learning.recall(self.repo, tenant or self.tenant, scope or self.scope)["lessons"]

    def test_separate_framework_and_trusted_host(self):
        tools = self.repo / "installed-framework" / "tools"
        tools.mkdir(parents=True)
        entry = tools / "method_learning.py"
        shutil.copyfile(learning.__file__, entry)
        cmd = [sys.executable, str(entry)]
        subprocess.run(cmd + ["--help"], capture_output=True, check=True)
        args = ["--repo", str(self.repo), "--tenant", self.tenant, "scopes"]
        fake_adapter = self.repo / learning.ADAPTER
        fake_adapter.parent.mkdir(parents=True)
        fake_adapter.write_text("raise AssertionError('untrusted adapter loaded')")
        failed = subprocess.run(cmd + args, capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Supply --host-root", failed.stderr)
        subprocess.run(cmd + ["--host-root", str(learning.ROOT)] + args, check=True, capture_output=True)

    def test_complete_lifecycle(self):
        proposal = self.entry("propose", self.method, 1, None)
        head = self.record(proposal)["head"]
        self.assertEqual(self.lookup(), [])
        trial = self.entry("verify", {"test": "changed HEAD", "expected": "blocked", "observed": "blocked"}, 2, head)
        head = self.record(trial)["head"]
        self.assertEqual(self.lookup()[0]["head"], head)
        self.assertEqual(self.lookup("team-b"), [])
        self.assertEqual(self.lookup(scope="another"), [])
        with self.assertRaises(ValueError):
            learning.append(self.repo, "team-b", proposal)
        with self.assertRaisesRegex(ValueError, "Evidence outside tenant"):
            learning.evidence(self.repo, "team-b", [{"path": self.origin, "sha256": "0" * 64}])
        head = self.record(self.entry("applied", {"task": "next", "observed": "rechecked"}, 3, head))["head"]
        head = self.record(self.entry("counterexample", {"observed": "stale bytes at same HEAD"}, 4, head))["head"]
        self.assertEqual(self.lookup(), [])
        head = self.record(self.entry("revise", {**self.method, "method": "Also bind exact bytes"}, 5, head))["head"]
        self.assertEqual(self.lookup(), [])
        head = self.record({**trial, "revision": 6, "previous": head})["head"]
        self.assertEqual(self.lookup()[0]["method"]["method"], "Also bind exact bytes")
        self.record(self.entry("withdraw", {"reason": "retired protocol"}, 7, head))
        self.assertTrue(self.record(proposal)["idempotent"])
        self.assertEqual(self.lookup(), [])
        _, folder = learning.store_dir(self.repo, self.tenant, self.scope)
        self.assertEqual(len(learning.history(folder)), 7)

    def test_racing_trials_conflicts_and_stale_evidence(self):
        head = self.record(self.entry("propose", self.method, 1, None))["head"]
        trial = self.entry("verify", {"test": "read", "expected": "yes", "observed": "no"}, 2, head)
        with self.assertRaises(ValueError):
            self.record(trial)
        trial["details"]["observed"] = "yes"
        with self.assertRaises(ValueError):
            self.record({**trial, "previous": "wrong"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.record, [trial, trial]))
        self.assertEqual(sorted(r["idempotent"] for r in results), [False, True])
        with self.assertRaises(ValueError):
            self.record({**trial, "details": {**trial["details"], "test": "different"}})
        (self.repo / "receipt").write_bytes(b"changed")
        result = learning.recall(self.repo, self.tenant, self.scope)
        self.assertEqual(result["lessons"], [])
        self.assertEqual(len(result["unavailable"]), 1)


if __name__ == "__main__":
    unittest.main()

