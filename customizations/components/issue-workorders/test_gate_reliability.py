import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import issue_gate as gate
import work_items


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "core.autocrlf", "false")
        self.git("commit", "--allow-empty", "-qm", "base")
        self.git("branch", "base")
        self.issue = {"url": "https://github.com/test/repo/issues/106", "number": 106}
        self.event = "gonggong-diting-data/events/gonggong-workspace/req/event.json"
        self.evidence = "data-collection/evidence.json"

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def stage(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        self.git("add", "--", name)

    def check(self):
        return gate.check_pr_evidence(self.root, self.issue, "req", "gonggong-workspace", "base")

    def test_pr_scope_includes_previous_commits_and_index_not_working_bytes(self):
        self.stage(self.event, {"request_id": "req", "tenant_id": "gonggong-workspace"})
        self.git("commit", "-qm", "event")
        self.stage(self.evidence, {"request_id": "req", "issue_url": self.issue["url"]})
        (self.root / self.evidence).write_text("{}")
        self.assertTrue(self.check()["matching_collection"])
        self.git("add", self.evidence)
        with self.assertRaisesRegex(ValueError, "PR_EVIDENCE_BINDING"):
            self.check()

    def test_old_evidence_outside_pr_cannot_satisfy_ci(self):
        self.stage(self.evidence, {"request_id": "req", "issue_number": 106})
        self.git("commit", "-qm", "old evidence")
        self.git("branch", "-f", "base")
        self.stage(self.event, {"request_id": "req", "tenant_id": "gonggong-workspace"})
        with self.assertRaisesRegex(ValueError, "PR_EVIDENCE_BINDING"):
            self.check()

    def test_binding_variants_and_rejection(self):
        self.stage(self.event, {"request_id": "req", "tenant_id": "gonggong-workspace"})
        for field, value in [("issue", self.issue["url"]), ("issue_url", self.issue["url"]), ("issue_number", 106)]:
            self.stage(self.evidence, {"request_id": "req", field: value})
            self.assertTrue(self.check()["matching_collection"])
        for value in [
            {"request_id": "other", "issue_number": 106},
            {"request_id": "req", "issue_number": "106"},
            {"request_id": "req", "issue_number": 107},
        ]:
            self.stage(self.evidence, value)
            with self.assertRaisesRegex(ValueError, "PR_EVIDENCE_BINDING"):
                self.check()

    def test_no_event_preserves_ci_nonblocking_recording_policy(self):
        self.assertFalse(self.check()["matching_event"])

    def test_collector_binds_same_tenant_request_source_and_rejects_ambiguity(self):
        directory = self.root / "gonggong-diting-data/events/gonggong-workspace/req"
        directory.mkdir(parents=True)
        value = {
            "request_id": "req",
            "tenant_id": "gonggong-workspace",
            "kind": "request",
            "event_id": "one",
            "source_ref": self.issue["url"],
            "agent": {"origin": "test"},
        }
        (directory / "one.json").write_text(json.dumps(value))
        with (
            patch.object(
                work_items, "config", return_value=({"repository": "test/repo", "tenant_id": "gonggong-workspace"}, [])
            ),
            patch.object(work_items.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
        ):
            result = work_items.collect(self.root, "req")
            evidence = json.loads((self.root / result["path"]).read_text())
            self.assertEqual(evidence["issue_number"], 106)
            self.assertEqual(evidence["issue_url"], self.issue["url"])
            (directory / "two.json").write_text(
                json.dumps(dict(value, event_id="two", source_ref="github:test/repo:issue:107"))
            )
            with self.assertRaisesRegex(ValueError, "Ambiguous request Issue sources"):
                work_items.collect(self.root, "req")

    def test_same_fixtures_against_actual_ci_script(self):
        workflow = Path(__file__).resolve().parents[3] / ".github/workflows/gonggong-issue-gate.yml"
        script = textwrap.dedent(workflow.read_text(encoding="utf-8").split("          script: |\n", 1)[1])
        harness = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const issue = {number:106, html_url:'https://github.com/test/repo/issues/106', state:'open',
 labels:['workspace:gonggong','type:bug','status:in-progress'], body:'<!-- gonggong-request:req -->'};
const pr = {number:1, state:'open', body:'GongGong-Issue: #106\nGongGong-Request: req', base:{sha:'base'}};
const files = input.values.map((v,i)=>({filename:v.path,sha:String(i),status:'added'}));
const github = {paginate:async()=>files,rest:{
 pulls:{get:async()=>({data:pr}),listFiles:()=>{}},issues:{get:async()=>({data:issue})},
 repos:{getContent:async()=>({data:{content:Buffer.from('[{"name":"type:bug"}]').toString('base64')}})},
 git:{getBlob:async({file_sha})=>({data:{encoding:'base64',content:Buffer.from(JSON.stringify(input.values[Number(file_sha)].value)).toString('base64')}})}}};
const core = {warning:()=>{},summary:{addRaw:()=>({write:async()=>{}})}};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('github','context','core',input.script)(github,
 {repo:{owner:'test',repo:'repo'},payload:{pull_request:{number:1}}},core)
 .then(()=>process.stdout.write('passed')).catch(()=>process.stdout.write('rejected'));
"""
        self.stage(self.event, {"request_id": "req", "tenant_id": "gonggong-workspace"})
        for evidence in [
            {},
            {"request_id": "req", "issue_number": 106},
            {"request_id": "req", "issue_number": "106"},
            {"request_id": "req", "issue_url": self.issue["url"]},
            {"request_id": "other", "issue_number": 106},
        ]:
            self.stage(self.evidence, evidence)
            try:
                self.check()
                local = "passed"
            except ValueError:
                local = "rejected"
            values = [
                {"path": self.event, "value": {"request_id": "req", "tenant_id": "gonggong-workspace"}},
                {"path": self.evidence, "value": evidence},
            ]
            remote = subprocess.check_output(
                ["node", "-e", harness], input=json.dumps({"script": script, "values": values}).encode()
            ).decode()
            self.assertEqual(local, remote, evidence)

    def test_ci_reads_current_pr_state_before_checking_issue(self):
        workflow = Path(__file__).resolve().parents[3] / ".github/workflows/gonggong-issue-gate.yml"
        script = textwrap.dedent(workflow.read_text(encoding="utf-8").split("          script: |\n", 1)[1])
        harness = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const summaries = [];
const pr = {number:1, state:input.currentState, merged:input.merged,
 body:input.invalidBody ? '' : 'GongGong-Issue: #106\nGongGong-Request: req', base:{sha:'base'}};
const issue = {number:106, state:input.issueState, pull_request:input.fakeIssue,
 labels:['workspace:gonggong','type:bug',input.label || 'status:in-progress'],
 body:'<!-- gonggong-request:req -->'};
const github = {paginate:async()=>{calls.push('files');return [];},rest:{
 pulls:{get:async()=>{calls.push('pr');return {data:pr};},listFiles:()=>{}},
 issues:{get:async()=>{calls.push('issue');return {data:issue};}},
 repos:{getContent:async()=>{calls.push('labels');return {data:{content:
 Buffer.from('[{"name":"type:bug"}]').toString('base64')}};}}}};
const core = {warning:()=>{},summary:{addRaw:(s)=>{summaries.push(s);return {write:async()=>{}};}}};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('github','context','core',input.script)(github,
 {repo:{owner:'test',repo:'repo'},payload:{action:input.action,
 pull_request:{number:1,state:input.payloadState}}},core)
 .then(()=>process.stdout.write(JSON.stringify({result:'passed',calls,summaries})))
 .catch((e)=>process.stdout.write(JSON.stringify({result:'rejected',calls,error:e.message})));
"""
        cases = [
            # A queued edit can execute after closure; neither old payload nor body grants admission.
            ({"currentState": "closed", "payloadState": "open", "issueState": "closed"}, "passed", ["pr"]),
            ({"currentState": "closed", "merged": True, "invalidBody": True}, "passed", ["pr"]),
            ({"currentState": "closed", "action": "reopened", "issueState": "open"}, "passed", ["pr"]),
            # Conversely, an old closed payload must not skip a PR that has since reopened.
            ({"payloadState": "closed", "issueState": "closed"}, "rejected", ["pr", "issue"]),
            ({"action": "reopened", "issueState": "closed"}, "rejected", ["pr", "issue"]),
            ({"invalidBody": True}, "rejected", ["pr"]),
            ({"fakeIssue": {}}, "rejected", ["pr", "issue"]),
            ({"label": "status:done"}, "rejected", ["pr", "issue", "labels"]),
            ({}, "passed", ["pr", "issue", "labels", "files"]),
            ({"action": "reopened"}, "passed", ["pr", "issue", "labels", "files"]),
        ]
        for overrides, expected, calls in cases:
            with self.subTest(overrides=overrides):
                fixture = dict(script=script, currentState="open", issueState="open", action="edited")
                fixture.update(overrides)
                result = json.loads(
                    subprocess.check_output(["node", "-e", harness], input=json.dumps(fixture).encode())
                )
                self.assertEqual(result["result"], expected, result)
                self.assertEqual(result["calls"], calls)
                if fixture["currentState"] == "closed":
                    self.assertIn("not applicable", result["summaries"][0])
                    self.assertIn("not candidate admission", result["summaries"][0])

    def test_dirty_worktree_diagnosis(self):
        self.stage("file", {})
        (self.root / "file").write_text("changed")
        with self.assertRaisesRegex(ValueError, "WORKTREE_UNSTAGED"):
            gate.git(self.root, "diff", "--quiet")

    def test_diagnostics_never_echo_sensitive_stderr(self):
        for error, expected in [
            (b"Permission denied secret-token", "GIT_PERMISSION"),
            (b"index.lock secret-token", "GIT_LOCK"),
        ]:
            with patch.object(gate.subprocess, "run", return_value=subprocess.CompletedProcess([], 128, b"", error)):
                with self.assertRaisesRegex(ValueError, expected) as caught:
                    gate.git(self.root, "status")
                self.assertNotIn("secret-token", str(caught.exception))
        for error, expected in [
            ("error connecting to api.github.com secret-token", "GITHUB_NETWORK"),
            ("HTTP 403 secret-token", "GITHUB_HTTP_403"),
        ]:
            with patch.object(work_items.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", error)):
                with self.assertRaisesRegex(ValueError, expected) as caught:
                    work_items.gh("api", "user")
                self.assertNotIn("secret-token", str(caught.exception))

    def test_timeout_reports_unknown_not_failed_admission(self):
        with patch.object(gate.subprocess, "run", side_effect=subprocess.TimeoutExpired("validator", 300)):
            with self.assertRaisesRegex(ValueError, "VALIDATOR_TIMEOUT"):
                gate.validate_command([], self.root, {}, "Framework")
        with patch.object(work_items.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ValueError, "GITHUB_RUNTIME"):
                work_items.gh("api", "user")


if __name__ == "__main__":
    unittest.main()
