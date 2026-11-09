import json
import shutil
import tempfile
import unittest
from pathlib import Path

from yanluo_host import ROOT, sha, verify_definition


class DefinitionTests(unittest.TestCase):
    def test_exact_release_inventory_and_rejection_of_drift(self):
        manifest_path = "data-collection/yanluo-0.1.3-candidate.json"
        manifest = json.loads((ROOT / manifest_path).read_bytes())
        registration = dict(
            id="yanluo",
            version="0.1.3",
            definition="customizations/components/yanluo/AGENT.md",
            candidate_digest=manifest["candidate_digest"],
            approval="fixture-approval.json",
        )
        approval = dict(
            subject="yanluo",
            version="0.1.3",
            decision="approved",
            candidate_digest=manifest["candidate_digest"],
            candidate_manifest=manifest_path,
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            for name in [manifest_path] + [item["path"] for item in manifest["files"]]:
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, repo / name)
            decision = repo / registration["approval"]
            decision.write_text(json.dumps(approval), encoding="utf-8")
            grant = dict(
                approval_sha256=sha(decision.read_bytes()),
                definition_digest=manifest["candidate_digest"],
                candidate_manifest_sha256=sha((repo / manifest_path).read_bytes()),
            )
            verify_definition(repo, registration, grant)
            with self.assertRaisesRegex(ValueError, "matching approval"):
                verify_definition(repo, dict(registration, version="0.1.2"), grant)
            (repo / registration["definition"]).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Approved definition drift"):
                verify_definition(repo, registration, grant)
            decision.write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "Signed record drift"):
                verify_definition(repo, registration, grant)
