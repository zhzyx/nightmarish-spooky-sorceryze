import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from relations import verify_relations


class RelationsTests(unittest.TestCase):
    def test_native_target_external_and_unavailable_fork_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            blob = subprocess.check_output(["git", "-C", temp, "hash-object", "-w", "--stdin"],
                                           input=b"abc").decode().strip()
            prefix = "github:o/r/"
            missing = "a" * 40
            rows = [
                dict(source_id=prefix+"requirement/test", kind="requirement", content={"blob": blob},
                     relations=[]),
                dict(source_id=prefix+"pull/1", kind="pull",
                     content={"head": {"sha": missing, "repo": {"full_name": "fork/r"}, "ref": "past"}},
                     relations=[prefix+"commit/"+missing, prefix+"requirement/test", prefix+"issue/2",
                                "github:else/r/issue/3", prefix+"commit/"+blob])]
            records = root / "records.jsonl"
            records.write_text("\n".join(map(json.dumps, rows)))
            report = verify_relations(records, root)
            self.assertFalse(report["complete"])
            self.assertEqual((6, 2, 1, 3), (report["checked"], report["resolved"],
                             len(report["external"]), len(report["unresolved"])))
            edge = next(x for x in report["unresolved"] if x["target"].endswith(missing))
            self.assertTrue(edge["historical_refs"][0]["fork"])
            self.assertEqual(edge["source_id"], prefix+"pull/1")


if __name__ == "__main__":
    unittest.main()
