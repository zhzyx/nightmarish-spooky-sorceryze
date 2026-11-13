"""Installed adapter for a live, native-confirmed complete design contract.

The native owner supplies live execution observations, never model output. This
module cannot restore a parent/reviewer from disk, execute arbitrary commands or
accept a producer's verdict. Its grants are consumed only by that native owner.
"""

import hashlib
import importlib.util
import json
import re
import shutil
import signal
import sys
import tempfile
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def authority_snapshot(verified):
    row = verified["row"]
    # Comments and API timestamps are not task definitions. Body/title/state
    # changes are; intake separately checks current workflow labels every time.
    revision = {k: row.get(k) for k in ("number", "html_url", "title", "body", "state", "state_reason")}
    return {"actor": verified["actor"], "source_sha256": digest(revision)}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def live(request):
    marker = Path(request["host_liveness_path"])
    require(marker.is_absolute(), "Missing live parent owner")
    value = json.loads(marker.read_text(encoding="utf8"))
    require(
        value.get("active") is True and value.get("request_nonce") == request["request_nonce"],
        "Parent generation cancelled",
    )


def run_command(bridge, root, request, arguments, payload=None, timeout=120, require_success=True):
    """Reuse the installed bounded process-group / Windows Job owner."""
    implementation = Path(__file__).resolve().parents[3] / "tools/ainative/owned_process.py"
    spec = importlib.util.spec_from_file_location("parent_owned_process", implementation)
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    cancelled = False

    def cancel(_number, _frame):
        # The outer provenance owner may terminate this bridge while its
        # command owns a different POSIX group. Keep this owner alive long
        # enough for run_owned's finally block to close that group/Job.
        nonlocal cancelled
        cancelled = True

    def active():
        if cancelled:
            return False
        try:
            live(request)
            return True
        except (OSError, ValueError, KeyError):
            return False

    def fail(reason):
        raise ValueError("Parent adapter process " + reason)

    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr, tempfile.TemporaryFile() as stdin:
        if payload is not None:
            stdin.write(payload.encode("utf8"))
        stdin.seek(0)
        previous = {}
        try:
            for number in (signal.SIGTERM, signal.SIGINT):
                previous[number] = signal.signal(number, cancel)
            code = owned.run_owned(
                arguments,
                stdout=stdout,
                stderr=stderr,
                stdin=stdin,
                env=bridge.host_environment(root),
                limit=16 * 1024 * 1024,
                timeout=timeout,
                active=active,
                fail=fail,
            )
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
        require(not cancelled, "Parent adapter owner cancelled")
        live(request)
        stdout.seek(0)
        require(code == 0 or (not require_success and code is not None), "Installed parent command failed")
        return stdout.read().decode("utf8")


def source(bridge, root, request):
    installation = Path(__file__).resolve().parents[3]
    checked = json.loads(
        run_command(
            bridge,
            root,
            request,
            [
                sys.executable,
                "-E",
                "-s",
                "-X",
                "utf8",
                str(installation / "customizations/components/issue-workorders/issue_gate.py"),
                "--repo",
                str(root),
                "--issue",
                str(request["issue_number"]),
                "--request-id",
                request["request_id"],
                "--tenant",
                "gonggong-workspace",
                "--intake-only",
                "--include-issue-source",
            ],
        )
    )
    verified = checked["verified_issue_source"]
    actor = verified["actor"]
    require(isinstance(actor, dict) and actor.get("login"), "Authenticated source actor unavailable")
    env = bridge.host_environment(root)
    gh = bridge.find_gh(env, root)
    require(gh, "GitHub authority unavailable")

    def api(endpoint):
        return json.loads(run_command(bridge, root, request, [gh, "api", endpoint], timeout=45))

    require(api("user")["login"] == actor["login"], "Operator changed during intake")
    permission = api(f"repos/{actor['repo']}/collaborators/{actor['login']}/permission")
    require(
        permission.get("permission") in {"write", "maintain", "admin"}
        or permission.get("role_name") in {"write", "maintain", "admin"},
        "Current write authority required",
    )
    return verified


