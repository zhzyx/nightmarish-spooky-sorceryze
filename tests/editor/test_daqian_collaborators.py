import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"customizations/components/godot-host/daqian"))
import repository_access as access
import plan_store


class Membership(unittest.TestCase):
    def identity(self, membership, after="7"):
        def gh(*args):
            if args==("api","user"):
                return json.dumps({"login":"operator","id":7})
            if args==("api","user","--jq",".id"):
                return after
            self.assertIn("organization_member",args[1])
            self.assertIn("--paginate",args)
            self.assertIn("zhzyx/nightmarish-spooky-sorceryze",args[-1])
            return "\n".join(str(value) for value in membership)
        with patch.object(access.work_items,"gh",side_effect=gh):
            return access.collaborator(ROOT)

    def test_session_reuse_switch_and_restart(self):
        nonce = "a" * 32
        with tempfile.TemporaryDirectory() as tmp, patch.dict(access.os.environ, {"LOCALAPPDATA":tmp, "GH_TOKEN":"","GITHUB_TOKEN":""}), patch.object(access,"configured_login",return_value="operator") as login, patch.object(access,"refresh_collaborator",return_value={"login":"operator","user_id":"7","repo_id":"123","repo":"example/repo"}) as verify:
            actor = access.session_actor(ROOT,nonce,allow_login=True)
            self.assertEqual(access.session_actor(ROOT,nonce),actor)
            self.assertEqual(access.session_actor(ROOT,nonce,allow_login=True),actor)
            verify.assert_called_once()
            login.return_value = "another"
            with self.assertRaises(access.SessionChanged):
                access.session_actor(ROOT,nonce)
            with self.assertRaises(access.SessionChanged):
                access.session_actor(ROOT,"b"*32)

    def test_membership_on_later_page_is_bound_to_same_viewer(self):
        def response(uid,nodes,more):
            return json.dumps({"data":{"viewer":{"databaseId":uid,"login":"operator",
                "repositories":{"nodes":nodes,"pageInfo":{"hasNextPage":more,"endCursor":"next"}}}}})
        row = {"nameWithOwner":"zhzyx/nightmarish-spooky-sorceryze","databaseId":123}
        for uid in (7,8):
            with patch.object(access.work_items,"gh",side_effect=[response(7,[],True),response(uid,[row],False)]) as gh:
                if uid == 7:
                    self.assertEqual(access.refresh_collaborator(ROOT)["repo_id"],"123")
                else:
                    with self.assertRaises(access.AccessDenied):
                        access.refresh_collaborator(ROOT)
                self.assertIn("cursor=next",gh.call_args.args)

    def test_member_without_push_can_use_graph(self):
        self.assertEqual(self.identity([123])["login"],"operator")

    def test_plan_edit_permission_comes_from_membership(self):
        issue={"html_url":"https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/42","number":42,"state":"open",
               "labels":[{"name":"type:development"},{"name":"workspace:gonggong"},{"name":"status:in-progress"}],
               "title":"Readonly collaborator","body":"<!-- gonggong-request:fixture -->","updated_at":"fixture-revision"}
        actor={"login":"readonly","user_id":"7","repo_id":"123","repo":"zhzyx/nightmarish-spooky-sorceryze"}
        with patch.object(plan_store,"collaborator",return_value=actor), patch.object(access.work_items,"gh",return_value=json.dumps(issue)) as gh:
            with tempfile.TemporaryDirectory() as path, patch.object(plan_store.model_catalog,"config_dir",return_value=Path(path)):
                self.assertTrue(plan_store.read_source(ROOT,42)["can_edit"])
            gh.assert_called_once_with("api","repos/zhzyx/nightmarish-spooky-sorceryze/issues/42")

    def test_public_access_is_not_membership(self):
        with self.assertRaises(access.AccessDenied):
            self.identity([])

    def test_switched_account_denied(self):
        with self.assertRaisesRegex(access.AccessDenied,"切换"):
            self.identity([123],"8")

    def test_explicit_token_never_opens_other_account_offline_cache(self):
        with patch.dict(access.os.environ,{"GH_TOKEN":"test-only"}):
            self.assertEqual(access.configured_login(),"")


if __name__=="__main__":
    unittest.main()
