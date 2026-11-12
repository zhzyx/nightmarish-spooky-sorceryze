"""Model-neutral local runtime. Trusted operator owns grants; models return proposals."""

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

import diting
from adapters import TransportUnknown, call, canonical, model_provenance

ROOT = Path(__file__).resolve().parents[5] / "framework"


def runtime_digest():
    folder = Path(__file__).resolve().parent
    return digest({
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ("runner.py", "adapters.py", "diting.py", "evaluate.py")
    })


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(v):
    return hashlib.sha256(canonical(v).encode()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def key():
    value = os.environ.get("GONGGONG_HOST_KEY", "")
    require(len(value) >= 32, "Host must provision GONGGONG_HOST_KEY (at least 32 characters) outside model context")
    return value.encode()


def signature(payload):
    return hmac.new(key(), canonical(payload).encode(), hashlib.sha256).hexdigest()


def verify_grant(grant, root, state):
    p = grant["payload"]
    require(hmac.compare_digest(signature(p), grant["signature"]), "Invalid host grant signature")
    require(p.get("runtime_sha256") == runtime_digest(), "Host runtime changed; reauthorize")
    require(p["expires_at"] > time.time(), "Host grant expired")
    require(
        p["framework_sha256"] == hashlib.sha256((root / "framework-manifest.json").read_bytes()).hexdigest(),
        "Framework changed; reauthorize",
    )
    require(Path(p["state_dir"]).resolve() == state.resolve(), "State directory differs from authorized budget ledger")
    require(p["authority_ref"].strip(), "Missing host authority reference")
    return p


def schema_check(value, schema):
    """Deliberately small closed schema dialect; reject unsupported keywords."""
    require(
        isinstance(schema, dict)
        and set(schema) <= {"type", "properties", "required", "items", "enum", "additionalProperties"},
        "Unsupported schema keywords",
    )
    kind = schema.get("type")
    types = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }
    require(kind in types, "Schema type required")
    require(
        isinstance(value, types[kind]) and not (isinstance(value, bool) and kind in {"integer", "number"}),
        "Output type mismatch",
    )
    if "enum" in schema:
        require(value in schema["enum"], "Output outside enum")
    if kind == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        require(set(required) <= set(value), "Required output field missing")
        require(schema.get("additionalProperties", False) is False, "Only closed objects supported")
        require(set(value) <= set(props), "Unexpected output fields")
        for k, v in value.items():
            schema_check(v, props[k])
    if kind == "array":
        require("items" in schema, "Array item schema required")
        for v in value:
            schema_check(v, schema["items"])


def validate_plan(p):
    t = p["task"]
    limits = p["limits"]
    profiles = p["profiles"]
    for field in ["id", "tenant_id", "project_id", "agent_id", "outcome", "authority_ref", "retention"]:
        require(isinstance(t.get(field), str) and t[field].strip(), "Missing task " + field)
    require(t["mode"] in {"single", "workflow", "autonomous"}, "Unknown execution mode")
    require(isinstance(t.get("steps"), list) and 0 < len(t["steps"]) <= 100, "Host plan requires 1..100 steps")
    require(t["mode"] != "single" or len(t["steps"]) == 1, "Single mode requires one step")
    require(isinstance(t.get("work_items"), list) and t["work_items"], "Work linkage required")
    require(isinstance(t.get("resources", {}), dict), "Resources must be host-provided map")
    for field, maximum in [("max_calls", 100), ("max_output_tokens", 32000)]:
        require(type(limits.get(field)) is int and 1 <= limits[field] <= maximum, "Invalid " + field)
    require(profiles and len({x["id"] for x in profiles}) == len(profiles), "Unique model profiles required")
    for model in profiles:
        model_provenance(model)  # Validate the requested identity before any dispatch.
        require(
            model["protocol"] in {"chat-completions", "ollama-chat", "gonggong-json"}, "Unsupported model transport"
        )
        require(
            type(model["max_context_bytes"]) is int and model["max_context_bytes"] > 0, "Context byte ceiling required"
        )
        require(0 < model.get("timeout_seconds", 30) <= 120, "Timeout must be 1..120 seconds")
        evidence = model["evaluation"]
        require(
            evidence["profile_digest"] == digest({k: v for k, v in model.items() if k != "evaluation"}),
            "Model evaluation is stale",
        )
        evidence_file = Path(evidence["evidence_ref"])
        report = read(evidence_file)
        require(
            hashlib.sha256(evidence_file.read_bytes()).hexdigest() == evidence["evidence_sha256"],
            "Evaluation evidence changed",
        )
        require(
            all(report[k] == evidence[k] for k in ["profile_digest", "scope", "passed_task_types"]),
            "Evaluation result mismatch",
        )
        require(evidence["scope"] in {"synthetic", "live"} and evidence["evidence_ref"], "Evaluation evidence required")
        require(
            t.get("validation_only", False) or evidence["scope"] == "live",
            "Synthetic model evaluation cannot authorize production",
        )
    ids = set()
    for step in t["steps"]:
        require(step["id"] not in ids, "Duplicate step")
        ids.add(step["id"])
        require(step["kind"] and isinstance(step["instruction"], str), "Step kind/instruction required")
        require(step.get("output") in {"text", "json"}, "Output must be text or json")
        if step["output"] == "json":
            require(isinstance(step.get("schema"), dict), "Output schema required")
        require(set(step.get("tools", [])) <= {"lookup_resource"}, "Unknown tool capability")
        require(not step.get("tools") or t["mode"] == "autonomous", "Tools require autonomous mode")


