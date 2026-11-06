"""Publication preserves existing files and rolls back its own report on failure."""

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from character_publish import publish_pair
from interop_publish import publish as publish_artifact


class CharacterPublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.staged = self.root / "staged.glb"
        document = b'{"asset":{"version":"2.0"}}'
        document += b" " * (-len(document) % 4)
        self.staged.write_bytes(
            struct.pack("<4sII", b"glTF", 2, 20 + len(document))
            + struct.pack("<I4s", len(document), b"JSON")
            + document
        )
        self.report = self.root / "staged.json"
        self.report.write_text(
            json.dumps({"schema_version": 1, "scope": "body_skin_and_final_body_animation"}),
            encoding="utf-8",
        )
        self.target = self.root / "character.glb"
        self.sidecar = self.root / "character.glb.report.json"

    def publish(self) -> None:
        publish_pair(str(self.staged), str(self.report), str(self.target))

    def test_pair_success_and_existing_files_preserved(self) -> None:
        self.publish()
        original = self.target.read_bytes()
        report = self.sidecar.read_bytes()
        self.assertEqual(json.loads(report)["artifact_sha256"], hashlib.sha256(original).hexdigest())
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(self.sidecar.read_bytes(), report)

    def test_invalid_glb_rolls_back_own_report(self) -> None:
        self.staged.write_bytes(b"invalid")
        with self.assertRaises(ValueError):
            self.publish()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.sidecar.exists())

    def test_racing_existing_target_is_preserved(self) -> None:
        def collide(_staged: Path, target: Path) -> None:
            target.write_bytes(b"other publisher")
            raise FileExistsError("simulated exclusive destination race")

        with patch("character_publish.publish", side_effect=collide):
            with self.assertRaises(FileExistsError):
                self.publish()
        self.assertEqual(self.target.read_bytes(), b"other publisher")
        self.assertFalse(self.sidecar.exists())

    def test_caller_stage_changes_do_not_change_snapshot(self) -> None:
        original = self.staged.read_bytes()

        def mutate_caller(snapshot: Path, target: Path) -> None:
            self.staged.write_bytes(b"replaced caller stage")
            publish_artifact(snapshot, target)

        with patch("character_publish.publish", side_effect=mutate_caller):
            self.publish()
        self.assertEqual(self.target.read_bytes(), original)
        report = json.loads(self.sidecar.read_text(encoding="utf-8"))
        self.assertEqual(report["artifact_sha256"], hashlib.sha256(original).hexdigest())


if __name__ == "__main__":
    unittest.main()
