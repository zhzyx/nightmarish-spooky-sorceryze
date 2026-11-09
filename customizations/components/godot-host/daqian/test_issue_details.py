"""Single-issue detail projection and optimistic local saves."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import board


class IssueDetails(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.actor = {"repo": "org/repo", "repo_id": "12", "user_id": "13"}
        self.request = {"action": "details", "number": 1, "request": "req"}
        self.path = "design-docs/spec.md"
        self.issue = self.row(1)
        self.issue["body"] = f"<!-- gonggong-request:req -->\n\n需求文档：`{self.path}`\n\n# 已发布\n#2 org/other#3"
        self.push = True
        self.enterContext(patch.object(board.work_items, "gh", side_effect=self.gh))
        self.enterContext(patch.object(board, "collaborator", return_value=self.actor))

    @staticmethod
    def row(number, repo="org/repo"):
        return {
            "number": number,
            "html_url": f"https://github.com/{repo}/issues/{number}",
            "title": f"Issue {number}",
            "state": "closed" if number in (1, 2) else "open",
        }

    def gh(self, _, endpoint, *args):
        base = "repos/org/repo/issues/1"
        pages = {
            "/sub_issues": [self.row(2)],
            "/dependencies/blocked_by": [self.row(4)],
            "/dependencies/blocking": [self.row(5)],
            "/timeline": [{"event": "cross-referenced", "source": {"issue": self.row(2)}}],
        }
        if args == ("--paginate", "--slurp"):
            return json.dumps([pages[endpoint.removeprefix(base).split("?")[0]]])
        direct = {
            base: self.issue,
            base + "/parent": self.row(6),
            "repos/org/other/issues/3": self.row(3, "org/other"),
            "repos/org/repo": {"id": 12, "full_name": "org/repo", "permissions": {"push": self.push}},
        }
        return json.dumps(direct[endpoint])

    def call(self, **updates):
        return board.issue_request(self.root, self.actor, self.request | updates)

    def test_closed_and_cross_repo_related_issues(self):
        result = self.call()
        rows = {i["title"]: i for i in result["related"]}
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows["Issue 2"]["status"], "closed")
        self.assertEqual(set(rows["Issue 2"]["relation"].split("、")), {"子工单", "反向引用", "正文引用"})
        self.assertEqual(rows["Issue 3"]["url"], "https://github.com/org/other/issues/3")
        self.assertEqual(rows["Issue 4"]["relation"], "依赖")
        self.assertEqual(rows["Issue 5"]["relation"], "被依赖")
        self.assertEqual(rows["Issue 6"]["relation"], "父工单")

    def test_published_creation_and_concurrent_update(self):
        document = self.call()["document"]
        save = dict(action="save_document", path=self.path, revision=document["revision"], markdown="新文档\n")
        local = self.call(**save)["document"]
        self.assertEqual(local["source"], "工作区")
        self.assertEqual(local["markdown"], save["markdown"])
        with self.assertRaisesRegex(ValueError, "已变更"):
            self.call(**save)
        save.update(revision=local["revision"])

        def update(value):
            try:
                return self.call(**(save | {"markdown": value}))["document"]["markdown"]
            except (ValueError, OSError):
                return None

        with ThreadPoolExecutor(2) as pool:
            values = [v for v in pool.map(update, ["甲", "乙"]) if v]
        self.assertEqual(values, [(self.root / self.path).read_text(encoding="utf-8")])

    def test_access_binding_and_path_validation(self):
        doc = self.call()["document"]
        with self.assertRaisesRegex(ValueError, "绑定"):
            self.call(request="other")
        with self.assertRaisesRegex(ValueError, "绑定"):
            self.call(action="save_document", path="design-docs/other.md", revision=doc["revision"], markdown="x")
        self.push = False
        self.assertFalse(self.call()["document"]["editable"])
        with self.assertRaisesRegex(ValueError, "权限"):
            self.call(action="save_document", path=self.path, revision=doc["revision"], markdown="x")
        for invalid in ["../x.md", "x:ads.md", "sub\\x.md", "CON.md", ". /x.md"]:
            body = self.issue["body"].replace("spec.md", invalid)
            self.assertEqual(board.design_document(self.root, body), {})

    def test_mixed_endings_survive_append_and_restore(self):
        original = b"one\ntwo\r\n"
        modified = board.document_bytes(original, "one\ntwo\nadded\n")
        self.assertTrue(modified.startswith(original))
        self.assertEqual(board.document_bytes(modified, "one\ntwo\n"), original)

    def test_legacy_request_filename(self):
        docs = self.root / "design-docs"
        docs.mkdir()
        (docs / "req.md").write_text("旧格式", encoding="utf-8")
        body = "<!-- gonggong-request:req -->\n父工单 #6"
        self.assertEqual(board.design_document(self.root, body)["markdown"], "旧格式")

    def test_native_newlines_survive_textedit(self):
        path = self.root / self.path
        path.parent.mkdir()
        path.write_bytes(b"one\r\ntwo\r\n")
        document = self.call()["document"]
        self.assertEqual(document["markdown"], "one\ntwo\n")
        self.call(action="save_document", path=self.path, revision=document["revision"], markdown="first\ntwo\n")
        self.assertEqual(path.read_bytes(), b"first\r\ntwo\r\n")


if __name__ == "__main__":
    unittest.main()
