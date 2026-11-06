"""Regression cases for reading a real work order's published evidence."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from flow_views import brief, completed_revision, recovery_receipts, turnaround


class FlowViews(unittest.TestCase):
    @staticmethod
    def comment(n, text, marker="", heading=""):
        return {
            "id": n,
            "html_url": f"https://example.test/#c{n}",
            "created_at": "2026-11-01T10:00:00Z",
            "user": {"login": "writer"},
            "author_association": "COLLABORATOR",
            "body": f"<!-- requirement-revision:{'a' * 64}{marker} -->\n\nYanshi / ClarifyFeature 澄清更新{heading}\n\n{text}",
        }

    def test_partial_revision_and_conflicting_segment(self):
        part = self.comment(1, "first", "-part-1", "（1/2）")
        end = self.comment(2, "second", "", "（2/2）")
        self.assertIsNone(completed_revision([part]))
        self.assertEqual(completed_revision([end, part])[0], "firstsecond")
        self.assertIsNone(completed_revision([part, end, self.comment(3, "different", "-part-1", "（1/2）")]))
        self.assertIsNone(completed_revision([part, dict(end, author_association="NONE")]))

    def test_legacy_revision_and_dependencies_are_distinct_from_children(self):
        issue = {
            "html_url": "https://example.test/1",
            "number": 1,
            "title": "位置",
            "body": "## 待确认\n- 原问题",
            "comments": 1,
            "state_reason": None,
            "state": "open",
            "labels": [],
            "assignees": [],
        }
        child = {"title": "child", "state": "open", "state_reason": None, "html_url": "child-url"}
        tables = {
            "repos/a/b/issues/1": issue,
            "repos/a/b/issues/1/comments?per_page=100": [[self.comment(1, "新目标\n\n验收：\n- 新验收")]],
            "repos/a/b/issues/1/sub_issues?per_page=100": [[child]],
            "repos/a/b/issues/1/dependencies/blocked_by?per_page=100": [[dict(child, title="predecessor")]],
        }
        result = brief(lambda cmd, url, *args: json.dumps(tables[url]), Path.cwd(), "a/b", 1)
        for value in ("原问题", "新验收", "旧修订未提供", "predecessor", "child-url"):
            self.assertIn(value, result)

    def test_cohorts_use_created_after_release_and_snapshot_close(self):
        release = datetime(2026, 11, 2, tzinfo=timezone.utc)
        original = {
            "number": 1,
            "state": "closed",
            "state_reason": "completed",
            "created_at": "2026-11-01T00:00:00Z",
            "closed_at": "2026-11-04T00:00:00Z",
            "labels": [{"name": "type:bug"}],
        }
        after = dict(original, number=2, created_at="2026-11-03T00:00:00Z")
        rows = [
            [original, after, dict(after, number=3, state_reason="not_planned"), dict(after, number=4, pull_request={})]
        ]
        baseline = {
            "closed_issues": [
                {"issue": 1, "closed_at": "2026-11-01T01:00:00Z"},
                {"issue": 5, "closed_at": "2026-11-01T01:00:00Z"},
            ]
        }
        result = turnaround(
            lambda cmd, url, *args: json.dumps([[]] if "/comments?" in url else rows), "a/b", baseline, release
        )
        group = result["grouped_by_current_type"]["type:bug"]
        self.assertEqual((group["baseline"]["median_minutes"], group["after"]["issues"]), (60, [2]))
        self.assertEqual(result["unavailable_baseline_issues"], [5])

    def test_recovery_requires_exact_source_issue_bot_and_candidate(self):
        release = datetime(2026, 11, 1, tzinfo=timezone.utc)
        proof = {
            "original_issue": 7,
            "state": "operation_reverified",
            "old_candidate": "f" * 40,
            "new_candidate": "f" * 40,
        }
        row = self.comment(1, "")
        row.update(
            body="<!-- kuafu-recovery:exact-run-1-attempt-1 -->\n\n```json\n" + json.dumps(proof) + "\n```",
            user={"login": "github-actions[bot]"},
            issue_url="https://api.github.com/repos/a/b/issues/7",
        )
        copies = [row, dict(row, issue_url=row["issue_url"] + "8"), dict(row, user={"login": "untrusted"})]
        self.assertEqual(len(recovery_receipts(copies, "a/b", release)), 1)
