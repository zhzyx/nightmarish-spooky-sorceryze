import hashlib
import unittest

from wenqu import (
    build_ai_index,
    classify,
    export_markdown,
    merge_offline,
    normalize_markdown,
    search,
)

REQUIREMENT_MARKDOWN = """---
request_id: req-1
kind: requirement
lang: zh
---

# 天璇首切片

## 目标

注册后能创建文档并建工单。

## 验收

- [[doc-1]]
- [[doc-2]]
"""


def frontmatter(markdown: str) -> dict[str, str]:
    """解析文曲导出的简单 frontmatter（键值行）。"""
    lines = markdown.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    result: dict[str, str] = {}
    for line in lines[1:end]:
        key, value = line.split(": ", 1)
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        result[key] = value
    return result


class AiIndexTests(unittest.TestCase):
    def test_headings_anchors_links_and_summary(self):
        index = build_ai_index(REQUIREMENT_MARKDOWN)
        self.assertEqual([heading["text"] for heading in index["headings"]], ["天璇首切片", "目标", "验收"])
        self.assertEqual([heading["anchor"] for heading in index["headings"]], ["天璇首切片", "目标", "验收"])
        self.assertEqual([heading["level"] for heading in index["headings"]], [1, 2, 2])
        self.assertEqual(index["links"], ["doc-1", "doc-2"])
        self.assertEqual(index["summary"], "注册后能创建文档并建工单。")
        self.assertEqual(index["language"], "zh")
        self.assertGreater(index["estimated_tokens"], 0)
        self.assertEqual(len(index["content_hash"]), 64)

    def test_duplicate_and_explicit_anchors_are_stable(self):
        markdown = "# 说明\n\n## 说明\n\n## 固定标题 {#custom-anchor}\n"
        index = build_ai_index(markdown)
        self.assertEqual(
            [heading["anchor"] for heading in index["headings"]],
            ["说明", "说明-1", "custom-anchor"],
        )
        self.assertEqual(index["headings"][-1]["text"], "固定标题")
        self.assertEqual(build_ai_index(normalize_markdown(markdown))["headings"], index["headings"])

    def test_fenced_code_is_not_a_heading(self):
        markdown = "# 标题\n\n```python\n# 不是标题\n```\n"
        self.assertEqual([heading["text"] for heading in build_ai_index(markdown)["headings"]], ["标题"])
        self.assertEqual(normalize_markdown(markdown), "# 标题 {#标题}\n\n```python\n# 不是标题\n```\n")

    def test_content_hash_uses_normalized_markdown(self):
        index = build_ai_index(REQUIREMENT_MARKDOWN)
        expected = hashlib.sha256(normalize_markdown(REQUIREMENT_MARKDOWN).encode("utf-8")).hexdigest()
        self.assertEqual(index["content_hash"], expected)
        self.assertEqual(
            index["content_hash"], build_ai_index(REQUIREMENT_MARKDOWN.replace("\n", "\r\n"))["content_hash"]
        )
        self.assertEqual(index["content_hash"], build_ai_index(REQUIREMENT_MARKDOWN + "\n\n")["content_hash"])
        changed = build_ai_index(REQUIREMENT_MARKDOWN.replace("注册后", "登录后"))
        self.assertNotEqual(index["content_hash"], changed["content_hash"])

    def test_language_hint_and_empty_document(self):
        self.assertEqual(build_ai_index("# Design\n\nArchitecture and acceptance criteria.\n")["language"], "en")
        self.assertEqual(build_ai_index("# 需求\n\nDesign and architecture.\n")["language"], "mixed")
        empty = build_ai_index("")
        self.assertEqual(empty["headings"], [])
        self.assertEqual(empty["links"], [])
        self.assertEqual(empty["summary"], "")
        self.assertEqual(empty["estimated_tokens"], 0)
        self.assertEqual(empty["content_hash"], hashlib.sha256(b"").hexdigest())


