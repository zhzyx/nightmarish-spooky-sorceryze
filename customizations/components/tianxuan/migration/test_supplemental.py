"""Check that a Windows text pipe cannot change historical ref transactions."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import supplemental


class HistoricalRefTests(unittest.TestCase):
    def test_dangling_commit_is_pinned_once_with_windows_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            supplemental.git(root, "remote", "add", "origin", str(root), check=True)
            tree = supplemental.git(root, "mktree", input="", check=True).stdout.strip()
            commit = supplemental.git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit-tree",
                tree,
                "-m",
                "historical pull head",
                check=True,
            ).stdout.strip()
            records = root / "records.jsonl"
            row = {"kind": "pull", "content": {"head": {"sha": commit}}, "relations": []}
            records.write_text(json.dumps(row) + "\n", encoding="utf-8")

            run = subprocess.run

            def windows_text_pipe(command, **options):
                if "update-ref" in command and isinstance(options.get("input"), str):
                    options["input"] = options["input"].replace("\n", "\r\n").encode("ascii")
                    options["text"] = False
                return run(command, **options)

            with patch("supplemental.subprocess.run", side_effect=windows_text_pipe):
                first = supplemental.supplement(records, root, str(root))
                second = supplemental.supplement(records, root, str(root))
            self.assertEqual(first["pinned_existing"], 1)
            self.assertEqual(second["pinned_existing"], 0)
            ref = "refs/migration/historical/" + commit
            self.assertEqual(supplemental.git(root, "rev-parse", ref, check=True).stdout.strip(), commit)
