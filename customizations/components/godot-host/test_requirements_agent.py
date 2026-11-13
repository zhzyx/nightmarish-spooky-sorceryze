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
                return json.dumps([[{"body": body} for body in self.comments]])
            if args[0] == "issue":
                self.comments.append(Path(args[args.index("--body-file") + 1]).read_bytes().decode("utf-8"))
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
        self.assertIn("输入反馈", self.comments[0])
        self.assertLess(self.comments[0].index("## 待确认"), self.comments[0].index("## 范围"))

    def test_steering_new_scope_pauses_without_publication_or_rebinding(self):
        self.request.update(issue_number=17, request_id="bound-req", continuation_only=True)
        first = self.invoke()
        second = self.invoke()
        self.assertEqual(first, second)
        self.assertEqual(first["error"], "steering_requires_separate_task")
        self.assertFalse(first["remote_created"])
        self.work.issue.assert_not_called()
        self.bridge.issue_start.assert_not_called()
        self.bridge.enqueue.assert_not_called()
        self.assertEqual(self.comments, [])
        self.assertEqual(self.adapter.call.call_count, 1)

    def test_steering_continuation_keeps_exact_bound_issue(self):
        self.design["decision"] = "continue"
        self.request.update(issue_number=17, request_id="bound-req", continuation_only=True)
        result = self.invoke()
        self.assertEqual((result["issue_number"], result["request_id"]), (17, "bound-req"))
        self.work.issue.assert_not_called()
        self.assertEqual(len(self.comments), 1)

    def test_direct_steering_requires_original_start_receipt(self):
        key = "daqian-direct-" + "a" * 20
        self.existing["body"] = f"<!-- gonggong-request:{key} -->"
        self.request.update(issue_number=17, request_id=key, continuation_only=True)
        self.design["decision"] = "continue"
        routing = Mock()
        self.bridge.direct_adapter = Mock(return_value=(routing, self.bridge))
        routing.chat_context.side_effect = ValueError("missing original receipt")
        with self.assertRaisesRegex(ValueError, "missing original receipt"):
            self.invoke()
        self.bridge.issue_start.assert_not_called()
        self.assertEqual(self.comments, [])
        routing.chat_context.side_effect = None
        result = self.invoke()
        self.assertTrue(result["ready"])
        routing.chat_context.assert_called_with(self.root, {"issue_number": 17, "request_id": key}, self.bridge)
        self.bridge.issue_start.assert_not_called()
        self.work.issue.assert_not_called()

    def test_steering_validates_binding_and_host_flag_before_model(self):
        for flag in [1, "true", None]:
            self.request.update(continuation_only=flag)
            with self.assertRaisesRegex(ValueError, "continuation-only host state"):
                self.invoke()
        self.request.update(issue_number=17, request_id="other-req", continuation_only=True)
        with self.assertRaisesRegex(ValueError, "same real open bound Issue"):
            self.invoke()
        self.request.update(request_id="bound-req")
        self.existing["state"] = "closed"
        with self.assertRaisesRegex(ValueError, "same real open bound Issue"):
            self.invoke()
        self.adapter.call.assert_not_called()
        self.work.issue.assert_not_called()

    def test_steering_does_not_reuse_normal_intake_publication(self):
        self.request.update(issue_number=17, request_id="bound-req")
        published = self.invoke()
        self.assertEqual(published["issue_number"], 18)
        self.work.issue.reset_mock()
        self.request["continuation_only"] = True
        paused = self.invoke()
        self.assertEqual(paused["error"], "steering_requires_separate_task")
        self.work.issue.assert_not_called()
        self.assertEqual(self.adapter.call.call_count, 2)

    def test_long_followup_resumes_after_first_part(self):
        self.design.update(decision="continue", questions=["问" * 1999 + str(i % 10) for i in range(20)])
        self.request.update(issue_number=17, request_id="bound-req")
        original = self.work.gh

        def interrupt(*args):
            if args[:2] == ("issue", "comment") and self.comments:
                raise ValueError("interrupted")
            return original(*args)

        with patch.object(self.work, "gh", side_effect=interrupt), self.assertRaisesRegex(ValueError, "interrupted"):
            self.invoke()
        self.invoke()
        self.assertEqual(len(self.comments), 3)
        self.assertTrue(all("\r" not in c for c in self.comments))
        self.assertEqual(sum(c.count("- 问") for c in self.comments), 20)
        self.assertTrue(all(len(c.encode("utf-8")) < 65536 for c in self.comments))
        self.assertEqual(self.adapter.call.call_count, 1)

    def test_followup_retains_answers_and_latest_scope_for_intake(self):
        self.design["decision"] = "continue"
        self.request.update(issue_number=17, request_id="bound-req", outcome="先忽略图片")
        history = [
            {"role": "user", "content": "支持 Max、ultra"},
            {"role": "editor", "content": "不支持 ultra 时如何处理？"},
            {"role": "user", "content": "仅 Codex CLI，改为中、高、极高"},
        ]
        self.request["conversation_context"] = history
        self.invoke()
        messages = self.adapter.call.call_args.args[1]
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["conversation_context"], history)
        self.assertIn("Latest user corrections supersede", messages[0]["content"])
        self.assertIn("Never re-ask", messages[0]["content"])
        self.request["conversation_context"] = history + [{"role": "user", "content": "留下 TODO"}]
        self.invoke()
        self.assertEqual(self.adapter.call.call_count, 2)

    def test_invalid_or_oversized_history_is_rejected_before_model_call(self):
        for context in [None, [{"role": "system", "content": "bad"}], [{"role": "user", "content": "x" * 16001}]]:
            self.request["conversation_context"] = context
            with self.assertRaisesRegex(ValueError, "bounded requirements conversation"):
                self.invoke()
        self.adapter.call.assert_not_called()

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

    def test_incomplete_draft_asks_for_clarification_without_publishing_or_recharging(self):
        self.design.update(scope=[], acceptance=[], questions=["这次希望测试哪个功能？"])
        result = self.invoke()
        self.assertTrue(result["ok"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["phase"], "clarification_required")
        self.assertEqual(result["questions"], self.design["questions"])
        self.assertNotIn("issue_number", result)
        self.work.issue.assert_not_called()
        self.bridge.issue_start.assert_not_called()
        self.bridge.enqueue.assert_not_called()
        self.assertFalse((self.root / "design-docs").exists())
        self.request["retry_authorized"] = True
        self.assertEqual(self.invoke(), result)
        self.assertEqual(self.adapter.call.call_count, 1)

    def test_empty_required_lists_without_model_questions_produce_a_targeted_question(self):
        for field in ["scope", "acceptance"]:
            with self.subTest(field=field):
                self.request["conversation_id"] = "partial-" + field
                self.design.update(scope=["输入反馈"], acceptance=["点击后显示反馈"], questions=[])
                self.design[field] = []
                with self.assertRaisesRegex(ValueError, "scope and acceptance"):
                    module.proposal(self.design, ["requirement"])
                result = self.invoke()
                self.assertEqual(result["phase"], "clarification_required")
                self.assertEqual(len(result["questions"]), 1)
                self.assertTrue(result["questions"][0].strip())
        self.work.issue.assert_not_called()
        self.bridge.issue_start.assert_not_called()

    def test_clarification_completes_requirements_and_preserves_the_original_draft(self):
        self.design.update(scope=[], acceptance=[], questions=["这次希望测试哪个功能？"])
        self.assertFalse(self.invoke()["ready"])
        original = next((self.root / ".gonggong-outbox/requirements").glob("*.json"))
        original_bytes = original.read_bytes()
        self.request["outcome"] += "\n用户补充：点击按钮后应立即显示状态文字"
        self.design.update(scope=["按钮点击反馈"], acceptance=["点击后出现状态文字"], questions=[])
        self.assertTrue(self.invoke()["ready"])
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(self.adapter.call.call_count, 2)
        self.work.issue.assert_called_once()
        self.bridge.issue_start.assert_called_once()

    def test_empty_goal_or_title_is_an_incomplete_draft_not_an_environment_error(self):
        for field in ["title", "goal"]:
            with self.subTest(field=field):
                self.request["conversation_id"] = "missing-" + field
                self.design.update(title="响应输入", goal="减少按钮延迟", questions=[])
                self.design[field] = ""
                with self.assertRaisesRegex(ValueError, "requirement " + field):
                    module.proposal(self.design, ["requirement"])
                result = self.invoke()
                self.assertEqual(result["phase"], "clarification_required")
                self.assertTrue(result["questions"])
                self.assertFalse(result["ready"])
        self.work.issue.assert_not_called()
        self.bridge.issue_start.assert_not_called()

    def test_incomplete_draft_still_rejects_credentials_before_persisting(self):
        self.design.update(scope=[], acceptance=[], questions=["ghp_" + "a" * 20])
        with self.assertRaisesRegex(ValueError, "credentials"):
            self.invoke()
        self.work.issue.assert_not_called()
        for journal in (self.root / ".gonggong-outbox/requirements").glob("*.json"):
            self.assertNotIn("ghp_", journal.read_text(encoding="utf-8"))

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
        expected_agent = "yanshi"
        original = module.subprocess.run.side_effect

        def transport(args, **kwargs):
            if any(str(a).endswith("godot_bridge.js") for a in args):
                payload = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
                self.assertEqual(payload["available_tools"], [])
                self.assertFalse(payload["tool_context"]["permission_enabled"])
                self.assertEqual(payload["agent_id"], expected_agent)
                if backend == "codebuddy" or expected_agent == "yanshi":
                    self.assertEqual(payload["response_format"], "json")
                    self.assertNotIn("For the CLI envelope", payload["messages"][0]["content"])
                    if backend == "codex":
                        self.assertEqual(payload["requirements_contract"], {"categories": ["requirement"]})
                else:
                    self.assertNotIn("response_format", payload)
                    self.assertNotIn("requirements_contract", payload)
                    self.assertIn("For the CLI envelope", payload["messages"][0]["content"])
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
        expected_agent = "sinan"
        routed = module.complete(
            self.root, self.request, {}, [{"role": "system", "content": "registered sinan"}], {}, agent_id="sinan"
        )
        self.assertEqual(routed["finish_reason"], "stop")
        self.adapter.call.assert_not_called()

    def test_invalid_response_journal_preserves_identity_and_requires_explicit_retry(self):
        secret = "ghp_" + "x" * 24
        self.adapter.call.side_effect = lambda *args: {
            "text": '{}\n\n{"private":"' + secret + '"}',
            "finish_reason": "stop",
        }
        with self.assertRaises(module.ResponseFailure) as caught:
            self.invoke()
        diagnostic = caught.exception.diagnostic
        self.assertEqual((diagnostic["stage"], diagnostic["code"]), ("proposal_json", "invalid_json"))
        self.assertEqual((diagnostic["position"], diagnostic["line"], diagnostic["column"]), (4, 3, 1))
        journal = next((self.root / ".gonggong-outbox/requirements").glob("*.json"))
        original = journal.read_bytes()
        saved = json.loads(original)
        self.assertEqual(saved["phase"], "model_response_invalid")
        self.assertEqual(saved["failure"], diagnostic)
        self.assertNotIn(secret, str(caught.exception) + original.decode())
        self.assertEqual(self.adapter.call.call_count, 1)  # Actual transport callback preceded failure.
        self.work.issue.assert_not_called()
        self.assertEqual(self.comments, [])
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
        archive = next(journal.parent.glob("*attempt*.json"))
        self.assertEqual(archive.read_bytes(), original)
        self.assertEqual(json.loads(journal.read_bytes())["request_sha256"], saved["request_sha256"])

    def test_proposal_failure_stages_do_not_publish(self):
        for index, (text, finish, stage, code) in enumerate([
            ("", "stop", "proposal_json", "empty"),
            ("  ", "stop", "proposal_json", "empty"),
            ("private prose", "stop", "proposal_json", "invalid_json"),
            (None, "stop", "proposal_json", "invalid_type"),
            ('{"refusal":"private"}', "stop", "proposal_schema", "refusal"),
            ('{"actions":[]}', "stop", "proposal_schema", "actions_forbidden"),
            ("{}", "stop", "proposal_schema", "invalid_shape"),
            ("{}", "length", "model_completion", "nonstop"),
        ]):
            with self.subTest(stage=stage, code=code, index=index):
                self.request["outcome"] = "separate synthetic request " + str(index)
                self.adapter.call.side_effect = lambda *args: {"text": text, "finish_reason": finish}
                with self.assertRaises(module.ResponseFailure) as caught:
                    self.invoke()
                self.assertEqual(
                    (caught.exception.diagnostic["stage"], caught.exception.diagnostic["code"]), (stage, code)
                )
                self.assertNotIn("private", str(caught.exception))
        self.work.issue.assert_not_called()
        self.assertEqual(self.comments, [])

    def test_cli_envelope_failures_are_structural_and_private(self):
        valid = {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}
        cases = [
            ("{}\n{}", "cli_envelope_json", "invalid_json"),
            ("", "cli_envelope_json", "empty"),
            ('{"choices":[]}', "cli_envelope_shape", "invalid_shape"),
        ]
        for field, value, code in [
            ("refusal", "private", "refusal"),
            ("tool_calls", [{"private": 1}], "actions_forbidden"),
            ("function_call", {}, "actions_forbidden"),
            ("content", None, "invalid_type"),
        ]:
            envelope = json.loads(json.dumps(valid))
            envelope["choices"][0]["message"][field] = value
            cases.append((
                json.dumps(envelope),
                "proposal_json" if code == "invalid_type" else "cli_envelope_shape",
                code,
            ))
        envelope = json.loads(json.dumps(valid))
        envelope["choices"][0]["finish_reason"] = "tool_calls"
        cases.append((json.dumps(envelope), "cli_envelope_shape", "nonstop"))
        for raw, stage, code in cases:
            with self.subTest(stage=stage, code=code):
                with self.assertRaises(module.ResponseFailure) as caught:
                    module.cli_response(raw)
                self.assertEqual(
                    (caught.exception.diagnostic["stage"], caught.exception.diagnostic["code"]), (stage, code)
                )
                self.assertNotIn("private", str(caught.exception))
        self.assertEqual(module.cli_response(json.dumps(valid))["text"], "{}")

    def test_actual_complete_failure_stages_reach_journal_without_private_output(self):
        import sys

        entry = self.root / "entry.js"
        entry.write_text("// synthetic transport", encoding="utf-8")
        self.request.update(backend="codex", cli_node=sys.executable, cli_entry=str(entry), cli_model="fixture")
        original = module.subprocess.run.side_effect
        native_diagnostic = {
            "stage": "codex_data_json",
            "code": "invalid_json",
            "output_bytes": 12,
            "output_sha256": "a" * 64,
            "utf16_position": 3,
        }
        cases = [
            (0, "{}\n{}", "cli_envelope_json", "invalid_json"),
            (0, "", "cli_envelope_json", "empty"),
            (0, '{"choices":[]}', "cli_envelope_shape", "invalid_shape"),
            (
                1,
                json.dumps({"error": {"requirements_diagnostic": native_diagnostic, "message": "private-token"}}),
                "codex_data_json",
                "invalid_json",
            ),
            (
                1,
                json.dumps({"error": {"requirements_diagnostic": {**native_diagnostic, "stage": ["private-token"]}}}),
                "cli_transport",
                "process_failed",
            ),
            (1, "private-token", "cli_transport", "process_failed"),
            (None, "private-token", "cli_transport", "timeout"),
        ]
        calls = []
        for index, (exit_code, raw, stage, code) in enumerate(cases):

            def transport(args, **kwargs):
                if any(str(arg).endswith("godot_bridge.js") for arg in args):
                    calls.append(args)
                    if exit_code is None:
                        raise subprocess.TimeoutExpired(args, 210, output="private-token", stderr="private-token")
                    return subprocess.CompletedProcess(args, exit_code, raw, "private-token")
                return original(args, **kwargs)

            module.subprocess.run.side_effect = transport
            self.request["outcome"] = "transport stage " + str(index)
            with self.subTest(stage=stage, index=index):
                with self.assertRaises(module.ResponseFailure) as caught:
                    self.invoke()
                self.assertEqual(
                    (caught.exception.diagnostic["stage"], caught.exception.diagnostic["code"]), (stage, code)
                )
                self.assertEqual(len(calls), index + 1)
                self.assertNotIn("private-token", str(caught.exception))
        journals = list((self.root / ".gonggong-outbox/requirements").glob("*.json"))
        self.assertEqual(len(journals), len(cases))
        for journal in journals:
            self.assertNotIn("private-token", journal.read_text(encoding="utf-8"))
            record = json.loads(journal.read_bytes())
            self.assertEqual(
                record["phase"],
                "model_transport_failed" if record["failure"]["stage"] == "cli_transport" else "model_response_invalid",
            )
        self.work.issue.assert_not_called()
        self.assertEqual(self.comments, [])

    def test_cancel_after_real_transport_return_never_publishes(self):
        cancel = self.root / "active-request"
        cancel.write_text("active", encoding="utf-8")
        self.request["_cancel_path"] = str(cancel)

        def cancelled(*args):
            cancel.unlink()
            return {"text": json.dumps(self.design), "finish_reason": "stop", "usage": {}}

        self.adapter.call.side_effect = cancelled
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.invoke()
        self.assertEqual(self.adapter.call.call_count, 1)
        self.work.issue.assert_not_called()
        self.assertEqual(self.comments, [])

    def test_parser_limits_and_invalid_unicode_keep_failure_journal(self):
        nested = "[" * 10000 + "0" + "]" * 10000
        long_integer = "9" * 4301
        real_loads = json.loads
        cases = []
        for text in (nested, long_integer):
            # Interpreter versions may accept these valid JSON documents. The
            # requirement schema must still reject their non-object values.
            try:
                parsed = real_loads(text)
            except (ValueError, RecursionError):
                cases.append((text, "proposal_json", "invalid_json", None))
            else:
                self.assertNotIsInstance(parsed, dict)
                cases.append((text, "proposal_schema", "invalid_shape", None))
        cases.append(("\ud800", "proposal_json", "invalid_encoding", None))
        # Exercise both defensive catch paths independently of interpreter
        # limits, only after the actual adapter returns this exact payload.
        cases.extend([
            (nested, "proposal_json", "invalid_json", RecursionError),
            (long_integer, "proposal_json", "invalid_json", ValueError),
        ])
        journals = self.root / ".gonggong-outbox/requirements"
        for index, (text, stage, code, parser_error) in enumerate(cases):
            self.request["outcome"] = "parser limit " + str(index)
            self.adapter.call.side_effect = lambda *args: {"text": text, "finish_reason": "stop"}
            before = set(journals.glob("*.json"))

            def limited_loads(raw, *args, **kwargs):
                if raw == text:
                    self.assertEqual(self.adapter.call.call_count, index + 1)
                    raise parser_error("synthetic decoder limit")
                return real_loads(raw, *args, **kwargs)

            context = patch.object(module.json, "loads", side_effect=limited_loads) if parser_error else nullcontext()
            with self.subTest(stage=stage, code=code, controlled_limit=parser_error, index=index), context:
                with self.assertRaises(module.ResponseFailure) as caught:
                    self.invoke()
                diagnostic = caught.exception.diagnostic
                self.assertEqual((diagnostic["stage"], diagnostic["code"]), (stage, code))
                self.assertEqual(self.adapter.call.call_count, index + 1)
                self.assertNotIn("position", diagnostic)
                if code == "invalid_encoding":
                    self.assertEqual(diagnostic["output_characters"], 1)
                    self.assertNotIn("output_bytes", diagnostic)
                    self.assertNotIn("output_sha256", diagnostic)
                new_journals = set(journals.glob("*.json")) - before
                self.assertEqual(len(new_journals), 1)
                record = real_loads(new_journals.pop().read_bytes())
                self.assertEqual(record["phase"], "model_response_invalid")
                self.assertEqual(record["failure"], diagnostic)
                self.assertNotIn("proposal", record)
                self.work.issue.assert_not_called()
                self.assertEqual(self.comments, [])
        self.assertEqual(len(list(journals.glob("*.json"))), len(cases))

    def test_escaped_surrogate_in_valid_fields_is_rejected_before_journal_proposal(self):
        text = json.dumps({**self.design, "title": "\ud800"}, ensure_ascii=True)
        self.assertTrue(text.isascii())  # The actual wire is valid UTF-8 JSON.
        self.adapter.call.side_effect = lambda *args: {"text": text, "finish_reason": "stop", "usage": {}}
        with self.assertRaises(module.ResponseFailure) as caught:
            self.invoke()
        diagnostic = caught.exception.diagnostic
        self.assertEqual((diagnostic["stage"], diagnostic["code"]), ("proposal_schema", "invalid_encoding"))
        self.assertEqual(diagnostic["output_bytes"], len(text.encode("utf-8")))
        self.assertEqual(self.adapter.call.call_count, 1)
        journal = next((self.root / ".gonggong-outbox/requirements").glob("*.json"))
        saved = json.loads(journal.read_bytes())
        self.assertEqual(saved["failure"], diagnostic)
        self.assertEqual(saved["phase"], "model_response_invalid")
        self.assertNotIn("proposal", saved)
        self.work.issue.assert_not_called()
        self.assertEqual(self.comments, [])


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