class ClassifyTests(unittest.TestCase):
    def test_multi_label_fixed_order(self):
        self.assertEqual(classify("# 需求\n\n设计与验收如下。\n"), ["requirement", "design", "zh"])
        self.assertEqual(classify("Ticket: fix bug on branch with commit"), ["ticket", "code", "en"])
        self.assertEqual(classify("工单缺陷：修复分支与提交"), ["ticket", "code", "zh"])
        # 需求正文提到“建工单”，规则归类同时给出 requirement 与 ticket。
        self.assertEqual(classify(REQUIREMENT_MARKDOWN), ["requirement", "ticket", "zh"])

    def test_frontmatter_keys_do_not_force_english(self):
        markdown = "---\ntitle: 中文标题\nlang: zh\n---\n\n正文内容。\n"
        self.assertEqual(classify(markdown), ["zh"])
        self.assertEqual(classify(""), [])

    def test_classification_is_deterministic(self):
        text = "需求、设计、工单、分支与 commit"
        self.assertEqual(classify(text), classify(text))
        self.assertEqual(classify(text), ["requirement", "design", "ticket", "code", "zh", "en"])


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {"id": "doc-body", "title": "运维手册", "body_md": "# 说明\n\n离线合并需要处理冲突。"},
            {"id": "doc-title", "title": "离线合并", "body_md": "处理离线草稿。"},
            {"id": "doc-heading", "title": "指南", "body_md": "# 离线合并\n\n按行合并。"},
            {"id": "doc-none", "title": "其他", "body_md": "无关内容。"},
        ]

    def test_ranking_prefers_title_then_heading_then_body(self):
        results = search(self.documents, "离线合并")
        self.assertEqual([item["id"] for item in results], ["doc-title", "doc-heading", "doc-body"])
        self.assertTrue(all(set(item) == {"id", "score", "snippet"} for item in results))
        self.assertGreater(results[0]["score"], results[1]["score"])
        self.assertGreater(results[1]["score"], results[2]["score"])
        self.assertIn("离线", results[0]["snippet"])

    def test_empty_query_and_no_match(self):
        self.assertEqual(search(self.documents, ""), [])
        self.assertEqual(search(self.documents, "   "), [])
        self.assertEqual(search(self.documents, "量子计算"), [])

    def test_body_alias_and_determinism(self):
        documents = [{"id": "alt", "title": "", "body": "离线合并说明。"}]
        self.assertEqual(search(documents, "离线合并")[0]["id"], "alt")
        self.assertEqual(search(self.documents, "离线合并"), search(self.documents, "离线合并"))


