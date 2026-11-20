"""Operator-owned signer/runtime process; never import into the app server.

The fixed broker configuration pins the host-http template and framework. Only
requirement input is read from stdin. GONGGONG_HOST_KEY exists in this process,
never in app-server or model installation environments. Process ownership is the
caller's responsibility; uncertain exit is not permission to call again.
"""

import argparse
import base64
import hashlib
import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

from native_model_host import executable_sha256
from native_observations import model_observation

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "customizations/platforms/ai-access/host-http/runtime"))
import runner  # noqa: E402


def load_config(path, digest):
    source = Path(path)
    runner.require(
        source.is_absolute() and source.is_file() and not source.is_symlink(), "Absolute broker configuration required"
    )
    raw = source.read_bytes()
    runner.require(hashlib.sha256(raw).hexdigest() == digest, "Broker configuration changed")
    config = json.loads(raw)
    runner.require(
        set(config) - {"context_transport", "catalog_bindings"}
        == {
            "template",
            "template_sha256",
            "framework",
            "framework_sha256",
            "runtime_sha256",
            "node",
            "node_sha256",
            "python",
            "python_sha256",
            "state",
            "key_file",
            "authority_ref",
        },
        "Closed broker configuration required",
    )
    for name in ("template", "framework", "node", "python", "state", "key_file"):
        runner.require(Path(config[name]).is_absolute(), "Absolute broker paths required")
    template = Path(config["template"])
    runner.require(
        hashlib.sha256(template.read_bytes()).hexdigest() == config["template_sha256"], "Broker template changed"
    )
    runner.require(
        executable_sha256(config["node"]) == config["node_sha256"],
        "Admitted Node executable changed",
    )
    runner.require(Path(config["node"]).name.lower() in {"node", "node.exe"}, "Direct Node executable required")
    runner.require(
        executable_sha256(config["python"]) == config["python_sha256"],
        "Admitted Python executable changed",
    )
    runner.require(runner.runtime_digest() == config["runtime_sha256"], "Host runtime changed")
    runner.require(
        hashlib.sha256((Path(config["framework"]) / "framework-manifest.json").read_bytes()).hexdigest()
        == config["framework_sha256"],
        "Framework manifest changed",
    )
    return config, runner.read(template)


def runtime_state(config, plan, task):
    central = plan.get("central_budget")
    root = Path(config["state"])
    if central is not None:
        runner.require(
            root.resolve() == Path(central["state_dir"]).resolve(),
            "Broker state must use the admitted central budget root",
        )
        return root / "tasks" / runner.jid_for(task)
    return root / task["id"]


