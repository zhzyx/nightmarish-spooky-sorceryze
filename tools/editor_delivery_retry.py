"""Retry only activation for one already verified, host-bound terminal transaction.

The live request is a new Desktop host action. Its nonce/generation never replace
the original transaction's identity or business declaration. Original finalizer
journals are read-only; every retry has its own durable uncertainty/result record.
"""

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editor_delivery_finalize import installed_module

delivery = installed_module("retry_finalizer", "tools/editor_delivery_finalize.py")
require = delivery.require
canonical = delivery.canonical


def sha(value):
    return hashlib.sha256(value).hexdigest()


def original_transaction(root, request):
    """Select a unique immutable pending transaction, never a caller-selected path."""
    common, repository, _ = delivery._candidate.identity(root)
    folder = common / "gonggong-delivery-finalization"
    require(
        folder.is_dir() and not folder.is_symlink() and folder.resolve() == folder,
        "Pending delivery journal is unavailable",
    )
    names = sorted(folder.glob("*.json"))
    require(len(names) <= 1024, "Pending delivery journal selection is ambiguous")
    matches = []
    binding = request["binding"]
    for path in names:
        saved = delivery.read_json(path)
        scope = saved.get("scope", {})
        if not isinstance(scope, dict) or any(
            scope.get(key) != expected
            for key, expected in {
                "repository": repository,
                "issue": binding["issue"],
                "request_id": binding["request_id"],
                "owner": request["owner"],
                "source_root": str(root),
                "candidate": request["expected_candidate"],
            }.items()
        ):
            continue
        receipt = saved.get("last_receipt", {})
        require(isinstance(receipt, dict), "Pending delivery receipt is unavailable")
        if receipt.get("snapshot_id") != request["snapshot_id"]:
            continue
        require(
            receipt.get("kind") == "native_delivery_finalization"
            and receipt.get("completion_verified") is True
            and receipt.get("ok") is False
            and receipt.get("stage") == "activation_pending",
            "Original delivery state is not a verified pending activation",
        )
        key = sha(canonical({k: v for k, v in scope.items() if k != "acceptance_sha256"}).encode())
        require(path.name == key + ".json", "Original transaction journal identity differs")
        require(scope.get("signed_commit") == request["expected_signed_commit"], "Original signed head differs")
        facts = receipt.get("host_facts", {})
        require(isinstance(facts, dict), "Original delivery facts are unavailable")
        for key in ("repository", "issue", "request_id", "candidate", "signed_commit", "tree"):
            require(facts.get(key) == scope.get(key), "Original delivery facts differ: " + key)
        require(
            facts.get("pull_request") == f"https://github.com/{repository}/pull/{request['pr']}"
            and facts.get("pr_state") == "MERGED"
            and facts.get("delivered_paths_differ") == [],
            "Original PR binding differs",
        )
        declaration = delivery.acceptance_declaration(receipt.get("acceptance_declaration", {}).get("items"))
        require(
            declaration == receipt.get("acceptance_declaration")
            and declaration["sha256"] == scope.get("acceptance_sha256"),
            "Original acceptance declaration differs",
        )
        for key in ("owner", "source_root", "issue", "request_id"):
            require(receipt.get(key) == scope.get(key), "Original receipt identity differs: " + key)
        require(
            type(receipt.get("generation")) is int
            and receipt["generation"] >= 0
            and isinstance(receipt.get("nonce"), str)
            and 0 < len(receipt["nonce"]) <= 128,
            "Original execution identity is unavailable",
        )
        matches.append((path, saved, receipt, declaration))
    require(len(matches) == 1, "A unique verified pending delivery is required")
    path, saved, receipt, declaration = matches[0]
    original_bytes = path.read_bytes()
    require(sha(original_bytes) == request["original_journal_sha256"], "Original pending journal changed")
    original = {
        "schema_version": 1,
        **{key: receipt[key] for key in ("owner", "snapshot_id", "generation", "nonce", "source_root")},
        "binding": binding,
        "pr": request["pr"],
        "expected_candidate": saved["scope"]["candidate"],
        "expected_signed_commit": saved["scope"]["signed_commit"],
        "acceptance_items": declaration["items"],
    }
    return common, path, original_bytes, original, saved["scope"]


