"""Offline snapshot checks use synthetic files and never change the real framework."""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("frozen_check", ROOT / "tools/check_olympus_distribution.py")
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class FrozenDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.framework = self.root / "Olympus"
        self.framework.mkdir()
        self.write("definition.md", b"Synthetic test definition. No real approval.\n")
        self.write("evidence/review.json", b'{"synthetic": true}\n')
        self.write("parse_only.py", b'raise RuntimeError("must never execute")\n')
        self.write("extensions/hermes-files/README.md", b"Independent test extension\n")
        self.write("extensions/hermes-files/hermes_files.py", b'raise RuntimeError("must never execute")\n')
        self.write("extensions/hermes-files/event.schema.json", b"{}\n")
        records = [{"path": "definition.md", "sha256": gate.digest((self.framework / "definition.md").read_bytes())}]
        candidate = gate.digest("".join(r["path"] + "\0" + r["sha256"] + "\n" for r in records).encode())
        agents = []
        for name in sorted(gate.AGENTS):
            permit = f"reviews/{name}.json"
            agents.append({
                "id": name,
                "version": "fixture",
                "candidate_digest": candidate,
                "candidate_files": ["definition.md"],
                "admission_pass": permit,
            })
            self.json(
                permit,
                {
                    "template": False,
                    "status": "approved",
                    "subject": {
                        "id": name,
                        "version_or_digest": {
                            "version": "fixture",
                            "candidate_digest": candidate,
                            "candidate_files": records,
                        },
                    },
                    "review": {
                        "evaluator_id": "fixture",
                        "independence": "fixture",
                        "evidence_refs": ["evidence/review.json"],
                    },
                    "approval": {
                        "approver_id": "fixture",
                        "authority_ref": "fixture-only",
                        "decision_evidence_ref": "evidence/review.json",
                    },
                },
            )
        self.json("framework-manifest.json", {"agents": agents})
        self.pin()

    def write(self, name, data):
        target = self.framework / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def json(self, name, value):
        self.write(name, json.dumps(value).encode())

    def pin(self):
        target = self.root / gate.REGISTRATION
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({
                "schema_version": 1,
                "scope": gate.SCOPE,
                "exemption": gate.EXEMPT,
                "files": {
                    name: gate.digest(raw)
                    for name, raw in gate.inventory(self.framework).items()
                    if not name.startswith(gate.EXEMPT)
                },
            }),
            encoding="utf-8",
        )

    def test_check_is_read_only_and_never_executes_python(self):
        before = gate.inventory(self.framework)
        result = gate.check(self.root)
        self.assertTrue(result["ok"])
        self.assertFalse(result["authority_authenticated"])
        self.assertFalse(result["agent_execution_authorized"])
        self.assertEqual(before, gate.inventory(self.framework))

    def test_corrupt_missing_and_extra_are_rejected(self):
        for operation in ("corrupt", "missing", "extra"):
            with self.subTest(operation=operation):
                target = self.framework / "definition.md"
                original = target.read_bytes()
                if operation == "corrupt":
                    target.write_bytes(b"changed")
                elif operation == "missing":
                    target.unlink()
                else:
                    self.write("unexpected.txt", b"extra")
                with self.assertRaises(ValueError):
                    gate.check(self.root)
                target.write_bytes(original)
                (self.framework / "unexpected.txt").unlink(missing_ok=True)

    def test_registration_rejects_unsafe_and_case_colliding_paths(self):
        target = self.root / gate.REGISTRATION
        original = target.read_bytes()
        for name in (
            "../escape",
            "/absolute",
            "C:/absolute",
            "a\\b",
            "a/./b",
            "a//b",
            "a/../b",
            "definition.md ",
            "DEFINITION.md",
        ):
            with self.subTest(name=name):
                lock = json.loads(original)
                lock["files"][name] = "0" * 64
                target.write_text(json.dumps(lock), encoding="utf-8")
                with self.assertRaises(ValueError):
                    gate.check(self.root)
        target.write_bytes(original)

    def test_candidate_digest_mismatch_even_after_repin(self):
        self.write("definition.md", b"changed candidate")
        self.pin()
        with self.assertRaisesRegex(ValueError, "Candidate digest"):
            gate.check(self.root)

    def test_permit_subject_and_evidence_mismatch_even_after_repin(self):
        target = self.framework / "reviews/athena.json"
        original = json.loads(target.read_bytes())
        for mutation in ("subject", "candidate", "evidence"):
            permit = json.loads(json.dumps(original))
            if mutation == "subject":
                permit["subject"]["id"] = "someone-else"
            elif mutation == "candidate":
                permit["subject"]["version_or_digest"]["candidate_digest"] = "0" * 64
            else:
                permit["approval"]["decision_evidence_ref"] = "missing.json"
            self.json("reviews/athena.json", permit)
            self.pin()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                gate.check(self.root)

    def test_bad_registered_python_and_json_are_rejected_without_execution(self):
        for name, raw in (
            ("parse_only.py", b"if broken\n"),
            ("parse_only.py", b"return 1\n"),
            ("bad.json", b"{"),
            ("bad.json", b'{"a":1,"a":2}'),
        ):
            self.write(name, raw)
            self.pin()
            with self.subTest(name=name), self.assertRaises((ValueError, SyntaxError)):
                gate.check(self.root)
            self.write("parse_only.py", b"pass\n")

    def test_hermes_exemption_does_not_hide_bad_syntax_or_missing_extension(self):
        self.write("extensions/hermes-files/hermes_files.py", b"if broken\n")
        with self.assertRaises(SyntaxError):
            gate.check(self.root)
        (self.framework / "extensions/hermes-files/hermes_files.py").unlink()
        with self.assertRaisesRegex(ValueError, "extension missing"):
            gate.check(self.root)

    def test_reparse_points_are_rejected(self):
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)):
            with self.assertRaisesRegex(ValueError, "Reparse point"):
                gate.no_link(self.framework)

    def test_symlink_is_rejected(self):
        link = self.framework / "linked"
        try:
            link.symlink_to(self.framework / "definition.md")
        except OSError as error:
            self.skipTest(f"OS does not permit symlinks: {error}")
        with self.assertRaisesRegex(ValueError, "Linked path"):
            gate.check(self.root)

    def test_node_check_clears_preload_environment_and_checks_failures(self):
        self.write("parse_only.mjs", b'throw new Error("must never execute");\n')
        self.pin()
        with patch.dict(os.environ, {"NODE_OPTIONS": "--require malicious", "NODE_PATH": "malicious"}):
            with patch.object(gate.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
                gate.check(self.root, node="trusted-node")
                self.assertEqual(run.call_args.args[0][:2], ["trusted-node", "--check"])
                self.assertNotIn("NODE_OPTIONS", run.call_args.kwargs["env"])
                self.assertNotIn("NODE_PATH", run.call_args.kwargs["env"])
            with patch.object(
                gate.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "bad syntax")
            ):
                with self.assertRaisesRegex(ValueError, "JavaScript syntax error"):
                    gate.check(self.root, node="trusted-node")

    def test_real_node_parses_without_executing_and_rejects_invalid_syntax(self):
        node = shutil.which("node")
        bundled = ROOT / "project/runtime/node/node.exe"
        if not node and bundled.is_file():
            node = str(bundled)
        if not node:
            self.skipTest("Node unavailable in this test environment")
        self.write("parse_only.mjs", b'throw new Error("must never execute");\n')
        self.pin()
        self.assertTrue(gate.check(self.root, node=node)["ok"])
        self.write("parse_only.mjs", b"const broken = ;\n")
        self.pin()
        with self.assertRaisesRegex(ValueError, "JavaScript syntax error"):
            gate.check(self.root, node=node)


if __name__ == "__main__":
    unittest.main()
