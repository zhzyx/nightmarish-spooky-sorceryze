"""Isolated regression probes: pass a freshly rebuilt Olympus candidate root."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main(root):
    results = []
    with tempfile.TemporaryDirectory(prefix="olympus-standalone-") as temp:
        package = Path(temp) / "Olympus"
        shutil.copytree(root, package, ignore=shutil.ignore_patterns("__pycache__"))
        env = dict(
            os.environ,
            GONGGONG_FRAMEWORK_SOURCE=str(Path(temp) / "absent"),
            OLYMPUS_PYTHON=sys.executable,
            PYTHONUTF8="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        binding = package / "sync/binding.json"
        binding.write_text(
            json.dumps({
                "path_base": "olympus_framework_root",
                "source": "../absent",
                "sinan_source": {"framework": "../absent"},
            })
        )

        def probe(name, command, expected, message=None):
            run = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8")
            assert (run.returncode == 0) == expected, (name, run.stdout, run.stderr)
            if message:
                assert message in run.stdout + run.stderr, (name, run.stdout, run.stderr)
            results.append({"name": name, "passed": True, "exit_code": run.returncode})

        verify = [sys.executable, str(package / "tools/verify_framework.py")]
        probe("candidate_without_source", verify + ["--candidate"], True)
        probe(
            "update_without_source_rejected",
            [sys.executable, str(package / "sync/gonggong_sync.py"), "check", "--root", str(package)],
            False,
            "Upstream unavailable",
        )
        probe("pending_admission_rejected", verify, False, "Invalid admission")
        target = package / "README.md"
        original = target.read_bytes()
        target.write_bytes(original + b"\ntampered\n")
        probe("changed_file_rejected", verify + ["--candidate"], False, "Local distribution drift")
        target.write_bytes(original)
        extra = package / "unexpected.txt"
        extra.write_text("extra")
        probe("extra_file_rejected", verify + ["--candidate"], False, "Local distribution drift")
        extra.unlink()
        target.unlink()
        probe("missing_file_rejected", verify + ["--candidate"], False, "Local distribution drift")
        target.write_bytes(original)
        # Synthetic permits exist only in this temporary test package.
        evidence = package / "reviews/local-admission/fixture.txt"
        evidence.parent.mkdir(exist_ok=True)
        evidence.write_text("SYNTHETIC TEST ONLY; not a production approval.")
        manifest = json.loads((package / "framework-manifest.json").read_text(encoding="utf-8"))
        template = json.loads((package / "templates/review-pass.json").read_text(encoding="utf-8"))
        for agent in manifest["agents"]:
            permit = json.loads(json.dumps(template))
            permit.update(
                template=False, status="approved", event="agent_definition_change", phase="local_definition_release"
            )
            permit["subject"] = {
                "id": agent["id"],
                "scope": ["local_agent_definition_only"],
                "version_or_digest": {"version": agent["version"], "candidate_digest": agent["candidate_digest"]},
            }
            permit["review"] = {
                "olympus_framework": "pass",
                "applicable_validation": "pass",
                "independence": "independent_subagent_review",
                "evaluator_id": "synthetic-reviewer",
                "concision": {"status": "pass"},
                "evidence_refs": ["reviews/local-admission/fixture.txt"],
                "zeus": {
                    key: "pass" for key in ["purpose", "truth", "economy", "authority", "adaptation", "continuity"]
                },
            }
            permit["approval"] = {
                "approver_id": "synthetic-approver",
                "authority_ref": "test-only",
                "decision_evidence_ref": "reviews/local-admission/fixture.txt",
                "approved_at": "2026-01-01T00:00:00Z",
                "valid_until_or_task_end": "bound_candidate_only",
                "expires_at": None,
            }
            (package / agent["admission_pass"]).write_text(json.dumps(permit), encoding="utf-8")
        probe("synthetic_formal_validation_without_source", verify, True)
        mandate = Path(temp) / "mandate.json"
        mandate.write_text(
            json.dumps({"feature_id": "isolated-test", "outcome": "test context", "authority_ref": "synthetic-only"})
        )
        context = ["node", str(package / "tools/agent-context.mjs"), "athena", str(mandate)]
        probe("node_context_without_source", context, True, "Host mandate")
        lock = package / "sync/runtime-lock.json"
        record = json.loads(lock.read_text(encoding="utf-8"))
        target.write_bytes(original + b"\nresealed tamper\n")
        record["files"]["README.md"] = hashlib.sha256(target.read_bytes()).hexdigest()
        lock.write_text(json.dumps(record), encoding="utf-8")
        probe("rewritten_lock_rejected_by_candidate", verify + ["--candidate"], False, "Candidate content changed")
        probe("rewritten_lock_rejected_by_context", context, False, "Candidate content changed")
    print(json.dumps({"synthetic_only": True, "production_admission": False, "checks": results}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: test_olympus_standalone.py CANDIDATE_ROOT")
    main(Path(sys.argv[1]).resolve())