def connect(state):
    state.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(state / "runtime.sqlite", timeout=10)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.executescript("""CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, tenant TEXT NOT NULL, task_hash TEXT NOT NULL, grant_hash TEXT NOT NULL, task TEXT NOT NULL, status TEXT NOT NULL, result TEXT);
    CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL,time TEXT NOT NULL,kind TEXT NOT NULL,data TEXT NOT NULL);""")
    if "grant_json" not in {r[1] for r in cx.execute("PRAGMA table_info(jobs)")}:
        cx.execute("ALTER TABLE jobs ADD COLUMN grant_json TEXT")
    cx.commit()
    return cx


def emit(cx, jid, kind, data):
    stamp = now()
    cx.execute("INSERT INTO events(job,time,kind,data) VALUES(?,?,?,?)", (jid, stamp, kind, canonical(data)))
    cx.commit()
    return stamp


def events(cx, jid):
    return [
        {"seq": r[0], "time": r[1], "kind": r[2], "data": json.loads(r[3])}
        for r in cx.execute("SELECT seq,time,kind,data FROM events WHERE job=? ORDER BY seq", (jid,))
    ]


def jid_for(t):
    return digest([t["tenant_id"], t["id"]])


def context(root, t):
    with tempfile.TemporaryDirectory() as temp:
        mandate = Path(temp) / "mandate.json"
        mandate.write_text(
            canonical({"feature_id": t["id"], "outcome": t["outcome"], "authority_ref": t["authority_ref"]}),
            encoding="utf-8",
        )
        result = subprocess.run(
            ["node", str(root / "tools/agent-context.mjs"), t["agent_id"], str(mandate)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    require(result.returncode == 0, "Definition admission/context rejected: " + result.stderr.strip())
    return result.stdout


def step_context(root, step):
    registry = read(root / "framework-manifest.json")
    texts = []
    if step.get("skill"):
        matches = [s for s in [*registry["skills"], registry["upstream_skill_reporting"]] if s["name"] == step["skill"]]
        require(len(matches) == 1, "Skill not registered")
        texts.append((root / matches[0]["path"]).read_text(encoding="utf-8"))
    for ref in step.get("references", []):
        f = (root / ref).resolve()
        f.relative_to(root.resolve())
        require(f.suffix == ".md" and f.is_file(), "Reference must be an existing framework Markdown file")
        texts.append(f.read_text(encoding="utf-8"))
    return "\n\n".join(texts)


def export(root, state, t, cx, jid):
    a = next(a for a in read(root / "framework-manifest.json")["agents"] if a["id"] == t["agent_id"])
    try:
        return diting.export(root, state, t, a, events(cx, jid))
    except Exception as error:
        raise RuntimeError("Diting projection/delivery requires recovery: " + str(error)) from None


def set_status(cx, jid, status, result=None):
    cx.execute(
        "UPDATE jobs SET status=?,result=? WHERE id=?", (status, canonical(result) if result is not None else None, jid)
    )
    cx.commit()


@contextmanager
def worker_lock(state):
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "worker.lock", "a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def run(grant, root, state):
    verify_grant(grant, root, state)
    with worker_lock(state):
        return _run(grant, root, state)


def _run(grant, root, state):
    p = verify_grant(grant, root, state)
    validate_plan(p)
    t = p["task"]
    base = context(root, t)
    jid = jid_for(t)
    with closing(connect(state)) as cx:
        cx.execute("BEGIN IMMEDIATE")
        old = cx.execute("SELECT task_hash,grant_hash,status,result FROM jobs WHERE id=?", (jid,)).fetchone()
        if old:
            require(old[0] == digest(t) and old[1] == digest(grant), "Task ID reused with changed task/grant")
            if old[2] == "completed":
                cx.rollback()
                return {"status": "completed", "result": json.loads(old[3]), "replayed": True}
            require(old[2] == "ready", "Job requires explicit reconciliation; status=" + old[2])
            cx.execute("UPDATE jobs SET status='running' WHERE id=?", (jid,))
            cx.commit()
        else:
            cx.execute(
                "INSERT INTO jobs(id,tenant,task_hash,grant_hash,task,status,result,grant_json) VALUES(?,?,?,?,?,?,NULL,?)",
                (jid, t["tenant_id"], digest(t), digest(grant), canonical(t), "running", canonical(grant)),
            )
            cx.commit()
            emit(cx, jid, "request", {"outcome": t["outcome"]})
        try:
            export(root, state, t, cx, jid)  # Durable source and request must exist before model dispatch.
            history = events(cx, jid)
            outputs = {e["data"]["step_id"]: e["data"]["value"] for e in history if e["kind"] == "step_result"}
            calls = sum(e["kind"] == "call_start" for e in history)
            for step in t["steps"]:
                if step["id"] in outputs:
                    continue
                instruction = (
                    'Return only JSON: {"action":"final","value":...} or {"action":"tool","name":"lookup_resource","arguments":{"key":"..."}}. Tool requests are proposals; no authority or shell execution. Allowed tools: '
                    + canonical(step.get("tools", []))
                    + ". Required value format: "
                    + canonical({"output": step["output"], "schema": step.get("schema")})
                )
                messages = [
                    {"role": "system", "content": base + "\n" + step_context(root, step) + "\n" + instruction},
                    {
                        "role": "user",
                        "content": canonical({
                            "instruction": step["instruction"],
                            "input": t.get("input"),
                            "previous_results": outputs,
                            "available_resource_keys": list(t.get("resources", {})),
                        }),
                    },
                ]
                eligible = [m for m in p["profiles"] if step["kind"] in m["evaluation"]["passed_task_types"]]
                require(eligible, "No evaluated model for task type; needs human/capability admission")
                completed = False
                for model in eligible:
                    while calls < p["limits"]["max_calls"]:
                        verify_grant(grant, root, state)
                        if len(canonical(messages).encode()) > model["max_context_bytes"]:
                            emit(
                                cx,
                                jid,
                                "route_skip",
                                {"model": model["id"], "reason": "context byte ceiling; no silent truncation"},
                            )
                            break
                        calls += 1
                        started = emit(
                            cx, jid, "call_start", {"call": calls, "step_id": step["id"], "profile_id": model["id"]}
                        )
                        try:
                            response = call(model, messages, p["limits"]["max_output_tokens"])
                        except TransportUnknown as error:
                            emit(
                                cx,
                                jid,
                                "call_end",
                                {
                                    "call": calls,
                                    "step_id": step["id"],
                                    "profile": {"protocol": model["protocol"], "model": model["model"]},
                                    "started_at": started,
                                    "status": "unknown",
                                    **model_provenance(model),
                                    "error": str(error),
                                },
                            )
                            export(root, state, t, cx, jid)
                            set_status(cx, jid, "needs_reconciliation")
                            return {"status": "needs_reconciliation", "reason": str(error)}
                        emit(
                            cx,
                            jid,
                            "call_end",
                            {
                                "call": calls,
                                "step_id": step["id"],
                                "profile": {"protocol": model["protocol"], "model": model["model"]},
                                "started_at": started,
                                "status": "received",
                                **response,
                            },
                        )
                        try:
                            require(response["finish_reason"] == "stop", "Provider output incomplete/refused")
                            action = json.loads(response["text"])
                            require(isinstance(action, dict), "Action object required")
                            if action.get("action") == "tool":
                                require(set(action) == {"action", "name", "arguments"}, "Invalid tool envelope")
                                require(
                                    action["name"] in step.get("tools", []) and action["name"] == "lookup_resource",
                                    "Tool not authorized",
                                )
                                require(
                                    isinstance(action["arguments"], dict) and set(action["arguments"]) == {"key"},
                                    "Invalid tool arguments",
                                )
                                verify_grant(grant, root, state)
                                name = action["arguments"]["key"]
                                require(name in t.get("resources", {}), "Resource not authorized")
                                value = t["resources"][name]
                                emit(
                                    cx,
                                    jid,
                                    "tool_result",
                                    {"step_id": step["id"], "tool": "lookup_resource", "key": name, "call": calls},
                                )
                                export(root, state, t, cx, jid)
                                messages.extend([
                                    {"role": "assistant", "content": response["text"]},
                                    {
                                        "role": "user",
                                        "content": canonical({"tool_result": value, "untrusted_data": True}),
                                    },
                                ])
                                continue
                            require(
                                set(action) == {"action", "value"} and action["action"] == "final",
                                "Invalid final envelope",
                            )
                            value = action["value"]
                            if step["output"] == "text":
                                require(isinstance(value, str) and bool(value.strip()), "Nonempty text value required")
                            else:
                                schema_check(value, step["schema"])
                            verify_grant(grant, root, state)
                            outputs[step["id"]] = value
                            emit(cx, jid, "step_result", {"step_id": step["id"], "value": value, "call": calls})
                            export(root, state, t, cx, jid)
                            completed = True
                            break
                        except (ValueError, TypeError, KeyError) as error:
                            emit(
                                cx,
                                jid,
                                "validation_failure",
                                {"step_id": step["id"], "call": calls, "reason": str(error)},
                            )
                            export(root, state, t, cx, jid)
                            # Move to the next evaluated profile; no unlimited repair loop.
                            messages.append({
                                "role": "user",
                                "content": "Previous candidate rejected: "
                                + str(error)
                                + ". Produce a corrected proposal.",
                            })
                            break
                    if completed:
                        break
                if not completed:
                    set_status(cx, jid, "needs_attention")
                    return {
                        "status": "needs_attention",
                        "reason": "No valid result within capabilities/budget; human review or new authorized task required",
                    }
            emit(cx, jid, "completed", {"candidate_only": True})
            receipt = export(root, state, t, cx, jid)
            result = {
                "outputs": outputs,
                "acceptance": "candidate_requires_business_validation",
                "calls": calls,
                "diting_submission_id": receipt["submission_id"],
            }
            set_status(cx, jid, "completed", result)
            return {"status": "completed", "result": result}
        except Exception:
            set_status(cx, jid, "needs_attention")
            raise


def recover(grant, root, state, action):
    require(action in {"retry", "cancel"}, "Invalid reconciliation decision")
    verify_grant(grant, root, state)
    with worker_lock(state):
        return _recover(grant, root, state, action)


def _recover(grant, root, state, action):
    p = verify_grant(grant, root, state)
    t = p["task"]
    jid = jid_for(t)
    with closing(connect(state)) as cx:
        # Must only be used after the original worker has stopped. Operator owns reconciliation.
        row = cx.execute("SELECT grant_hash,status,grant_json FROM jobs WHERE id=?", (jid,)).fetchone()
        require(row, "Unknown authorized job")
        require(row[1] in {"running", "needs_reconciliation", "needs_attention"}, "Job not recoverable")
        if row[0] != digest(grant):
            require(p.get("replaces_grant") == row[0] and row[2], "Renewal must bind previous grant")
            old = json.loads(row[2])["payload"]
            omit = {"expires_at", "replaces_grant"}
            require(
                {k: v for k, v in old.items() if k not in omit} == {k: v for k, v in p.items() if k not in omit},
                "Renewal cannot change task, capabilities, framework or budget",
            )
            cx.execute("UPDATE jobs SET grant_hash=?,grant_json=? WHERE id=?", (digest(grant), canonical(grant), jid))
            cx.commit()
        history = events(cx, jid)
        ended = {e["data"]["call"] for e in history if e["kind"] == "call_end"}
        if any(e["kind"] == "completed" for e in history):
            require(action == "retry", "Completion already durable; retry delivery/finalization, cannot cancel")
            receipt = export(root, state, t, cx, jid)
            result = {
                "outputs": {e["data"]["step_id"]: e["data"]["value"] for e in history if e["kind"] == "step_result"},
                "acceptance": "candidate_requires_business_validation",
                "calls": sum(e["kind"] == "call_start" for e in history),
                "diting_submission_id": receipt["submission_id"],
            }
            set_status(cx, jid, "completed", result)
            return {"status": "completed", "result": result, "budget_reset": False}
        if any(e["kind"] == "operator_reconciliation" and e["data"]["decision"] == "cancel" for e in history):
            require(action == "cancel", "Cancellation already durable; retry cancellation delivery, cannot resume")
            export(root, state, t, cx, jid)
            set_status(cx, jid, "cancelled")
            return {"status": "cancelled", "budget_reset": False}
        resolved = {
            e["data"]["call"]
            for e in history
            if e["kind"] in {"step_result", "tool_result", "validation_failure", "validation_interrupted"}
        }
        for e in history:
            if e["kind"] == "call_end" and e["data"]["status"] == "received" and e["data"]["call"] not in resolved:
                emit(
                    cx,
                    jid,
                    "validation_interrupted",
                    {
                        "call": e["data"]["call"],
                        "step_id": e["data"]["step_id"],
                        "reason": "worker stopped before validation; preserve known usage without accepting candidate",
                    },
                )
            if e["kind"] == "call_start" and e["data"]["call"] not in ended:
                d = e["data"]
                profile = next(x for x in p["profiles"] if x["id"] == d["profile_id"])
                emit(
                    cx,
                    jid,
                    "call_end",
                    {
                        "call": d["call"],
                        "step_id": d["step_id"],
                        "profile": {"protocol": profile["protocol"], "model": profile["model"]},
                        "started_at": e["time"],
                        "status": "unknown",
                        **model_provenance(profile),
                        "error": "Worker interrupted; operator reconciliation; usage unavailable",
                    },
                )
        emit(cx, jid, "operator_reconciliation", {"decision": action, "authority_ref": p["authority_ref"]})
        export(root, state, t, cx, jid)
        set_status(cx, jid, "ready" if action == "retry" else "cancelled")
        return {"status": "ready" if action == "retry" else "cancelled", "budget_reset": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("authorize")
    a.add_argument("--plan", required=True)
    a.add_argument("--state", required=True)
    a.add_argument("--authority-ref", required=True)
    a.add_argument("--ttl", type=int, default=3600)
    a.add_argument("--out", required=True)
    a = sub.add_parser("renew")
    a.add_argument("--grant", required=True)
    a.add_argument("--ttl", type=int, default=3600)
    a.add_argument("--out", required=True)
    for name in ["run", "recover"]:
        a = sub.add_parser(name)
        a.add_argument("--grant", required=True)
        a.add_argument("--state", required=True)
        if name == "recover":
            a.add_argument("--action", choices=["retry", "cancel"], required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    state = Path(args.state).resolve() if hasattr(args, "state") else None
    if args.command == "authorize":
        plan = read(args.plan)
        validate_plan(plan)
        require(0 < args.ttl <= 86400, "TTL must be 1..86400 seconds")
        context(root, plan["task"])
        payload = {
            **plan,
            "runtime_sha256": runtime_digest(),
            "state_dir": str(state),
            "authority_ref": args.authority_ref,
            "expires_at": time.time() + args.ttl,
            "framework_sha256": hashlib.sha256((root / "framework-manifest.json").read_bytes()).hexdigest(),
        }
        with open(args.out, "x", encoding="utf-8") as stream:
            stream.write(canonical({"payload": payload, "signature": signature(payload)}))
        result = {"grant": args.out, "scope": "local trusted operator; key is not a production IAM service"}
    elif args.command == "renew":
        old = read(args.grant)
        require(hmac.compare_digest(signature(old["payload"]), old["signature"]), "Invalid prior grant")
        require(0 < args.ttl <= 86400, "TTL must be 1..86400 seconds")
        payload = {**old["payload"], "expires_at": time.time() + args.ttl, "replaces_grant": digest(old)}
        renewed = {"payload": payload, "signature": signature(payload)}
        verify_grant(renewed, root, Path(payload["state_dir"]))
        with open(args.out, "x", encoding="utf-8") as stream:
            stream.write(canonical(renewed))
        result = {
            "grant": args.out,
            "budget_reset": False,
            "next": "explicit recover retry/cancel after reconciliation",
        }
    else:
        grant = read(args.grant)
        result = run(grant, root, state) if args.command == "run" else recover(grant, root, state, args.action)
    print(canonical(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ": " + str(error), file=sys.stderr)
        sys.exit(1)