def contract_from_source(verified, root, request):
    row = verified["row"]
    require(
        row["number"] == request["issue_number"] and row["state"] == "open", "Original task is not current and open"
    )
    blocks = re.findall(r"^```gonggong-parent-contract\s*\n(.*?)\n```\s*$", row["body"], re.M | re.S)
    if not blocks:
        return None
    require(len(blocks) == 1 and len(blocks[0].encode()) <= 65536, "Ambiguous or oversized original contract")
    contract = json.loads(blocks[0])
    require(
        contract.get("version") == 1 and contract.get("scope") == "complete-original-task",
        "Original full scope declaration required",
    )
    require(
        contract.get("request_id") == request["request_id"] and contract.get("issue_number") == request["issue_number"],
        "Original task identity mismatch",
    )
    design = request["design"]
    filename = root / "design-docs" / (request["request_id"] + ".md")
    require(not filename.is_symlink() and filename.resolve().is_relative_to(root), "Design escaped workspace")
    require(
        hashlib.sha256(filename.read_bytes()).hexdigest() == design["sha256"] == contract.get("design_sha256"),
        "Original confirmed design changed",
    )
    require(
        design["workspace"] == str(root)
        and str(design["issue_number"]) == str(row["number"])
        and design["request_id"] == request["request_id"],
        "Confirmed design identity mismatch",
    )
    orders = request["orders"]
    require(isinstance(orders, list) and 0 < len(orders) <= 16, "Missing live registered orders")
    expected = []
    numbers = set()
    for order in orders:
        require(
            order.get("acceptance_criteria_valid") is True and order["number"] not in numbers,
            "Incomplete registered criteria",
        )
        numbers.add(order["number"])
        for criterion in order["acceptance_criteria"]:
            expected.append((order["number"], criterion["id"], criterion["requirement"]))
    criteria = contract.get("criteria")
    require(
        isinstance(criteria, list) and len(criteria) == len(expected) and len(criteria) > 0,
        "Original criteria coverage incomplete",
    )
    require(len({c["id"] for c in criteria}) == len(criteria), "Original criterion IDs must be unique")
    actual = []
    for c in criteria:
        require(
            isinstance(c.get("id"), str) and c["id"] and c.get("kind") in {"acceptance", "delivery"},
            "Invalid original criterion",
        )
        actual.append((c["order"], c["criterion"], c["requirement"]))
    require(
        sorted(expected) == sorted(actual) and len(set(actual)) == len(actual), "Partial or unrelated execution mapping"
    )
    require(any(c["kind"] == "delivery" for c in criteria), "Original delivery acceptance must be explicit")
    return contract


def candidate(bridge, root, request):
    installation = Path(__file__).resolve().parents[3]
    env = bridge.host_environment(root)
    node = env.get("GONGGONG_NODE") or shutil.which("node", path=env.get("PATH"))
    require(node, "Node host runtime unavailable")
    policy = {
        "tenant_id": "gonggong-workspace",
        "request_id": request["request_id"],
        "source_ref": request["source_ref"],
    }
    result = json.loads(
        run_command(
            bridge,
            root,
            request,
            [
                node,
                str(installation / "customizations/components/repository-dispatch/acceptance.mjs"),
                "capture",
                str(root),
            ],
            json.dumps(policy),
        )
    )
    require(result.get("ok") is True, "Candidate capture failed")
    return result["candidate"]


def choose_action(request, contract):
    """Finite choices from the current native scheduler, not text or disk flags."""
    observations = request.get("observations", [])
    expected = {c["order"] for c in contract["criteria"]}
    require(
        len(observations) == len(expected) and {o["number"] for o in observations} == expected,
        "Live execution coverage changed",
    )
    if request.get("unknown_effect"):
        return "readback_required"
    if request.get("reserved_decision"):
        return "decision_required"
    if all(o.get("accepted") is True and o.get("decision_sha256") for o in observations):
        return "complete"
    if request.get("no_progress", 0) >= 2:
        return "kuafu_required"
    if any(o.get("ready") is True and o.get("state") in {"waiting", "completed"} for o in observations):
        return "dispatch_registered"
    if any(o.get("state") in {"running", "review", "pending_host"} for o in observations):
        return "wait_event"
    return "decision_required"


