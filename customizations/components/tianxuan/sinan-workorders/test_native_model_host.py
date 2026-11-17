"""Actual owned-tree fault tests; no Codex/model/network is started."""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from native_model_host import NativeModelHost, digest

ROOT = Path(__file__).resolve().parents[4]
REQUEST = {
    "request_id": "test-1480",
    "task": "fixed",
    "context": "fixed",
    "write_allowlist": ["a.txt"],
    "acceptance": "fixed",
}
PROBE = """import json,sys,subprocess,os,time,hashlib
p=json.load(sys.stdin)
def digest(v): return hashlib.sha256(json.dumps(v,ensure_ascii=False,separators=(",", ":")).encode()).hexdigest()
marker=os.environ["TEST_MARKER"]
child=subprocess.Popen([sys.executable,"-c","import time,pathlib; time.sleep(1); pathlib.Path("+repr(marker)+").write_text('leaked')"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
mode=os.environ["TEST_MODE"]
if mode in ("timeout","cancel"): time.sleep(30)
if mode=="fault": sys.exit(7)
r=p["request"]; proposal={"request_id":r["request_id"],"input_digest":digest(r),"summary":"proposal", "files":[{"path":"a.txt","content":"hello"}]}
response={"request_id":r["request_id"],"input_digest":digest(r),"config_digest":p["installed"]["config_digest"],"requested_model":p["installed"]["model"],"execution_authority":False,"status":"proposed","proposal":proposal,"output_digest":digest(proposal),"usage":{"raw":None,"status":"unknown"},"elapsed_ms":0}
if mode=="bad": response["proposal"]["files"].append(response["proposal"]["files"][0]); response["output_digest"]=digest(proposal)
print(json.dumps(response))
"""


class OwnedHostTests(unittest.TestCase):
    def run_probe(self, mode):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            probe = folder / "probe.py"
            probe.write_text(PROBE, encoding="utf-8")
            marker = folder / "leaked"
            profile = {
                "node": sys.executable,
                "entry": str(probe),
                "python": sys.executable,
                "model": "fake-installed-probe",
                "reasoning_effort": None,
                "env": {**os.environ, "TEST_MODE": mode, "TEST_MARKER": str(marker)},
                "timeout": 0.3 if mode == "timeout" else 5,
            }
            host = NativeModelHost(profile, lambda p: p == profile, ROOT / "tools/ainative/owned_process.py")
            # Explicit test-only admitted producer. Production has no request-level wrapper selection.
            original_configuration = host.configuration
            fixed_profile, binding = original_configuration()
            host.wrapper = probe
            host.configuration = lambda: (fixed_profile, binding)
            cancel = threading.Event()
            timer = threading.Timer(0.3, cancel.set) if mode == "cancel" else None
            if timer:
                timer.start()
            try:
                result = host.run(REQUEST, cancel)
            finally:
                if timer:
                    timer.join()
            self.assertTrue(result["process_tree_closed"])
            time.sleep(1.15)
            self.assertFalse(marker.exists(), "Owned descendant escaped cleanup")
            return result

    def test_success_closes_descendant_before_acceptance(self):
        r = self.run_probe("success")
        self.assertEqual(r["status"], "proposed")
        self.assertEqual(r["proposal"]["files"][0]["content"], "hello")

    def test_timeout_closes_descendant(self):
        r = self.run_probe("timeout")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("timeout", r["process_reasons"])

    def test_cancel_closes_descendant(self):
        self.assertEqual(self.run_probe("cancel")["status"], "unknown")

    def test_host_fault_closes_descendant(self):
        r = self.run_probe("fault")
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["process_exit_code"], 7)

    def test_response_duplicate_paths_rejected(self):
        r = self.run_probe("bad")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("response_contract", r["process_reasons"])


class UsageContractTests(unittest.TestCase):
    def response(self):
        counts = dict(cachedInputTokens=2, inputTokens=5, outputTokens=3, reasoningOutputTokens=1, totalTokens=8)
        return dict(
            request_id=REQUEST["request_id"],
            input_digest=digest(REQUEST),
            config_digest="a" * 64,
            requested_model="installed-model",
            execution_authority=False,
            status="unknown",
            proposal=None,
            output_digest=None,
            elapsed_ms=1,
            usage=dict(thread_id="thread-1", turn_id="turn-1", status="observed", raw=dict(last=counts, total=counts)),
        )

    def test_unknown_proposal_preserves_bound_usage(self):
        NativeModelHost._validate(self.response(), REQUEST, "a" * 64)

    def test_usage_requires_both_acknowledged_identities(self):
        for field in ("thread_id", "turn_id"):
            value = self.response()
            value["usage"][field] = None
            with self.assertRaises(ValueError):
                NativeModelHost._validate(value, REQUEST, "a" * 64)

    def test_unknown_proposal_cannot_return_content(self):
        value = self.response()
        value["proposal"] = {"files": []}
        with self.assertRaises(ValueError):
            NativeModelHost._validate(value, REQUEST, "a" * 64)


if __name__ == "__main__":
    unittest.main()
