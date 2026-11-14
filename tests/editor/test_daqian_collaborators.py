import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import plan_store
import repository_access as access

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "customizations/components/godot-host/daqian"))


class Membership(unittest.TestCase):
    def identity(self, membership, after="7"):
        def gh(*args):
            if args == ("api", "user"):
                return json.dumps({"login": "operator", "id": 7})
            if args == ("api", "user", "--jq", ".id"):
                return after
            self.assertIn("organization_member", args[1])
            self.assertIn("--paginate", args)
            self.assertIn("zhzyx/nightmarish-spooky-sorceryze", args[-1])
            return "\n".join(str(value) for value in membership)

        with patch.object(access.work_items, "gh", side_effect=gh):
            return access.collaborator(ROOT)

    def test_session_reuse_switch_and_restart(self):
        nonce = "a" * 32
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(access.os.environ, {"LOCALAPPDATA": tmp, "GH_TOKEN": "", "GITHUB_TOKEN": ""}),
            patch.object(access, "configured_login", return_value="operator") as login,
            patch.object(
                access,
                "refresh_collaborator",
                return_value={"login": "operator", "user_id": "7", "repo_id": "123", "repo": "example/repo"},
            ) as verify,
        ):
            actor = access.session_actor(ROOT, nonce, allow_login=True)
            self.assertEqual(access.session_actor(ROOT, nonce), actor)
            self.assertEqual(access.session_actor(ROOT, nonce, allow_login=True), actor)
            verify.assert_called_once()
            login.return_value = "another"
            with self.assertRaises(access.SessionChanged):
                access.session_actor(ROOT, nonce)
            with self.assertRaises(access.SessionChanged):
                access.session_actor(ROOT, "b" * 32)

    def test_membership_on_later_page_is_bound_to_same_viewer(self):
        def response(uid, nodes, more):
            return json.dumps({
                "data": {
                    "viewer": {
                        "databaseId": uid,
                        "login": "operator",
                        "repositories": {"nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": "next"}},
                    }
                }
            })

        row = {"nameWithOwner": "zhzyx/nightmarish-spooky-sorceryze", "databaseId": 123}
        for uid in (7, 8):
            with patch.object(
                access.work_items, "gh", side_effect=[response(7, [], True), response(uid, [row], False)]
            ) as gh:
                if uid == 7:
                    self.assertEqual(access.refresh_collaborator(ROOT)["repo_id"], "123")
                else:
                    with self.assertRaises(access.AccessDenied):
                        access.refresh_collaborator(ROOT)
                self.assertIn("cursor=next", gh.call_args.args)

    def test_member_without_push_can_use_graph(self):
        self.assertEqual(self.identity([123])["login"], "operator")

    def test_plan_edit_permission_comes_from_membership(self):
        issue = {
            "html_url": "https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/42",
            "number": 42,
            "state": "open",
            "labels": [{"name": "type:development"}, {"name": "workspace:gonggong"}, {"name": "status:in-progress"}],
            "title": "Readonly collaborator",
            "body": "<!-- gonggong-request:fixture -->",
            "updated_at": "fixture-revision",
        }
        actor = {"login": "readonly", "user_id": "7", "repo_id": "123", "repo": "zhzyx/nightmarish-spooky-sorceryze"}
        with (
            patch.object(plan_store, "collaborator", return_value=actor),
            patch.object(access.work_items, "gh", return_value=json.dumps(issue)) as gh,
        ):
            with (
                tempfile.TemporaryDirectory() as path,
                patch.object(plan_store.model_catalog, "config_dir", return_value=Path(path)),
            ):
                self.assertTrue(plan_store.read_source(ROOT, 42)["can_edit"])
            gh.assert_called_once_with("api", "repos/zhzyx/nightmarish-spooky-sorceryze/issues/42")

    def test_public_access_is_not_membership(self):
        with self.assertRaises(access.AccessDenied):
            self.identity([])

    def test_switched_account_denied(self):
        with self.assertRaisesRegex(access.AccessDenied, "切换"):
            self.identity([123], "8")

    def test_explicit_token_never_opens_other_account_offline_cache(self):
        with patch.dict(access.os.environ, {"GH_TOKEN": "test-only"}):
            self.assertEqual(access.configured_login(), "")

    def test_multi_account_session_cache_retains_verified_accounts_and_guards_unapproved_switch(self):
        nonce = "c" * 32
        calls = []

        def verify_refresh(_root):
            current = access.os.environ["GH_TOKEN"]
            calls.append(current)
            if current == "token-alice":
                return {
                    "login": "alice",
                    "user_id": "101",
                    "repo_id": "123",
                    "repo": "zhzyx/nightmarish-spooky-sorceryze",
                }
            return {"login": "bob", "user_id": "202", "repo_id": "123", "repo": "zhzyx/nightmarish-spooky-sorceryze"}

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(access, "refresh_collaborator", side_effect=verify_refresh),
        ):
            with patch.dict(access.os.environ, {"LOCALAPPDATA": tmp, "GH_TOKEN": "token-alice", "GONGGONG_GH": ""}):
                alice = access.session_actor(ROOT, nonce, allow_login=True)
                self.assertEqual(alice["login"], "alice")
                self.assertEqual(access.session_actor(ROOT, nonce)["user_id"], "101")
            with patch.dict(access.os.environ, {"LOCALAPPDATA": tmp, "GH_TOKEN": "token-bob", "GONGGONG_GH": ""}):
                # Mid-flight switch without explicit allow_login must still raise SessionChanged.
                with self.assertRaises(access.SessionChanged):
                    access.session_actor(ROOT, nonce, allow_login=False)
                bob = access.session_actor(ROOT, nonce, allow_login=True)
                self.assertEqual(bob["login"], "bob")
            # Switching back to alice on explicit login reuses verified multi-account cache without re-querying GitHub.
            with patch.dict(access.os.environ, {"LOCALAPPDATA": tmp, "GH_TOKEN": "token-alice", "GONGGONG_GH": ""}):
                alice_again = access.session_actor(ROOT, nonce, allow_login=True)
                self.assertEqual(alice_again["login"], "alice")
            self.assertEqual(calls, ["token-alice", "token-bob"])

    def test_fast_write_collaborator_verifies_graphql_and_rest_fallback(self):
        graphql_ok = json.dumps({
            "data": {
                "viewer": {"login": "alice", "databaseId": 101},
                "repository": {
                    "nameWithOwner": "zhzyx/nightmarish-spooky-sorceryze",
                    "databaseId": 123,
                    "viewerPermission": "WRITE",
                },
            }
        })
        with patch.object(access.work_items, "gh", return_value=graphql_ok) as gh:
            actor = access.fast_write_collaborator(ROOT)
            self.assertEqual(actor["login"], "alice")
            self.assertEqual(actor["permission"], "write")
            self.assertEqual(gh.call_count, 1)

        graphql_read = json.dumps({
            "data": {
                "viewer": {"login": "reader", "databaseId": 303},
                "repository": {
                    "nameWithOwner": "zhzyx/nightmarish-spooky-sorceryze",
                    "databaseId": 123,
                    "viewerPermission": "READ",
                },
            }
        })
        with patch.object(access.work_items, "gh", return_value=graphql_read):
            with self.assertRaises(access.AccessDenied):
                access.fast_write_collaborator(ROOT)


if __name__ == "__main__":
    unittest.main()
