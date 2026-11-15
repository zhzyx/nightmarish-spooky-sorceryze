"""多宝仓库策略：保护分支解析、匹配与角色授权。"""

from __future__ import annotations

import unittest

from policy import (
    PolicyError,
    ProtectedBranchError,
    RoleDenied,
    ensure_branch_mutation_allowed,
    ensure_merge_allowed,
    is_protected,
    parse_protected_branches,
)


class ParseProtectedBranchesTests(unittest.TestCase):
    def test_none_and_empty_list_produce_no_patterns(self) -> None:
        self.assertEqual(parse_protected_branches(None), ())
        self.assertEqual(parse_protected_branches(""), ())
        self.assertEqual(parse_protected_branches("  ,  "), ())
        self.assertEqual(parse_protected_branches([]), ())

    def test_comma_separated_patterns_are_trimmed_deduplicated_and_ordered(self) -> None:
        self.assertEqual(
            parse_protected_branches("main, release/* ,main,hotfix/*"),
            ("main", "release/*", "hotfix/*"),
        )

    def test_invalid_patterns_are_rejected(self) -> None:
        for value in ("../main", "/main", "main/", "a" * 201, "main\x00", 42):
            with self.subTest(value=value):
                with self.assertRaises(PolicyError):
                    parse_protected_branches(value)  # type: ignore[arg-type]


class ProtectedMatchTests(unittest.TestCase):
    def test_exact_and_wildcard_patterns(self) -> None:
        patterns = ("main", "release/*")
        self.assertTrue(is_protected("main", patterns))
        self.assertTrue(is_protected("release/1.0", patterns))
        self.assertFalse(is_protected("feature/x", patterns))

    def test_matching_is_case_sensitive(self) -> None:
        self.assertFalse(is_protected("Main", ("main",)))

    def test_empty_branch_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            is_protected("", ("main",))


class MergePolicyTests(unittest.TestCase):
    def test_editor_can_merge_unprotected_branch_directly(self) -> None:
        decision = ensure_merge_allowed("feature/x", ("main",), actor_role="editor")
        self.assertEqual(decision["protected"], False)
        self.assertEqual(decision["path"], "direct")

    def test_viewer_cannot_merge(self) -> None:
        with self.assertRaises(RoleDenied):
            ensure_merge_allowed("feature/x", ("main",), actor_role="viewer")

    def test_protected_branch_rejects_direct_merge_even_for_admin(self) -> None:
        with self.assertRaises(ProtectedBranchError):
            ensure_merge_allowed("main", ("main",), actor_role="admin")
        with self.assertRaises(ProtectedBranchError):
            ensure_merge_allowed("release/1.0", ("release/*",), actor_role="editor")

    def test_protected_branch_allows_queue_merge_for_editor(self) -> None:
        decision = ensure_merge_allowed("main", ("main",), actor_role="editor", path="queue")
        self.assertEqual(decision, {"target": "main", "protected": True, "path": "queue", "actor_role": "editor"})

    def test_unknown_role_or_path_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            ensure_merge_allowed("feature/x", (), actor_role="owner")
        with self.assertRaises(PolicyError):
            ensure_merge_allowed("feature/x", (), actor_role="editor", path="bypass")


class BranchMutationPolicyTests(unittest.TestCase):
    def test_editor_can_create_and_delete_unprotected_branch(self) -> None:
        for operation in ("create", "delete"):
            decision = ensure_branch_mutation_allowed(
                "feature/x",
                ("main",),
                actor_role="editor",
                operation=operation,
            )
            self.assertEqual(decision["protected"], False)

    def test_viewer_cannot_mutate_branch(self) -> None:
        with self.assertRaises(RoleDenied):
            ensure_branch_mutation_allowed("feature/x", (), actor_role="viewer", operation="create")

    def test_only_admin_can_mutate_protected_branch(self) -> None:
        with self.assertRaises(ProtectedBranchError):
            ensure_branch_mutation_allowed("main", ("main",), actor_role="editor", operation="delete")
        decision = ensure_branch_mutation_allowed("main", ("main",), actor_role="admin", operation="delete")
        self.assertEqual(decision["protected"], True)

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            ensure_branch_mutation_allowed("main", (), actor_role="admin", operation="rename")


if __name__ == "__main__":
    unittest.main()
