import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import issue_gate as gate


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.issue = {
            "number": 6,
            "html_url": "https://github.com/test/repo/issues/6",
            "state": "open",
            "body": "<!-- gonggong-request:req-6 -->",
            "labels": [{"name": n} for n in ("type:development", "status:in-progress", "workspace:gonggong")],
        }

    def intake(self, value=None, number=6, tenant="test"):
        with (
            patch.object(
                gate.work_items,
                "config",
                return_value=({"repository": "test/repo", "tenant_id": "test"}, [{"name": "type:development"}]),
            ),
            patch.object(gate, "check_repository"),
            patch.object(gate.work_items, "gh", return_value=json.dumps(value or self.issue)),
        ):
            return gate.intake(self.root, number, "req-6", tenant)

    def test_real_issue_and_rejected_bindings(self):
        self.assertEqual(self.intake()["number"], 6)
        for change in (
            {"state": "closed"},
            {"pull_request": {}},
            {"body": "<!-- gonggong-request:other -->"},
            {"labels": self.issue["labels"][:-1]},
            {"labels": [{"name": "type:development"}, {"name": "status:planned"}, {"name": "workspace:gonggong"}]},
        ):
            with self.assertRaises(ValueError):
                self.intake(dict(self.issue, **change))
        for number in (None, True, 0, "6"):
            with self.assertRaises(ValueError):
                self.intake(number=number)
        with self.assertRaises(ValueError):
            self.intake(tenant="wrong")

    def test_collection_requires_index_bytes_including_ignored_files(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "Fixture",
            ],
            check=True,
        )
        folder = self.root / "data-collection"
        folder.mkdir()
        path = folder / "receipt.json"
        path.write_text("{}")
        with self.assertRaises(ValueError):
            gate.check_collection(self.root)

        subprocess.run(["git", "-C", str(self.root), "add", "data-collection"], check=True)
        gate.check_collection(self.root)
        path.write_text('{"changed":true}')
        with self.assertRaises(ValueError):
            gate.check_collection(self.root)
        (self.root / ".gitignore").write_text("data-collection/hidden.json\n")
        subprocess.run(["git", "-C", str(self.root), "add", "data-collection/receipt.json"], check=True)
        gate.check_collection(self.root)
        (folder / "hidden.json").write_text("{}")
        with self.assertRaises(ValueError):
            gate.check_collection(self.root)

    def test_host_private_state_is_ignored_but_never_staged(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "Fixture",
            ],
            check=True,
        )
        (self.root / ".gitignore").write_text(
            "/data-collection/*.local.json\n/data-collection/*.sqlite*\n"
            "/data-collection/inbox/\n/data-collection/outbox/\n/data-collection/receipts/\n"
        )
        for name in [
            "diting.sqlite",
            "diting.sqlite-wal",
            "session.local.json",
            "inbox/event.json",
            "outbox/pending.json",
            "receipts/consumed.json",
        ]:
            path = self.root / "data-collection" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private host state")
        gate.check_collection(self.root)
        # Merely ignoring an arbitrary business receipt still does not waive delivery.
        (self.root / "data-collection/hidden.json").write_text("{}")
        with (self.root / ".gitignore").open("a") as stream:
            stream.write("/data-collection/hidden.json\n")
        with self.assertRaises(ValueError):
            gate.check_collection(self.root)
        (self.root / "data-collection/hidden.json").unlink()
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "data-collection/session.local.json"], check=True)
        with self.assertRaisesRegex(ValueError, "Host-private"):
            gate.check_collection(self.root)
        subprocess.run(
            ["git", "-C", str(self.root), "rm", "--cached", "data-collection/session.local.json"], check=True
        )
        (self.root / ".gitignore").unlink()
        with self.assertRaises(ValueError):
            gate.check_collection(self.root)

    def test_committed_collection_original_cannot_be_rewritten_even_when_staged(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        folder = self.root / "data-collection"
        folder.mkdir()
        path = folder / "receipt.json"
        path.write_text("{}")
        subprocess.run(["git", "-C", str(self.root), "add", "data-collection"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "Original receipt",
            ],
            check=True,
        )
        gate.check_collection(self.root)
        path.write_text('{"rewritten":true}')
        subprocess.run(["git", "-C", str(self.root), "add", "data-collection"], check=True)
        with self.assertRaisesRegex(ValueError, "Preserve collection"):
            gate.check_collection(self.root)


if __name__ == "__main__":
    unittest.main()
