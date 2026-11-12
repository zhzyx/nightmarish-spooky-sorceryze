import hashlib
import json
import os
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

import evaluate
import runner

RUNTIME = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5] / "framework"
BASE = Path.cwd()
(BASE / "work").mkdir(exist_ok=True)

checks: list[dict[str, Any]] = []
requests: list[dict[str, Any]] = []
answers = []
response_overrides: list[dict[str, Any]] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append(body)
        answer = answers.pop(0) if answers else {"action": "final", "value": "ok"}
        text = answer if isinstance(answer, str) else json.dumps(answer)
        if self.path == "/chat":
            data = {
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        elif self.path == "/ollama":
            data = {
                "message": {"content": text},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 10,
                "eval_count": 5,
            }
        else:
            data = {"text": text, "finish_reason": "stop", "usage": {"input_tokens": 10, "output_tokens": 5}}
        data["model"] = body["model"] + "-provider-alias"
        if response_overrides:
            data = response_overrides.pop(0)
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
os.environ["GONGGONG_HOST_KEY"] = "isolated-test-key-not-a-production-secret"
try:
    with tempfile.TemporaryDirectory(dir=BASE / "work", prefix="model-integration-") as tmp:
        temp = Path(tmp)
        root = temp / "framework"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
        manifest = runner.read(root / "framework-manifest.json")
        (root / "reviews/fixture.txt").write_text("Synthetic test only; not production approval.")
        fp = runpy.run_path(str(root / "tools/verify_framework.py"))["fingerprint"]
        for a in manifest["agents"]:
            p = runner.read(root / "templates/review-pass.json")
            d, files = fp(root, a["candidate_files"])
            assert d == a["candidate_digest"]
            p.update(
                template=False, status="approved", event="agent_definition_change", phase="local_definition_release"
            )
            p["subject"] = {
                "id": a["id"],
                "version_or_digest": {"version": a["version"], "candidate_digest": d, "candidate_files": files},
                "scope": ["local_agent_definition_only"],
            }
            p["review"] = {
                "gonggong_framework": "pass",
                "concision": {"status": "pass"},
                "applicable_validation": "pass",
                "independence": "independent_subagent_review",
                "evaluator_id": "synthetic-reviewer",
                "yuanheng": {
                    k: "pass" for k in ["purpose", "truth", "economy", "authority", "adaptation", "continuity"]
                },
                "evidence_refs": ["reviews/fixture.txt"],
            }
            p["approval"] = {
                "approver_id": "synthetic-approver",
                "authority_ref": "test-only",
                "decision_evidence_ref": "reviews/fixture.txt",
                "approved_at": runner.now(),
                "valid_until_or_task_end": "bound_candidate_only",
                "expires_at": None,
            }
            (root / a["admission_pass"]).write_text(json.dumps(p), encoding="utf-8")
        inv = runpy.run_path(str(root / "tools/package_integrity.py"))["inventory"](root)
        (root / "package-lock.json").write_text(
            json.dumps({"schema_version": 1, "path_base": "framework_root", "files": inv})
        )

        def profile(protocol, path, ident):
            p = {
                "id": ident,
                "protocol": protocol,
                "endpoint": f"http://127.0.0.1:{server.server_port}/{path}",
                "model": "synthetic-" + ident,
                "max_context_bytes": 100000,
                "system_role": False if path == "ollama" else True,
            }
            report = evaluate.evaluate(
                p,
                [
                    {
                        "id": "summary",
                        "task_type": "summary",
                        "messages": [{"role": "user", "content": "return ok"}],
                        "schema": {"type": "string"},
                        "expected": "ok",
                    }
                ],
                "synthetic",
            )
            assert report["passed_task_types"] == ["summary"]
            identity = report["results"][0]["response"]
            assert identity["requested_model"] == p["model"]
            assert identity["observed_model"] == p["model"] + "-provider-alias"
            assert identity["protocol"] == protocol and identity["model_identity_verified"] is False
            f = temp / (ident + "-eval.json")
            f.write_text(json.dumps(report), encoding="utf-8")
            p["evaluation"] = {
                **{k: report[k] for k in ["profile_digest", "scope", "passed_task_types"]},
                "evidence_ref": str(f),
                "evidence_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            }
            return p

        profiles = [
            profile("chat-completions", "chat", "chat"),
            profile("ollama-chat", "ollama", "ollama"),
            profile("gonggong-json", "bridge", "bridge"),
        ]

        def plan(name, agent="yanshi", models=None, mode="single"):
            return {
                "task": {
                    "id": name,
                    "tenant_id": "synthetic",
                    "project_id": "test",
                    "agent_id": agent,
                    "outcome": "test summary",
                    "authority_ref": "isolated test",
                    "retention": "temporary test",
                    "mode": mode,
                    "validation_only": True,
                    "work_items": [{"id": "test", "kind": "feature", "relation": "tests", "certainty": "confirmed"}],
                    "steps": [{"id": "summary", "kind": "summary", "instruction": "return ok", "output": "text"}],
                },
                "profiles": models or profiles,
                "limits": {"max_calls": 5, "max_output_tokens": 128},
            }

        def grant(p, state):
            payload = {
                **p,
                "runtime_sha256": runner.runtime_digest(),
                "state_dir": str(state),
                "expires_at": time.time() + 600,
                "authority_ref": "synthetic-only",
                "framework_sha256": hashlib.sha256((root / "framework-manifest.json").read_bytes()).hexdigest(),
            }
            return {"payload": payload, "signature": runner.signature(payload)}

        def ok(name):
            checks.append({"name": name, "pass": True})

        for p in profiles:
            state = temp / p["id"]
            g = grant(plan("protocol-" + p["id"], models=[p]), state)
            r = runner.run(g, root, state)
            assert r["status"] == "completed"
            assert r["result"]["calls"] == 1
            n = len(requests)
            assert runner.run(g, root, state)["replayed"]
            assert len(requests) == n
            ledger = runpy.run_path(str(root / "agents/diting/scripts/ledger.py"))
            records = [x["record"] for x in ledger["query"](state / "diting.sqlite", "synthetic")]
            step = next(x for x in records if x["kind"] == "step")
            usage = step["payload"]["usage"]
            assert usage["model"] == p["model"]  # Frozen schema: configured/requested identity only.
            database, reference = usage["metering_ref"].split("#", 1)
            task_id, seq = reference.rsplit("/", 1)
            job = runner.jid_for({"tenant_id": step["tenant_id"], "id": task_id})
            with sqlite3.connect(state / database) as cx:
                kind, raw = cx.execute("SELECT kind,data FROM events WHERE job=? AND seq=?", (job, int(seq))).fetchone()
            receipt = json.loads(raw)
            assert kind == "call_end" and receipt["status"] == "received"
            assert task_id == g["payload"]["task"]["id"] and receipt["call"] == 1
            assert receipt["requested_model"] == p["model"]
            assert receipt["observed_model"] == p["model"] + "-provider-alias"
            assert receipt["protocol"] == p["protocol"] and receipt["observed_model_source"] == "response.model"
            assert receipt["observed_model_status"] == "provider_reported"
            assert receipt["model_identity_verified"] is False
            # Simulate a stop after the completed event but before terminal finalization.
            with sqlite3.connect(state / database) as cx:
                runner.set_status(cx, job, "needs_attention")
            assert runner.recover(g, root, state, "retry")["status"] == "completed"
            with sqlite3.connect(state / database) as cx:
                assert cx.execute("SELECT data FROM events WHERE job=? AND seq=?", (job, int(seq))).fetchone()[0] == raw
            assert len(requests) == n
            ok(p["protocol"] + " evaluation/journal/telemetry reference provenance + replay/recovery")
        for model, status in [(None, "unavailable"), ({"untrusted": "object"}, "invalid")]:
            state = temp / status
            p = profiles[0]
            response_overrides.append({
                "model": model,
                "choices": [{"message": {"content": '{"action":"final","value":"ok"}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            })
            g = grant(plan(status, models=[p]), state)
            assert runner.run(g, root, state)["status"] == "completed"
            with sqlite3.connect(state / "runtime.sqlite") as cx:
                receipt = next(
                    e["data"]
                    for e in runner.events(cx, runner.jid_for(g["payload"]["task"]))
                    if e["kind"] == "call_end"
                )
            assert receipt["observed_model"] is None and receipt["observed_model_status"] == status
            assert receipt["requested_model"] == p["model"] and receipt["model_identity_verified"] is False
        ok("missing/malformed optional model identity retained as unknown without rejecting valid output")
        state = temp / "unknown"
        response_overrides.append({"model": "unusable-response-model"})
        g = grant(plan("unknown", models=[profiles[0]]), state)
        assert runner.run(g, root, state)["status"] == "needs_reconciliation"
        with sqlite3.connect(state / "runtime.sqlite") as cx:
            receipt = next(
                e["data"] for e in runner.events(cx, runner.jid_for(g["payload"]["task"])) if e["kind"] == "call_end"
            )
        assert receipt["observed_model"] is None and receipt["observed_model_status"] == "unavailable"
        assert receipt["requested_model"] == profiles[0]["model"]
        assert receipt["protocol"] == profiles[0]["protocol"] and receipt["model_identity_verified"] is False
        ok("malformed response reconciliation does not invent observed identity")
        state = temp / "interrupted"
        g = grant(plan("interrupted", models=[profiles[0]]), state)
        with patch("runner.call", side_effect=KeyboardInterrupt):
            try:
                runner.run(g, root, state)
                raise AssertionError("interruption not delivered")
            except KeyboardInterrupt:
                pass
        assert runner.recover(g, root, state, "cancel")["status"] == "cancelled"
        with sqlite3.connect(state / "runtime.sqlite") as cx:
            receipt = next(
                e["data"] for e in runner.events(cx, runner.jid_for(g["payload"]["task"])) if e["kind"] == "call_end"
            )
        assert receipt["requested_model"] == profiles[0]["model"]
        assert receipt["observed_model"] is None and receipt["observed_model_status"] == "unavailable"
        assert receipt["model_identity_verified"] is False
        ok("interrupted-call recovery preserves request identity and unknown observation")
        for agent in ["kuafu", "diting"]:
            state = temp / agent
            assert runner.run(grant(plan(agent, agent), state), root, state)["status"] == "completed"
            ok(agent + " admitted context to local telemetry")
        state = temp / "fallback"
        p = plan("fallback")
        p["task"]["steps"][0]["skill"] = "clarify-feature"
        p["task"]["steps"][0]["references"] = ["agents/yanshi/references/understanding.md"]
        answers.extend(["bad json", {"action": "final", "value": "ok"}])
        r = runner.run(grant(p, state), root, state)
        assert r["status"] == "completed" and r["result"]["calls"] == 2
        ledger = runpy.run_path(str(root / "agents/diting/scripts/ledger.py"))
        records = [x["record"] for x in ledger["query"](state / "diting.sqlite", "synthetic")]
        assert (
            sum(x["kind"] == "quality_issue" for x in records) == 1 and sum(x["kind"] == "rework" for x in records) == 1
        )
        steps = [x for x in records if x["kind"] == "step"]
        assert len(steps) == 2 and all(x["payload"]["reporting_component"]["id"] == "clarify-feature" for x in steps)
        ok("rejected output fallback, quality/rework and once-only skill attribution")
        state = temp / "autonomous"
        p = plan("autonomous", mode="autonomous")
        p["task"]["resources"] = {"brief": "approved facts"}
        p["task"]["steps"][0]["tools"] = ["lookup_resource"]
        answers.extend([
            {"action": "tool", "name": "lookup_resource", "arguments": {"key": "brief"}},
            {"action": "final", "value": "ok"},
        ])
        assert runner.run(grant(p, state), root, state)["result"]["calls"] == 2
        ok("bounded autonomous resource read")
        state = temp / "workflow"
        p = plan("workflow", mode="workflow")
        p["task"]["steps"].append({"id": "second", "kind": "summary", "instruction": "use previous", "output": "text"})
        assert runner.run(grant(p, state), root, state)["result"]["calls"] == 2
        assert "previous_results" in requests[-1]["messages"][-1]["content"]
        ok("host planned multi-step workflow")
        state = temp / "context"
        p = plan("context")
        p["profiles"] = [dict(profiles[0])]
        p["profiles"][0]["max_context_bytes"] = 1
        # Changed model config must invalidate evaluation before dispatch.
        before = len(requests)
        try:
            runner.run(grant(p, state), root, state)
            raise AssertionError("stale evaluation accepted")
        except ValueError as e:
            assert "stale" in str(e)
        assert len(requests) == before
        ok("changed profile rejected before network")
        # Actual CLI signing / running uses a separate process, not Python test-only call injection.
        state = temp / "cli"
        p = plan("cli")
        f = temp / "plan.json"
        f.write_text(json.dumps(p))
        g = temp / "cli-grant.json"
        for args in [
            [
                "authorize",
                "--plan",
                str(f),
                "--state",
                str(state),
                "--authority-ref",
                "synthetic-test",
                "--out",
                str(g),
            ],
            ["run", "--grant", str(g), "--state", str(state)],
        ]:
            out = subprocess.run(
                [sys.executable, str(RUNTIME / "runner.py"), "--root", str(root), *args], capture_output=True, text=True
            )
            assert out.returncode == 0, out.stderr
        ok("standalone CLI authorization and execution without Codex SDK")
finally:
    server.shutdown()
    server.server_close()
report_path = BASE / "work/model-integration-results.json"
report_path.write_text(
    json.dumps(
        {"synthetic_only": True, "checks": checks, "passed": len(checks), "real_models_tested": False}, indent=2
    ),
    encoding="utf-8",
)
print(report_path.read_text())