def execute(bridge, root, request):
    root = Path(root).resolve()
    live(request)
    operation = request.get("operation")
    require(operation in {"bind", "check", "authorize", "blocker"}, "Invalid parent operation")
    verified = source(bridge, root, request)
    live(request)
    contract = contract_from_source(verified, root, request)
    result = {"ok": True, "request_nonce": request["request_nonce"]}
    if contract is None:
        require(operation == "bind", "Original complete contract removed")
        return dict(result, state="unmapped", reason="original_complete_contract_absent")
    owner = request["owner"]
    require(
        all(isinstance(owner.get(k), str) and owner[k] for k in ("conversation", "token", "authority_ref", "operator")),
        "Missing native confirmation owner",
    )
    authority = authority_snapshot(verified)
    require(
        owner["operator"] == verified["actor"]["login"] and request.get("confirmation_source") == authority,
        "Native confirmation authority changed",
    )
    binding = dict(authority, contract=contract, owner=owner, design=request["design"], workspace=str(root))
    if operation != "bind":
        require(binding == request.get("binding"), "Source, authority, original criteria or owner changed")
    request = dict(request, source_ref=verified["row"]["html_url"])
    current = candidate(bridge, root, request)
    live(request)
    if operation == "bind":
        return dict(result, state="bound", binding=binding, candidate=current)
    action = choose_action(request, contract)
    facts = digest({
        "binding": binding,
        "candidate": current,
        "observations": request["observations"],
        "unknown_effect": request.get("unknown_effect"),
        "reserved_decision": request.get("reserved_decision"),
    })
    # Code/transcript/audit churn alone is not verified business progress.
    # Only actual registered execution/independent-review observations advance
    # this bounded loop; the full candidate remains pinned separately above.
    progress = digest({"binding": binding, "observations": request["observations"]})
    if operation == "authorize":
        require(
            request["checked_candidate"] == current
            and request["checked_facts"] == facts
            and request["checked_action"] == action,
            "Candidate or execution changed before action",
        )
    if operation == "blocker":
        require(action == "kuafu_required", "No bounded continuation failure")
        # Existing deduplicated incident route owns its private storage and
        # unknown delivery readback. This adapter adds no task ledger.
        installation = Path(__file__).resolve().parents[3]
        receipt = run_command(
            bridge,
            root,
            request,
            [
                sys.executable,
                str(installation / "customizations/components/issue-workorders/kuafu_incident.py"),
                "--repo",
                str(root),
                "detect",
                "--issue",
                str(request["issue_number"]),
                "--request-id",
                request["request_id"],
                "--action",
                "dispatch",
                "--evidence",
                "parent-completion:" + facts,
            ],
        )
        result["blocker_receipt"] = {"returncode": 0, "output": receipt[:16384]}
    return dict(result, state="checked", action=action, facts_sha256=facts, progress_sha256=progress, candidate=current)


