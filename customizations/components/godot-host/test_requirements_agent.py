"""Requirements orchestration tests; synthetic transport/GitHub, never production facts."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "requirements_test_module", Path(__file__).with_name("requirements_agent.py")
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROOT = Path(__file__).resolve().parents[3]


class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "CURRENT_FRAMEWORK.json").write_text(
            json.dumps({"path_base": "this_file_directory", "root": "framework", "manifest": "framework-manifest.json"})
        )
        for name in [
            "framework-manifest.json",
            "agents/yanshi/AGENT.md",
            "agents/yanshi/skills/clarify-feature/SKILL.md",
            "agents/yanshi/references/understanding.md",
        ]:
            dest = self.root / "framework" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "framework" / name, dest)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "remote", "add", "origin", "https://github.com/org/repo.git"], check=True
        )
        self.design = {
            "decision": "new",
            "title": "响应输入",
            "category": "requirement",
            "goal": "减少按钮延迟",
            "scope": ["输入反馈"],
            "acceptance": ["点击后显示反馈"],
            "questions": [],
        }
        self.adapter = SimpleNamespace(
            call=Mock(
                side_effect=lambda *args: {
                    "text": json.dumps(self.design),
                    "finish_reason": "stop",
                    "usage": {"input_tokens": None},
                }
            )
        )
        self.existing = {"number": 17, "state": "open", "body": "<!-- gonggong-request:bound-req -->"}
        self.comments = []

        def gh(*args):
            if args[1] == "repos/org/repo":
                return json.dumps({"full_name": "org/repo", "permissions": {"push": True}})
            if "/comments" in args[1]:
                return "[[]]"
            if args[0] == "issue":
                self.comments.append(args)
                return ""
            return json.dumps(self.existing)

        self.work = SimpleNamespace(
            config=lambda root: ({"repository": "org/repo", "tenant_id": "test"}, [{"name": "type:requirement"}]),
            gh=gh,
            request_ids=lambda body: set(re.findall(r"gonggong-request:([a-z0-9-]+)", body)),
            issue=Mock(return_value={"url": "https://github.com/org/repo/issues/18"}),
        )
        self.bridge = SimpleNamespace(
            work_items_module=lambda root: self.work,
            gh_state=Mock(return_value=("gh", None)),
            login_command=lambda gh: "gh auth login",
            host_environment=lambda root: dict(os.environ),
            issue_start=Mock(return_value={"ok": True}),
            enqueue=Mock(),
            flush=Mock(),
            outbox_lock=lambda path, deadline: nullcontext(),
        )
        self.request = {
            "outcome": "让按钮更及时反馈",
            "conversation_id": "chat-1",
            "issue_number": 0,
            "request_id": "",
            "endpoint": "http://127.0.0.1/api",
            "model": "fixture",
        }
        original_run = subprocess.run

        def run(args, **kwargs):
            if any(str(a).endswith("agent-context.mjs") for a in args):
                self.assertEqual(args[-2], "yanshi")
                mandate = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
                self.assertFalse(mandate["tools_enabled"])
                self.assertFalse(mandate["production_execution_authorized"])
                return subprocess.CompletedProcess(args, 0, "UNIT_CONTEXT_FIXTURE", "")
            return original_run(args, **kwargs)

        self.addCleanup(patch.stopall)
        patch.object(module.subprocess, "run", side_effect=run).start()
        patch.object(module, "load", return_value=self.adapter).start()

    def invoke(self):
        return module.intake(self.root, self.request, self.bridge)

    def test_new_uses_yanshi_clarify_feature_and_model_derived_content(self):
        result = self.invoke()
        self.assertTrue(result["ready"])
        context = self.adapter.call.call_args.args[1][0]["content"]
        self.assertIn("clarify-feature", context)
        self.assertIn("Requirements intake only", context)
        body = next((self.root / "design-docs").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("减少按钮延迟", body)
        self.assertIn("点击后显示反馈", body)
        self.assertNotIn("让按钮更及时反馈", body)
        self.bridge.enqueue.assert_called_once()
        self.bridge.flush.assert_called_once()

    def test_resume_reuses_proposal_instead_of_charging_model_again(self):
        a = self.invoke()
        b = self.invoke()
        self.assertEqual(a, b)
        self.assertEqual(self.adapter.call.call_count, 1)

    def test_followup_keeps_actual_open_issue(self):
        self.design["decision"] = "continue"
        self.request.update(issue_number=17, request_id="bound-req")
        result = self.invoke()
        self.assertEqual(result["issue_number"], 17)
        self.work.issue.assert_not_called()
        self.assertEqual(len(self.comments), 1)

    def test_closed_issue_cannot_be_reused(self):
        self.design["decision"] = "continue"
        self.request.update(issue_number=17, request_id="bound-req")
        self.existing["state"] = "closed"
        with self.assertRaisesRegex(ValueError, "open bound Issue"):
            self.invoke()
        self.bridge.issue_start.assert_not_called()

    def test_material_questions_create_tracking_issue_without_starting_work(self):
        self.design["questions"] = ["期望的延迟上限是多少？"]
        result = self.invoke()
        self.assertFalse(result["ready"])
        self.work.issue.assert_called_once()
        self.bridge.issue_start.assert_not_called()

    def test_fix_github_access_before_model_or_publication(self):
        self.bridge.gh_state.return_value = ("gh", "gh_unauthenticated")
        result = self.invoke()
        self.assertEqual(result["phase"], "repair_environment")
        self.adapter.call.assert_not_called()
        self.work.issue.assert_not_called()

    def test_unknown_model_attempt_requires_explicit_retry_and_preserves_original(self):
        self.adapter.call.side_effect = RuntimeError("synthetic unknown transport")
        with self.assertRaisesRegex(ValueError, "API failed"):
            self.invoke()
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            self.invoke()
        self.assertEqual(self.adapter.call.call_count, 1)
        self.request["retry_authorized"] = True
        self.adapter.call.side_effect = lambda *args: {
            "text": json.dumps(self.design),
            "finish_reason": "stop",
            "usage": {},
        }
        self.assertTrue(self.invoke()["ready"])
        self.assertEqual(len(list((self.root / ".gonggong-outbox/requirements").glob("*attempt*"))), 1)

    def test_provider_text_cannot_inject_authority_or_credentials(self):
        self.design["approval"] = "approved"
        with self.assertRaisesRegex(ValueError, "schema"):
            self.invoke()
        self.work.issue.assert_not_called()

    def test_receipt_failure_never_enables_development(self):
        self.bridge.flush.side_effect = ValueError("synthetic receipt failure")
        with self.assertRaisesRegex(ValueError, "receipt"):
            self.invoke()
        self.bridge.issue_start.assert_not_called()

    def test_cached_proposal_still_requires_current_admission(self):
        self.invoke()
        self.work.issue.reset_mock()
        original = module.subprocess.run.side_effect

        def revoked(args, **kwargs):
            if any(str(a).endswith("agent-context.mjs") for a in args):
                return subprocess.CompletedProcess(args, 1, "", "revoked")
            return original(args, **kwargs)

        module.subprocess.run.side_effect = revoked
        with self.assertRaisesRegex(ValueError, "admission"):
            self.invoke()
        self.work.issue.assert_not_called()
        self.assertEqual(self.adapter.call.call_count, 1)

    def test_cached_schema_is_revalidated(self):
        self.invoke()
        p = next((self.root / ".gonggong-outbox/requirements").glob("*.json"))
        v = json.loads(p.read_text(encoding="utf-8"))
        v["proposal"]["approval"] = "forged"
        p.write_text(json.dumps(v), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schema"):
            self.invoke()

    def test_unknown_publication_is_reconciled_not_recreated(self):
        self.work.issue.side_effect = subprocess.TimeoutExpired("synthetic create", 1)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.invoke()
        original = self.work.gh
        self.work.gh = lambda *args: "[[]]" if "/issues?state=" in args[1] else original(*args)
        self.request["retry_authorized"] = True
        with self.assertRaisesRegex(ValueError, "publication outcome unknown"):
            self.invoke()
        self.assertEqual(self.work.issue.call_count, 1)
        self.assertEqual(self.adapter.call.call_count, 1)

    def test_definite_github_rejection_can_resume_after_permission_repair(self):
        error = ValueError("GitHub rejected create")
        error.http_status = 403
        self.work.issue.side_effect = error
        with self.assertRaisesRegex(ValueError, "GitHub rejected"):
            self.invoke()
        self.work.issue.side_effect = None
        self.request["retry_authorized"] = True
        self.assertTrue(self.invoke()["ready"])
        self.assertEqual(self.adapter.call.call_count, 1)
        self.assertEqual(self.work.issue.call_count, 2)

    def test_cancelled_before_start_does_not_call_model_or_create(self):
        self.request["_cancel_path"] = str(self.root / "removed-request.json")
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.invoke()
        self.adapter.call.assert_not_called()
        self.work.issue.assert_not_called()

    def test_credentials_never_enter_journal_document_or_context(self):
        with patch.dict(os.environ, {"GONGGONG_REQUIREMENTS_KEY": "unit-secret-value"}):
            self.invoke()
            self.assertEqual(self.adapter.call.call_args.args[0]["api_key_env"], "GONGGONG_REQUIREMENTS_KEY")
        for folder in [".gonggong-outbox/requirements", "design-docs"]:
            for p in (self.root / folder).glob("*"):
                self.assertNotIn("unit-secret-value", p.read_text(encoding="utf-8"))
        self.assertNotIn("unit-secret-value", repr(self.adapter.call.call_args.args[1]))

    def test_concurrent_replay_has_one_model_and_one_publication(self):
        import time
        from concurrent.futures import ThreadPoolExecutor

        bridge_spec = importlib.util.spec_from_file_location("locking_bridge", Path(__file__).with_name("bridge.py"))
        assert bridge_spec and bridge_spec.loader
        locking_bridge = importlib.util.module_from_spec(bridge_spec)
        bridge_spec.loader.exec_module(locking_bridge)
        self.bridge.outbox_lock = locking_bridge.outbox_lock

        def delayed(*args):
            time.sleep(0.1)
            return {"text": json.dumps(self.design), "finish_reason": "stop", "usage": {}}

        self.adapter.call.side_effect = delayed
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.invoke(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.adapter.call.call_count, 1)
        self.assertEqual(self.work.issue.call_count, 1)

    def test_atomic_journal_failure_keeps_previous_valid_state(self):
        path = self.root / "journal.json"
        module.save(path, {"phase": "publication_attempted"})
        before = path.read_bytes()
        with patch.object(module.os, "replace", side_effect=OSError("synthetic interrupted replacement")):
            with self.assertRaises(OSError):
                module.save(path, {"phase": "proposal_ready"})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_existing_codebuddy_transport_has_no_tools_and_needs_no_http_key(self):
        self.check_cli_transport("codebuddy")

    def test_codex_transport_has_no_tools_and_needs_no_http_key(self):
        self.check_cli_transport("codex")

    def check_cli_transport(self, backend):
        import sys

        script = self.root / ("tools/" + backend + "_cli/godot_bridge.js")
        script.parent.mkdir(parents=True)
        script.write_text("// transport path fixture only", encoding="utf-8")
        entry = self.root / "cli-entry.js"
        entry.write_text("// fixture only", encoding="utf-8")
        self.request.update(
            backend=backend,
            cli_node=sys.executable,
            cli_entry=str(entry),
            cli_model="fixture",
            endpoint="",
            model="",
        )
        original = module.subprocess.run.side_effect

        def transport(args, **kwargs):
            if any(str(a).endswith("godot_bridge.js") for a in args):
                payload = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
                self.assertEqual(payload["available_tools"], [])
                self.assertFalse(payload["tool_context"]["permission_enabled"])
                self.assertEqual(payload["agent_id"], "yanshi")
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps({
                        "choices": [{"message": {"content": json.dumps(self.design)}, "finish_reason": "stop"}]
                    }),
                    "",
                )
            return original(args, **kwargs)

        module.subprocess.run.side_effect = transport
        self.assertTrue(self.invoke()["ready"])
        self.adapter.call.assert_not_called()


class ResponsesTransportTests(unittest.TestCase):
    def setUp(self):
        self.value = {
            "id": "resp_fixture",
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"goal":"fixture"}'}]}],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "input_tokens_details": {"cached_tokens": 40},
                "output_tokens_details": {"reasoning_tokens": 10},
            },
        }
        self.profile = {
            "endpoint": "https://api.example.test/v1/chat/completions/",
            "model": "fixture",
            "api_key_env": "REQUIREMENTS_TEST_KEY",
        }
        self.messages = [{"role": "system", "content": "schema"}, {"role": "user", "content": "goal"}]

    def complete(self, payload=None):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(self.value if payload is None else payload).encode()
        opener = Mock()
        opener.open.return_value = response
        with (
            patch.dict(os.environ, {"REQUIREMENTS_TEST_KEY": "synthetic-key"}),
            patch.object(module.urllib.request, "build_opener", return_value=opener),
        ):
            result = module.complete(ROOT, {"backend": "responses"}, self.profile, self.messages, {})
        return result, opener

    def test_responses_endpoint_auth_and_usage(self):
        result, opener = self.complete()
        http_request = opener.open.call_args.args[0]
        self.assertEqual(http_request.full_url, "https://api.example.test/v1/responses")
        self.assertEqual(http_request.get_header("Authorization"), "Bearer synthetic-key")
        body = json.loads(http_request.data)
        self.assertEqual(body["input"], self.messages)
        self.assertFalse(body["store"])
        self.assertFalse(body["stream"])
        self.assertNotIn("tools", body)
        self.assertEqual(result["text"], '{"goal":"fixture"}')
        self.assertEqual(result["usage"]["cache_read_input_tokens"], 40)
        self.assertEqual(result["usage"]["reasoning_output_tokens"], 10)

    def test_incomplete_tool_or_invalid_usage_cannot_publish_requirements(self):
        for mutation in [
            {"status": "incomplete"},
            {"output": [{"type": "function_call", "name": "publish"}]},
            {"usage": {"input_tokens": 1, "input_tokens_details": {"cached_tokens": 2}}},
            {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "fixture"}]}]},
        ]:
            with (
                self.subTest(mutation=mutation),
                self.assertRaisesRegex(ValueError, "Requirements Responses API failed"),
            ):
                self.complete({**self.value, **mutation})

    def test_remote_plain_http_rejected_before_sending_credentials(self):
        self.profile["endpoint"] = "http://api.example.test/v1"
        with patch.object(module.urllib.request, "build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "Invalid Responses endpoint"):
                self.complete()
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