def retry(root, request):
    root = Path(root).absolute()
    result = {
        "schema_version": 1,
        "kind": "native_delivery_retry",
        "ok": False,
        "completion_verified": False,
        "mutations_may_have_started": False,
        "stage": "validation",
    }
    for key in (
        "owner",
        "snapshot_id",
        "generation",
        "nonce",
        "source_root",
        "host_action_request_id",
        "original_journal_sha256",
        "engine_pid",
        "host_instance_id",
    ):
        result[key] = request.get(key)
    binding = request.get("binding", {})
    result["issue"] = binding.get("issue") if isinstance(binding, dict) else None
    result["request_id"] = binding.get("request_id") if isinstance(binding, dict) else None
    try:
        require(
            set(request)
            == {
                "schema_version",
                "kind",
                "owner",
                "snapshot_id",
                "generation",
                "nonce",
                "source_root",
                "binding",
                "pr",
                "expected_candidate",
                "expected_signed_commit",
                "original_journal_sha256",
                "host_action_request_id",
                "engine_pid",
                "host_instance_id",
            }
            and request.get("kind") == "native_delivery_retry",
            "Invalid terminal retry request; new business declarations are not accepted",
        )
        require(
            isinstance(request.get("host_action_request_id"), str)
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", request["host_action_request_id"])
            and re.fullmatch(r"[a-f0-9]{64}", request.get("original_journal_sha256", "")),
            "Invalid terminal retry identity",
        )
        require(
            type(request.get("engine_pid")) is int
            and request["engine_pid"] > 1
            and isinstance(request.get("host_instance_id"), str)
            and re.fullmatch(r"[a-f0-9]{32}", request["host_instance_id"]),
            "Invalid live host process domain",
        )
        common, original_path, original_bytes, original, scope = original_transaction(root, request)
        # Validate both identities against the same real checkout, not closed-Issue intake.
        delivery.host_scope(root, original)
        delivery.host_scope(root, request)
        repository = binding["repository"]
        lock_key = sha(canonical([repository, binding["issue"], binding["request_id"]]).encode())
        folder = common / "gonggong-delivery-retries"
        require(not folder.is_symlink(), "Invalid retry journal directory")
        folder.mkdir(mode=0o700, exist_ok=True)
        key = sha(
            canonical([
                repository,
                binding["issue"],
                binding["request_id"],
                request["owner"],
                request["host_action_request_id"],
            ]).encode()
        )
        path = folder / (key + ".json")
        fingerprint = sha(canonical(request).encode())
        with delivery._candidate.binding_lock(common / "gonggong-delivery-finalization" / (lock_key + ".lock")):
            require(original_path.read_bytes() == original_bytes, "Original transaction changed before retry")
            prior_paths = sorted(folder.glob("*.json"))
            require(len(prior_paths) <= 1024, "Retry journal selection is ambiguous")
            for previous_path in prior_paths:
                previous = delivery.read_json(previous_path)
                if previous.get("original_scope") == scope:
                    require(
                        previous.get("state") in {"started", "finished"},
                        "A prior retry state is unknown; authoritative readback is required",
                    )
                    if previous.get("state") == "finished":
                        prior_result = previous.get("result", {})
                        require(
                            isinstance(prior_result, dict)
                            and prior_result.get("kind") == "native_delivery_retry"
                            and prior_result.get("completion_verified") is True
                            and prior_result.get("stage") in {"completed", "activation_pending"},
                            "A prior retry result is unknown; authoritative readback is required",
                        )
                require(
                    previous.get("original_scope") != scope
                    or previous.get("state") != "started"
                    or previous_path == path,
                    "A prior retry execution is unknown; authoritative readback is required",
                )
            if path.exists():
                prior = delivery.read_json(path)
                require(prior.get("fingerprint") == fingerprint, "Retry request identity conflicts")
                require(prior.get("state") == "finished", "Retry execution is unknown; read back before another action")
                return prior["result"]
            actor = delivery.submission.writer(repository)
            report = delivery.submission.inspect_pr(root, repository, request["pr"])
            require(
                all(
                    report.get(k) == scope.get(k)
                    for k in ("repository", "issue", "request_id", "candidate", "signed_commit", "tree")
                )
                and report.get("pr_state") == "MERGED"
                and report.get("delivered_paths_differ") == [],
                "Original signed delivery differs on authoritative readback",
            )
            require(
                delivery.submission.git(root, "merge-base", scope["candidate"], report["current_main"])
                == scope["candidate"],
                "Original candidate is not contained in main",
            )
            checks = delivery.verified_checks(repository, request["pr"], scope["signed_commit"])
            known_types = {v["name"] for v in delivery.submission.work_items.config(root)[1]}
            issue, statuses = delivery.issue_readback(repository, binding["issue"], binding["request_id"], known_types)
            require(
                issue.get("state") == "CLOSED"
                and issue.get("stateReason") == "COMPLETED"
                and statuses == ["status:done"],
                "Only a verified completed Issue may retry activation",
            )
            result.update(
                host_facts=delivery.compact_report(report),
                ci=checks,
                acceptance_declaration=delivery.acceptance_declaration(original["acceptance_items"]),
                original_transaction={
                    **scope,
                    "snapshot_id": original["snapshot_id"],
                    "generation": original["generation"],
                    "nonce": original["nonce"],
                    "pr": original["pr"],
                    "journal_sha256": request["original_journal_sha256"],
                },
                actor={"login": actor["login"], "databaseId": actor["databaseId"]},
                completion_verified=True,
                stage="activation",
                mutations_may_have_started=True,
            )
            # Durable uncertainty is recorded before the sole possible effect.
            saved = {
                "fingerprint": fingerprint,
                "state": "started",
                "live_authorization": request,
                "original_scope": scope,
            }
            delivery._candidate.atomic_json(path, saved)
            result["engine_launch_activation"] = delivery._activation.after_delivery(root, report)
            # The original transaction had an applicable entry. Removing its
            # binding cannot turn that known failed activation into success.
            result["ok"] = result["engine_launch_activation"].get("state") == "activated"
            result["stage"] = "completed" if result["ok"] else "activation_pending"
            require(original_path.read_bytes() == original_bytes, "Original transaction changed during retry")
            result["host_action_receipt"] = str(path)
            saved.update(state="finished", result=result)
            delivery._candidate.atomic_json(path, saved)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        result["ok"] = False
        if result["mutations_may_have_started"]:
            result["stage"] = "activation_unknown"
        result["error"] = str(error)[:1000]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = retry(args.source_root, delivery.read_json(args.request))
    delivery._candidate.atomic_json(args.out, result)
    return 0 if result["completion_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