def finalize(bridge, root, request):
    """Fresh guard immediately before the existing journaled finalizer.

    The native completion owner constructs the guard only after its live
    independent decisions pass. The ordinary delivery worker retains all
    branch/CI/signed-candidate/Issue readbacks and its unknown-outcome journal.
    """
    root = Path(root).resolve()
    guard = request["parent_completion_guard"]
    live(guard)
    require(
        request["owner"] == guard["owner"]["conversation"] and request["nonce"] == guard["request_nonce"],
        "Delivery owner changed",
    )
    require(Path(request["source_root"]).resolve() == root, "Delivery workspace changed")
    verified = source(bridge, root, guard)
    authority = authority_snapshot(verified)
    contract = contract_from_source(verified, root, guard)
    require(
        contract is not None
        and dict(authority, contract=contract, owner=guard["owner"], design=guard["design"], workspace=str(root))
        == guard["binding"],
        "Delivery original source or authority changed",
    )
    require(
        authority == guard["confirmation_source"] and guard["owner"]["operator"] == authority["actor"]["login"],
        "Delivery confirmation changed",
    )
    require(choose_action(guard, contract) == "complete", "Independent complete acceptance required before delivery")
    installation = Path(__file__).resolve().parents[3]
    env = bridge.host_environment(root)
    node = env.get("GONGGONG_NODE") or shutil.which("node", path=env.get("PATH"))
    require(node, "Node host runtime unavailable")
    verifier = str(installation / "customizations/components/repository-dispatch/acceptance.mjs")
    current = json.loads(
        run_command(bridge, root, guard, [node, verifier, "current", str(root)], json.dumps(guard["checked_candidate"]))
    )
    require(current.get("ok") is True, "Delivery candidate changed during approval")
    proofs = guard["live_decisions"]
    numbers = {c["order"] for c in contract["criteria"]}
    require(
        len(proofs) == len(numbers) and {p["number"] for p in proofs} == numbers,
        "Incomplete independent delivery proofs",
    )
    for proof in proofs:
        require(
            hashlib.sha256(proof["decision_json"].encode()).hexdigest() == proof["decision_sha256"],
            "Independent decision changed",
        )
        observation = next(o for o in guard["observations"] if o["number"] == proof["number"])
        require(
            observation.get("accepted") is True and observation["decision_sha256"] == proof["decision_sha256"],
            "Independent decision owner changed",
        )
        decision = json.loads(proof["decision_json"])
        require(
            {c["id"] for c in decision["criteria"]}
            == {c["criterion"] for c in contract["criteria"] if c["order"] == proof["number"]},
            "Independent original coverage changed",
        )
        checked = json.loads(
            run_command(
                bridge,
                root,
                guard,
                [node, verifier, "verify-finalization", decision["candidate"]["root"]],
                proof["decision_json"],
            )
        )
        require(checked.get("ok") is True, "Independent evidence changed during approval")
    items = request["acceptance_items"]
    require(
        len(items) == len(contract["criteria"]) and {i["id"] for i in items} == {c["id"] for c in contract["criteria"]},
        "Final delivery original coverage incomplete",
    )
    for item in items:
        original = next(c for c in contract["criteria"] if c["id"] == item["id"])
        require(
            item["state"] == "done" and item["acceptance"] == original["requirement"],
            "Final delivery declaration differs from original criteria",
        )
    live(guard)
    with tempfile.TemporaryDirectory(prefix="gonggong-parent-delivery-") as folder:
        input_path, output_path = Path(folder) / "request.json", Path(folder) / "result.json"
        # Do not expose full native authority/candidate manifests to the normal
        # finalizer's journal; its existing request schema stays unchanged.
        payload = {
            k: v
            for k, v in request.items()
            if k not in {"parent_completion_guard", "active", "request_nonce", "_cancel_path"}
        }
        input_path.write_text(json.dumps(payload), encoding="utf8")
        run_command(
            bridge,
            root,
            guard,
            [
                sys.executable,
                "-I",
                str(installation / "tools/editor_delivery_finalize.py"),
                "--source-root",
                str(root),
                "--request",
                str(input_path),
                "--out",
                str(output_path),
            ],
            timeout=600,
            require_success=False,
        )
        require(output_path.is_file(), "Delivery outcome unknown; read original finalization journal")
        return json.loads(output_path.read_text(encoding="utf8"))