def execute(config, template, request, *, recover=False):
    runner.require(
        set(request) == {"role", "entry", "tenant", "actor", "source", "document", "scopes", "complexity"},
        "Closed planning request required",
    )
    runner.require(
        (request["role"] == "yanshi" and template["task"]["agent_id"] == "yanshi")
        or (
            request["role"] == "reviewer"
            and template["task"]["agent_id"] != "yanshi"
            and template["task"].get("role") == "reviewer"
        ),
        "Admitted independent role template required",
    )
    runner.require(
        template["task"]["mode"] == "single" and len(template["task"]["steps"]) == 1,
        "Single planning proposal required",
    )
    runner.require(len(runner.canonical(request).encode()) <= 100000, "Planning input exceeds installed context bound")
    runner.require(
        isinstance(request["entry"], str)
        and len(request["entry"]) == 64
        and all(c in "0123456789abcdef" for c in request["entry"]),
        "Exact entry digest required",
    )
    # Configuration owns all instructions, role, profiles, evaluation and budgets.
    plan = json.loads(runner.canonical(template))
    task = plan["task"]
    task.update(id=request["entry"], tenant_id=request["tenant"], input=request, authority_ref=config["authority_ref"])
    for profile in plan["profiles"]:
        if profile["protocol"] == "codex-native-role":
            runner.require(profile.get("entry_role") == request["role"], "Installed CLI role mismatch")
    if request["role"] == "yanshi" and all(p["protocol"] == "codex-native-role" for p in plan["profiles"]):
        # Local IDs only link steps inside this plan. Supply portable, distinct
        # choices so the provider can enforce the host's finite naming contract.
        fields = task["steps"][0]["schema"]["properties"]
        fields["source"] = {"type": "string", "enum": [request["source"]]}
        item = fields["tasks"]["items"]["properties"]
        local_id = {"type": "string", "enum": ["task-" + str(n) for n in range(1, 65)]}
        item["id"] = local_id
        item["dependencies"]["items"] = local_id
        item["scope"] = {"type": "string", "enum": sorted(request["scopes"])}
        item["complexity"] = {"type": "string", "enum": sorted(request["complexity"])}
    if request["role"] == "reviewer" and all(p["protocol"] == "codex-native-role" for p in plan["profiles"]):
        # The reviewer sees the actual text and file digests. The original host
        # validates its returned coverage against the immutable candidate bytes.
        inspected = {}
        for name, encoded in request["scopes"].items():
            content = base64.b64decode(encoded, validate=True)
            inspected[name] = {"sha256": hashlib.sha256(content).hexdigest(), "text": content.decode("utf-8")}
        task["input"] = {**request, "scopes": inspected}
        properties = task["steps"][0]["schema"]["properties"]
        for field, value in (
            ("candidate", request["source"]),
            ("reviewer", request["complexity"]["reviewer"]),
            ("criteria", request["document"]["source"]["definition"]["acceptance"]),
        ):
            properties[field] = {"type": "string", "enum": [value]}
        properties["inspected"] = {
            "type": "object",
            "properties": {name: {"type": "string", "enum": [item["sha256"]]} for name, item in inspected.items()},
            "required": list(inspected),
            "additionalProperties": False,
        }
    state = runtime_state(config, plan, task)
    framework = Path(config["framework"])
    # runner.context uses the host Node CLI; resolve only the pinned installation.
    os.environ["PATH"] = str(Path(config["node"]).parent)
    os.environ["GONGGONG_PYTHON"] = config["python"]
    os.chdir(Path(config["node"]).parent)
    key_path = Path(config["key_file"])
    runner.require(key_path.is_file() and not key_path.is_symlink(), "Broker key unavailable")
    os.environ["GONGGONG_HOST_KEY"] = key_path.read_text(encoding="utf-8").strip()
    runner.validate_plan(plan)
    runner.context(framework, task)  # Existing role admission, not a synthetic approval.
    payload = {
        **plan,
        "runtime_sha256": runner.runtime_digest(),
        "state_dir": str(state),
        "authority_ref": config["authority_ref"],
        "expires_at": time.time() + 3600,
        "framework_sha256": hashlib.sha256((framework / "framework-manifest.json").read_bytes()).hexdigest(),
    }
    grant = {"payload": payload, "signature": runner.signature(payload)}
    state.mkdir(parents=True, exist_ok=True)
    binding = {"request": request, "template": runner.digest(template), "authority": config["authority_ref"]}
    intent = state / "entry-intent.json"
    receipt_path = state / "entry-receipt.json"
    if recover:
        saved = runner.read(intent)
        runner.require(saved["binding"] == binding, "Recovery binding changed")
        grant = saved["grant"]
        runner.require(grant["signature"] == runner.signature(grant["payload"]), "Recovery grant signature changed")
        if receipt_path.exists():
            return runner.read(receipt_path)

        database = (state / "runtime.sqlite").as_uri() + "?mode=ro"
        with closing(sqlite3.connect(database, uri=True)) as connection:
            old = connection.execute(
                "SELECT task_hash,grant_hash,status,result FROM jobs WHERE id=?", (runner.jid_for(task),)
            ).fetchone()
        runner.require(
            old is not None
            and old[0] == runner.digest(task)
            and old[1] == runner.digest(grant)
            and old[2] == "completed",
            "Runtime outcome unknown; read-only recovery cannot replay",
        )
        result = {"status": "completed", "result": json.loads(old[3])}
    else:
        # Exclusively created before invoking the external runtime. A previous intent
        # needs trusted reconciliation even when a process crashed before first call.
        with intent.open("x", encoding="utf-8") as stream:
            stream.write(runner.canonical(dict(binding=binding, grant=grant)))
            stream.flush()
            os.fsync(stream.fileno())
        result = runner.run(grant, framework, state)
    runner.require(result["status"] == "completed", "Planner result unknown/incomplete")
    outputs = result["result"]["outputs"]
    runner.require(len(outputs) == 1, "One planner result required")
    receipt = {
        "input_digest": runner.digest(request),
        "source": request["source"],
        "proposal": next(iter(outputs.values())),
        "runtime_state": str(state),
    }
    if all(profile["protocol"] == "codex-native-role" for profile in plan["profiles"]):
        with closing(sqlite3.connect((state / "runtime.sqlite").as_uri() + "?mode=ro", uri=True)) as cx:
            cx.row_factory = sqlite3.Row
            calls = cx.execute(
                "SELECT data FROM events WHERE job=? AND kind='call_end' ORDER BY seq", (runner.jid_for(task),)
            ).fetchall()
        receipt["model_calls"] = []
        for row in calls:
            call = json.loads(row["data"])
            usage = (call.get("protocol_evidence") or {}).get("usage") or {}
            receipt["model_calls"].append({
                "requested_model": call["requested_model"],
                **model_observation(usage.get("observed_model"), usage.get("raw")),
            })
    with receipt_path.open("x", encoding="utf-8") as stream:
        stream.write(runner.canonical(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    config, template = load_config(args.config, args.sha256)
    raw = sys.stdin.buffer.read(100001)
    runner.require(len(raw) <= 100000, "Planning request too large")
    print(runner.canonical(execute(config, template, json.loads(raw), recover=args.recover)))
