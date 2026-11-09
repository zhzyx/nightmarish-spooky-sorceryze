"""Exercise the module onboarding gate against actual Git trees and index blobs."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from issue_gate import check_module_build_impact


class ModuleImpactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("modules/old/SCsub", "old module")
        self.write("tools/service/main.py", "print('existing tool')")
        self.git("commit", "-qm", "base")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", self.root, *args], text=True).strip()

    def write(self, path, data):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        self.git("add", path)

    def test_new_module_and_real_candidate_bytes(self):
        directory = "modules/example"
        entry = directory + "/SCsub"
        self.write(entry, "initial")
        with self.assertRaisesRegex(ValueError, "missing regular candidate"):
            check_module_build_impact(self.root, "HEAD")
        report = "data-collection/probe.json"
        self.write(
            directory + "/build-impact.json",
            dict(
                placement="native",
                reason="Linked into editor",
                host_contract="editor module ABI",
                rollback="restore preceding engine",
                evidence=report,
            ),
        )
        proof = dict(
            input_blobs={entry: self.git("rev-parse", ":" + entry)},
            checks={
                "native_invalidation": {"command": "native fixture", "observed": "new object signature", "passed": True}
            },
        )
        self.write(report, proof)
        self.assertEqual(check_module_build_impact(self.root, "HEAD"), [directory])
        self.write(directory + "/logic.cpp", "int value = 1;")
        with self.assertRaisesRegex(ValueError, "every tested module input"):
            check_module_build_impact(self.root, "HEAD")
        proof["input_blobs"][directory + "/logic.cpp"] = self.git("rev-parse", ":" + directory + "/logic.cpp")
        self.write(report, proof)
        # A file changed after a successful run must not borrow its old receipt.
        self.write(entry, "updated")
        with self.assertRaisesRegex(ValueError, "tested input differs"):
            check_module_build_impact(self.root, "HEAD")

    def test_registry_can_add_an_existing_folder(self):
        self.write(
            "customizations/platforms/components.json", {"components": [{"id": "tool", "path": "tools/service"}]}
        )
        with self.assertRaisesRegex(ValueError, "tools/service/build-impact.json"):
            check_module_build_impact(self.root, "HEAD")

    def test_package_rollback_evidence_and_equal_executable(self):
        root = "samples/project/addons/scene_ui"
        entry = root + "/plugin.cfg"
        self.write(entry, "plugin")
        self.write(
            root + "/build-impact.json",
            dict(
                placement="runtime_package",
                reason="External UI",
                host_contract="v1",
                rollback="select earlier package",
                evidence="data-collection/ui.json",
            ),
        )
        run = {"command": "headless UI probe", "observed": "layout matched", "passed": True}
        checks = {k: dict(run) for k in ("same_binary_update", "incompatible_rejection", "rollback")}
        swap = checks["same_binary_update"]
        swap.update(
            before_executable="a" * 64, after_executable="b" * 64, before_package="c" * 64, after_package="d" * 64
        )
        proof = dict(input_blobs={entry: self.git("rev-parse", ":" + entry)}, checks=checks)
        self.write("data-collection/ui.json", proof)
        with self.assertRaisesRegex(ValueError, "one executable"):
            check_module_build_impact(self.root, "HEAD")
        swap["after_executable"] = swap["before_executable"]
        checks["rollback"]["passed"] = False
        self.write("data-collection/ui.json", proof)
        with self.assertRaisesRegex(ValueError, "rollback"):
            check_module_build_impact(self.root, "HEAD")
        checks["rollback"]["passed"] = True
        self.write("data-collection/ui.json", proof)
        self.assertEqual(check_module_build_impact(self.root, "HEAD"), [root])

    def test_prior_modules_and_archived_evidence_are_untouched(self):
        self.write("modules/old/SCsub", "updated")
        self.write("archive/sample/build-impact.json", {})
        self.assertEqual(check_module_build_impact(self.root, "HEAD"), [])
