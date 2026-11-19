import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from history_records import export_binary, read_attachment, read_body, record_detail, search_records
from importer import canonical, digest, import_inventory
from migration_status import publish_import


class HistoryTests(unittest.TestCase):
    def test_pinned_search_and_verified_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prefix = "github:a/b/"
            issue = prefix + "issue/14"
            attachment = prefix + "attachment/42"
            data = bytes(range(256)) * 19000
            binary = root / "binary"
            binary.write_bytes(data)
            long_body = "逐字🍀还原\n" * 10000
            records = [
                ("issue/14", {"number": 14, "title": "History search", "body": "archived"}, []),
                (
                    "issue_comment/22",
                    {"issue_url": "https://api.github.com/repos/a/b/issues/14", "body": long_body},
                    [issue],
                ),
                (
                    "issue_comment/23",
                    {"issue_url": "https://api.github.com/repos/a/b/issues/15", "body": "See #14"},
                    [prefix + "pull/15", issue],
                ),
                ("pull/15", {"number": 15, "title": "Neighbor"}, []),
                ("requirement/path", {"path": "design-docs/example.md", "blob": "a" * 40}, [issue]),
                ("attachment/42", {"url": "https://example.invalid/test"}, [issue]),
            ]
            lines = []
            counts = {}
            for key, content, edges in records:
                kind = key.split("/")[0]
                counts[kind] = counts.get(kind, 0) + 1
                lines.append(
                    canonical(
                        dict(
                            kind=kind,
                            source_id=prefix + key,
                            content=content,
                            relations=edges,
                            mode="record_only",
                            sha256=digest(canonical(content)),
                        )
                    )
                    + b"\n"
                )
            stream = b"".join(lines)
            (root / "records.jsonl").write_bytes(stream)
            report = root / "report.json"
            report.write_bytes(
                canonical(
                    dict(
                        source="a/b",
                        revision="sample",
                        counts=counts,
                        historical_policy="record_only",
                        records_sha256=digest(stream),
                    )
                )
            )
            db = root / "native.db"
            result = import_inventory(report, db, "tenant", "operator", artifacts={attachment: (binary, digest(data))})
            publish_import(db, "tenant", "project", "operator", result["module"], result["revision"])
            args = db, "tenant", "project", result["revision"]
            for query in ("#14", "History search", "design-docs/example"):
                self.assertEqual(search_records(*args, query=query)["total"], 1)
            with patch("history_records._build", side_effect=AssertionError("unnecessary index rebuild")):
                detail = record_detail(*args, issue, limit=1)
            self.assertEqual(detail["reverse"]["total"], 4)
            self.assertEqual(detail["comments"]["total"], 1)
            neighbor = record_detail(*args, prefix + "pull/15")
            self.assertEqual(neighbor["comments"]["items"][0]["source_id"], prefix + "issue_comment/23")
            self.assertEqual(len(detail["reverse"]["items"]), 1)
            self.assertTrue(detail["comments"]["items"][0]["truncated"])
            self.assertEqual(detail["record"]["content"]["body"], "archived")
            segments = []
            offset = 0
            while offset is not None:
                page = read_body(*args, prefix + "issue_comment/22", offset=offset, limit=10001)
                self.assertEqual(page["total"], len(long_body))
                segments.append(page["text"])
                offset = page["next_offset"]
            self.assertEqual("".join(segments), long_body)
            self.assertEqual(read_body(*args, issue, offset=100)["text"], "")
            with self.assertRaises(LookupError):
                read_body(db, "tenant", "hidden", result["revision"], issue)
            with self.assertRaises(ValueError):
                read_body(*args, issue, limit=16385)
            self.assertEqual(search_records(*args, offset=3)["total"], 6)
            self.assertEqual(read_attachment(*args, attachment), data)
            with self.assertRaises(ValueError):
                read_attachment(*args, attachment, max_bytes=4096)
            with self.assertRaises(LookupError):
                read_attachment(*args, issue)
            with self.assertRaises(LookupError):
                record_detail(db, "tenant", "other", result["revision"], issue)
            with self.assertRaises(LookupError):
                search_records(db, "tenant", "project", "wrong")
            out = root / "export.bin"
            self.assertEqual(export_binary(*args, attachment, out), dict(sha256=digest(data), size=len(data)))
            self.assertEqual(out.read_bytes(), data)
            with self.assertRaises(FileExistsError):
                export_binary(*args, attachment, out)

            with patch(
                "history_git.requirement_titles", return_value={"design-docs/example.md": "Unicode 标题"}
            ) as titles:
                next_catalog = import_inventory(
                    report, db, "tenant", "operator", artifacts={prefix + "history.bundle": (binary, digest(data))}
                )
                publish_import(db, "tenant", "project", "operator", next_catalog["module"], next_catalog["revision"])
                new_args = db, "tenant", "project", next_catalog["revision"]
                self.assertEqual(search_records(*new_args, query="标题")["items"][0]["path"], "design-docs/example.md")
                self.assertEqual(
                    search_records(*new_args, query="design-docs/example.md")["items"][0]["title"], "Unicode 标题"
                )
                titles.assert_called_once()
                with self.assertRaises(LookupError):
                    read_body(*args, issue)


if __name__ == "__main__":
    unittest.main()
