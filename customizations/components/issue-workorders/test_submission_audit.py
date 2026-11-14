from __future__ import annotations

import unittest

import submission_audit as audit


class SubmissionAuditTests(unittest.TestCase):
    def test_five_tier_diff_classification_and_mandatory_ci(self) -> None:
        reviewed = {"apps/tianxuan/app/page.tsx", "customizations/components/tianxuan/server/api.py"}

        tier0 = audit.classify_submission_diff(
            [("design-docs/spec.md", True), ("gonggong-diting-data/events/gonggong-workspace/r/e.json", False)],
            reviewed,
        )
        self.assertEqual(tier0["tier"], "tier0_docs_telemetry")
        self.assertFalse(tier0["yanluo_requirements"]["independent_review_required"])
        self.assertFalse(tier0["yanluo_requirements"]["full_windows_editor_ci_required"])

        tier1 = audit.classify_submission_diff(
            [("apps/tianxuan/app/page.tsx", True), ("customizations/components/tianxuan/server/api.py", True)],
            reviewed,
        )
        self.assertEqual(tier1["tier"], "tier1_isolated_host")
        self.assertTrue(tier1["yanluo_requirements"]["independent_review_required"])
        self.assertFalse(tier1["yanluo_requirements"]["full_windows_editor_ci_required"])
        self.assertIn("Module and web tests", tier1["yanluo_requirements"]["mandatory_ci_checks"])

        # Unreviewed new file in apps/tianxuan escalates to tier3 until added to reviewed host inputs.
        unreviewed = audit.classify_submission_diff([("apps/tianxuan/app/new.tsx", False)], reviewed)
        self.assertEqual(unreviewed["tier"], "tier3_shared_engine_or_ci")
        self.assertTrue(unreviewed["yanluo_requirements"]["full_windows_editor_ci_required"])

        tier2 = audit.classify_submission_diff([("modules/bmp/image_loader_bmp.cpp", True)], reviewed)
        self.assertEqual(tier2["tier"], "tier2_scoped_engine_impl")
        self.assertTrue(tier2["yanluo_requirements"]["scoped_engine_ci_required"])
        self.assertFalse(tier2["yanluo_requirements"]["full_windows_editor_ci_required"])

        tier3 = audit.classify_submission_diff(
            [("editor/docks/ai_chat_delivery.cpp", True), ("editor/docks/ai_chat_delivery_receipt.h", True)], reviewed
        )
        self.assertEqual(tier3["tier"], "tier3_shared_engine_or_ci")
        self.assertTrue(tier3["yanluo_requirements"]["full_windows_editor_ci_required"])
        self.assertIn("🏁 Windows / Editor (target=editor)", tier3["yanluo_requirements"]["mandatory_ci_checks"])

        tier4 = audit.classify_submission_diff(
            [("customizations/components/tianxuan/build-impact.json", True)], reviewed
        )
        self.assertEqual(tier4["tier"], "tier4_governance_or_admission")
        self.assertTrue(tier4["yanluo_requirements"]["governance_admission_required"])
        self.assertTrue(tier4["yanluo_requirements"]["module_impact_check_required"])

    def test_ci_deduplication_prefers_latest_rerun_and_enforces_mandatory_checks(self) -> None:
        checks = [
            {
                "__typename": "CheckRun",
                "name": "🏁 Windows / Editor (target=editor)",
                "workflowName": "🔗 GHA",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "completedAt": "2026-11-14T00:10:00Z",
            },
            {
                "__typename": "CheckRun",
                "name": "🏁 Windows / Editor (target=editor)",
                "workflowName": "🔗 GHA",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-11-14T00:25:00Z",
            },
            {
                "__typename": "CheckRun",
                "name": "📊 Static checks",
                "workflowName": "🔗 GHA",
                "status": "COMPLETED",
                "conclusion": "SKIPPED",
                "completedAt": "2026-11-14T00:05:00Z",
            },
            {
                "__typename": "CheckRun",
                "name": "📊 Static checks / Code style, file formatting, and docs",
                "workflowName": "🔗 GHA",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-11-14T00:06:00Z",
            },
            {
                "__typename": "CheckRun",
                "name": "issue-association",
                "workflowName": "GongGong Issue association",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-11-14T00:05:30Z",
            },
        ]
        profile = audit.classify_submission_diff([("editor/docks/ai_chat_dock.h", True)])
        verified = audit.verify_ci_rollup(checks, audit_profile=profile)
        self.assertEqual(len(verified), 4)

        # Mandatory check skipped instead of executed must be rejected.
        skipped_editor = [
            *checks[:-4],
            {
                "__typename": "CheckRun",
                "name": "🏁 Windows / Editor (target=editor)",
                "workflowName": "🔗 GHA",
                "status": "COMPLETED",
                "conclusion": "SKIPPED",
                "completedAt": "2026-11-14T00:30:00Z",
            },
            checks[3],
            checks[4],
        ]
        with self.assertRaisesRegex(ValueError, "Mandatory tier CI check was skipped"):
            audit.verify_ci_rollup(skipped_editor, audit_profile=profile)

    def test_scope_digest_tolerates_coordination_headers_but_detects_requirement_edits(self) -> None:
        canonical_body = "<!-- gonggong-request:demo-20261114 -->\n\n# Goal\n\n- [ ] Item A\n"
        pinned = audit.scope_digest(canonical_body, normalized=True)
        with_coordination = (
            "<!-- yanluo-coordination-20261114 -->\n## Window\nWaiting for CI\n\n---\n\n"
            + canonical_body
            + "\n<!-- gonggong-host-git:Sail-Li -->\n"
        )
        self.assertTrue(audit.scope_digest_matches(with_coordination, pinned))
        self.assertTrue(audit.scope_digest_matches(with_coordination, audit.scope_digest(with_coordination)))
        altered_scope = with_coordination.replace("Item A", "Item B")
        self.assertFalse(audit.scope_digest_matches(altered_scope, pinned))

    def test_multi_account_queue_planner_separates_accounts_and_schedules_waves(self) -> None:
        main_sha = "m" * 40
        prs = [
            {
                "number": 101,
                "writer": "alice",
                "issue": 80,
                "request_id": "req-80",
                "base": "a" * 40,
                "write_paths": ["apps/tianxuan/a.tsx"],
                "overlapping_write_paths": [],
                "ci_state": "SUCCESS",
                "mergeable": "MERGEABLE",
                "updated_at": "2026-11-14T00:01:00Z",
            },
            {
                "number": 105,
                "writer": "alice",
                "issue": 80,
                "request_id": "req-80",
                "base": main_sha,
                "write_paths": ["apps/tianxuan/a.tsx"],
                "overlapping_write_paths": [],
                "ci_state": "SUCCESS",
                "mergeable": "MERGEABLE",
                "updated_at": "2026-11-14T00:10:00Z",
            },
            # Different account on the SAME issue #80 is NOT marked superseded!
            {
                "number": 106,
                "writer": "bob",
                "issue": 80,
                "request_id": "req-80",
                "base": main_sha,
                "write_paths": ["engine_next/runtime.cpp"],
                "overlapping_write_paths": [],
                "ci_state": "SUCCESS",
                "mergeable": "MERGEABLE",
                "updated_at": "2026-11-14T00:05:00Z",
            },
            # Carries path overlap with alice's #105 -> placed in wave 2!
            {
                "number": 107,
                "writer": "carol",
                "issue": 90,
                "request_id": "req-90",
                "base": main_sha,
                "write_paths": ["apps/tianxuan/a.tsx", "apps/tianxuan/c.tsx"],
                "overlapping_write_paths": [],
                "ci_state": "PENDING",
                "mergeable": "MERGEABLE",
                "updated_at": "2026-11-14T00:08:00Z",
            },
        ]
        plan = audit.plan_submission_queue(prs, main_sha)
        self.assertEqual(plan["accounts"], ["alice", "bob", "carol"])
        self.assertEqual(plan["superseded_prs"], [{"pr": 101, "writer": "alice", "issue": 80, "superseded_by": 105}])
        self.assertEqual(plan["ready_to_merge"], [105, 106])
        self.assertEqual(plan["merge_waves"], [[105, 106], [107]])
        self.assertEqual(len(plan["pairwise_conflicts"]), 1)
        self.assertEqual(plan["pairwise_conflicts"][0]["paths"], ["apps/tianxuan/a.tsx"])


if __name__ == "__main__":
    unittest.main()