def delivery_module():
    filename = Path(__file__).resolve().parents[3] / "tools/editor_delivery_finalize.py"
    spec = importlib.util.spec_from_file_location("parent_delivery_reader", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readback_delivery(root, request):
    """Read an uncertain original delivery; never reopen intake or replay writes.

    This explicit installed command consumes the retained original request and
    existing finalizer journal. It grants no live owner/reviewer after restart.
    Verified activation-pending receipts remain resumable through the existing
    native delivery-retry action; this reader does not activate installations.
    """
    root = Path(root).resolve()
    delivery = delivery_module()
    guard = request["parent_completion_guard"]
    require(
        request["nonce"] == guard["request_nonce"] and request["owner"] == guard["owner"]["conversation"],
        "Original delivery identity differs",
    )
    common, binding, _, _ = delivery.host_scope(root, request)
    repository = binding["repository"]
    # Readback needs the original authenticated reader, not a new write grant.
    # This path cannot publish, activate, or restore live business acceptance.
    actor = json.loads(delivery.submission.work_items.gh("api", "user"))
    original_actor = guard["binding"]["actor"]
    require(
        actor["login"] == original_actor["login"] and str(actor.get("id")) == original_actor["user_id"],
        "Original delivery operator changed",
    )
    report = delivery.submission.inspect_pr(root, repository, request["pr"])
    require(
        report["candidate"] == request["expected_candidate"]
        and report["signed_commit"] == request["expected_signed_commit"]
        and report["issue"] == request["binding"]["issue"]
        and report["request_id"] == request["binding"]["request_id"]
        and report["pr_state"] == "MERGED"
        and report["delivered_paths_differ"] == [],
        "Original signed delivery changed",
    )
    require(
        delivery.submission.git(root, "merge-base", report["candidate"], report["current_main"]) == report["candidate"],
        "Original candidate is absent from main",
    )
    declaration = delivery.acceptance_declaration(request["acceptance_items"])
    scope = {k: report[k] for k in ("repository", "issue", "request_id", "candidate", "signed_commit", "tree")}
    scope.update(owner=request["owner"], source_root=str(root), acceptance_sha256=declaration["sha256"])
    key = hashlib.sha256(
        delivery.canonical({k: v for k, v in scope.items() if k != "acceptance_sha256"}).encode()
    ).hexdigest()
    journal = delivery.read_json(common / "gonggong-delivery-finalization" / (key + ".json"))
    require(journal.get("scope") == scope, "No matching original delivery transaction")
    paths = list((common / "gonggong-delivery-finalization/attempts").glob("*.json"))
    require(len(paths) <= 4096, "Original delivery attempts exceed bounded readback")
    attempts = [delivery.read_json(p) for p in paths]

    def matches_attempt(attempt):
        if (
            not all(
                attempt.get(k) == request.get(k) for k in ("owner", "snapshot_id", "generation", "nonce", "source_root")
            )
            or attempt.get("mutations_may_have_started") is not True
        ):
            return False
        if attempt.get("issue") != scope["issue"] or attempt.get("request_id") != scope["request_id"]:
            return False
        facts = attempt.get("host_facts", {})
        if any(
            k in facts and facts[k] != scope[k]
            for k in ("repository", "issue", "request_id", "candidate", "signed_commit", "tree")
        ):
            return False
        if "pull_request" in facts and facts["pull_request"] != report["pull_request"]:
            return False
        return "acceptance_declaration" not in attempt or attempt["acceptance_declaration"] == declaration

    require(
        any(matches_attempt(a) for a in attempts), "Original execution nonce has no observed attempt; preserve unknown"
    )
    checks = delivery.verified_checks(repository, request["pr"], request["expected_signed_commit"])
    known_types = {v["name"] for v in delivery.submission.work_items.config(root)[1]}
    issue, statuses = delivery.issue_readback(repository, scope["issue"], scope["request_id"], known_types)
    blocks = re.findall(r"^```gonggong-parent-contract\s*\n(.*?)\n```\s*$", issue["body"], re.M | re.S)
    require(
        len(blocks) == 1 and json.loads(blocks[0]) == guard["binding"]["contract"], "Original complete contract changed"
    )
    closed = issue.get("state") == "CLOSED" and issue.get("stateReason") == "COMPLETED" and statuses == ["status:done"]
    return {
        "ok": True,
        "kind": "parent_delivery_readback",
        "owner": request["owner"],
        "nonce": request["nonce"],
        "completion_verified": closed,
        "host_facts": delivery.compact_report(report),
        "ci": checks,
        "activation": journal.get("last_receipt", {}).get("engine_launch_activation", {"state": "unknown"}),
        "read_only": True,
        "business_acceptance_restored": False,
        "mutations_replayed": False,
    }