class ExportTests(unittest.TestCase):
    def test_canonical_frontmatter_and_body(self):
        document = {
            "id": "doc_1",
            "title": "离线合并方案",
            "body_md": "# 方案\n\n- [[doc-9]]\n",
            "lang": "zh",
            "kind": "design",
            "version": 3,
        }
        exported = export_markdown(document)
        self.assertTrue(
            exported.startswith("---\nid: doc_1\ntitle: 离线合并方案\nlang: zh\nkind: design\nversion: 3\n---\n\n")
        )
        self.assertIn("# 方案 {#方案}", exported)
        self.assertIn("- [[doc-9]]", exported)
        self.assertEqual(exported.count("---"), 2)
        self.assertTrue(exported.endswith("\n"))
        self.assertFalse(exported.endswith("\n\n"))

    def test_requirement_frontmatter_is_preserved(self):
        document = {
            "id": "doc_2",
            "title": "天璇首切片",
            "body_md": REQUIREMENT_MARKDOWN,
            "lang": "zh",
            "kind": "requirement",
            "version": 1,
            "request_id": "req-1",
        }
        exported = export_markdown(document)
        meta = frontmatter(exported)
        self.assertEqual(meta["id"], "doc_2")
        self.assertEqual(meta["title"], "天璇首切片")
        self.assertEqual(meta["lang"], "zh")
        self.assertEqual(meta["kind"], "requirement")
        self.assertEqual(meta["version"], "1")
        self.assertEqual(meta["request_id"], "req-1")
        self.assertEqual(exported.count("---"), 2)

    def test_body_frontmatter_fills_missing_metadata_and_quotes_values(self):
        markdown = '---\nid: doc_3\ntitle: "需求: 离线合并"\nlang: en\nkind: doc\nversion: 2\n---\n\n# Old\n'
        exported = export_markdown({"body_md": markdown})
        meta = frontmatter(exported)
        self.assertEqual(meta["id"], "doc_3")
        self.assertEqual(meta["title"], "需求: 离线合并")
        self.assertEqual(meta["lang"], "en")
        self.assertEqual(meta["kind"], "doc")
        self.assertEqual(meta["version"], "2")
        self.assertIn("# Old {#old}", exported)

    def test_frontmatter_scalars_stay_single_line(self):
        document = {
            "id": "doc_5",
            "title": "第一行\n第二行  ",
            "body_md": "内容。\n",
            "lang": "zh",
            "kind": "doc",
            "version": 1,
        }
        exported = export_markdown(document)
        self.assertEqual(frontmatter(exported)["title"], "第一行 第二行")
        frontmatter_block = exported.split("---", 2)[1]
        self.assertEqual(len(frontmatter_block.strip().splitlines()), 5)

    def test_export_is_idempotent(self):
        document = {
            "id": "doc_4",
            "title": "规范导出",
            "body_md": "# 正文\n\n内容。\n",
            "lang": "zh",
            "kind": "doc",
            "version": 2,
        }
        exported = export_markdown(document)
        self.assertEqual(export_markdown({**document, "body_md": exported}), exported)


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.base = "# 文档\n\n第一行\n第二行\n第三行\n"

    def test_clean_three_way_merge_keeps_both_sides(self):
        local = self.base.replace("第一行", "第一行（本地）")
        remote = self.base.replace("第三行", "第三行（远端）")
        merged, conflicts = merge_offline(self.base, local, remote)
        self.assertEqual(conflicts, [])
        self.assertIn("第一行（本地）", merged)
        self.assertIn("第二行", merged)
        self.assertIn("第三行（远端）", merged)
        self.assertNotIn("<<<<<<<", merged)
        self.assertTrue(merged.endswith("\n"))
        self.assertFalse(merged.endswith("\n\n"))

    def test_overlapping_edits_produce_markers_and_conflicts(self):
        local = self.base.replace("第二行", "第二行（本地）")
        remote = self.base.replace("第二行", "第二行（远端）")
        merged, conflicts = merge_offline(self.base, local, remote)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("conflict", conflicts[0])
        self.assertIn("<<<<<<< local", merged)
        self.assertIn("=======", merged)
        self.assertIn(">>>>>>> remote", merged)
        self.assertIn("第二行（本地）", merged)
        self.assertIn("第二行（远端）", merged)
        self.assertLess(merged.index("<<<<<<< local"), merged.index("======="))
        self.assertLess(merged.index("======="), merged.index(">>>>>>> remote"))

    def test_identical_changes_and_same_deletions_merge_cleanly(self):
        local = remote = self.base.replace("第二行", "第二行（共同）")
        merged, conflicts = merge_offline(self.base, local, remote)
        self.assertEqual(conflicts, [])
        self.assertIn("第二行（共同）", merged)

        deletion = "# 文档\n\n第一行\n第三行\n"
        merged, conflicts = merge_offline(self.base, deletion, deletion)
        self.assertEqual(conflicts, [])
        self.assertNotIn("第二行", merged)

    def test_clean_side_and_insertion_conflict(self):
        merged, conflicts = merge_offline(self.base, self.base, self.base.replace("第三行", "第三行（远端）"))
        self.assertEqual(conflicts, [])
        self.assertIn("第三行（远端）", merged)

        merged, conflicts = merge_offline("a\nb\n", "a\nb\nlocal\n", "a\nb\nremote\n")
        self.assertEqual(len(conflicts), 1)
        self.assertIn("<<<<<<< local", merged)
        self.assertIn("local", merged)
        self.assertIn("remote", merged)


class NormalizeTests(unittest.TestCase):
    def test_normalizes_eol_spaces_and_final_newline(self):
        raw = "\ufeff# 标题  \r\n\r\n正文\t\r\n\r\n\r\n"
        once = normalize_markdown(raw)
        self.assertEqual(once, "# 标题 {#标题}\n\n正文\n")
        self.assertEqual(normalize_markdown(once), once)
        self.assertNotIn("\r", once)
        self.assertTrue(once.endswith("\n"))
        self.assertFalse(once.endswith("\n\n"))
        self.assertTrue(all(line == line.rstrip() for line in once.splitlines()))

    def test_heading_anchors_are_unique_and_idempotent(self):
        raw = "# 说明\n\n## 说明\n\n## 固定标题 {#stable}\n"
        once = normalize_markdown(raw)
        self.assertEqual(once, "# 说明 {#说明}\n\n## 说明 {#说明-1}\n\n## 固定标题 {#stable}\n")
        self.assertEqual(normalize_markdown(once), once)
        self.assertEqual(once.count("{#说明}"), 1)

    def test_fenced_code_and_empty_documents(self):
        fenced = "```\n# 代码注释\n```\n"
        self.assertEqual(normalize_markdown(fenced), fenced)
        self.assertEqual(normalize_markdown(fenced + "\n\n"), fenced)
        self.assertEqual(normalize_markdown("  \n\n"), "")
        self.assertEqual(normalize_markdown("plain\n"), "plain\n")


if __name__ == "__main__":
    unittest.main()
