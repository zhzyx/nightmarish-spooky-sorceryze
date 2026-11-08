"""macOS Desktop retry exercise used by the private complete_delivery runner.

Run the parent runner directly with Apple's Python from Codex desktop. All model,
GitHub, Git, editor settings, application targets and projects are private data.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_client(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_retry(command, env, project, original, prepared, case, folder, model_calls):
    client_type = load_client("editor_instruction_client").EditorInstructionClient
    checks = []
    command_id = 0
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def check(name, value, detail=None):
        assert value, (name, detail)
        checks.append(name)

    def wait(predicate, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            if process.poll() is not None:
                raise AssertionError("Private editor exited before expected result")
            time.sleep(0.03)
        raise AssertionError("Private retry timed out")

    def fixture(name, value=None):
        nonlocal command_id
        command_id += 1
        path = project / "retry-command.json"
        temporary = path.with_suffix(".pending")
        temporary.write_text(json.dumps({"id": command_id, "name": name, "value": value}))
        temporary.replace(path)
        if name in {"quit", "finish"}:
            return
        result_path = project / "retry-command-result.json"
        return wait(
            lambda: (
                (lambda v: v if v.get("id") == command_id else None)(json.loads(result_path.read_text()))
                if result_path.exists()
                else None
            )
        )

    def start_client():
        ready = project / "retry-ready.json"
        wait(ready.exists)
        client = client_type(project, json.loads(ready.read_text())["pid"])
        wait(lambda: client.context().get("context", {}).get("delivery_retry_available"))
        return client

    try:
        client = start_client()
        initial = client.context()
        model_calls_before_recovery = len(model_calls)
        check("authenticated_desktop_peer", initial.get("authenticated_desktop_peer") is True)
        journals = list((original / ".git/gonggong-delivery-finalization").glob("*.json"))
        check("one_authoritative_original_transaction", len(journals) == 1)
        journal = journals[0]
        before = journal.read_bytes()
        old = json.loads(before)
        check(
            "actual_original_activation_pending",
            old["last_receipt"]["completion_verified"] and old["last_receipt"]["stage"] == "activation_pending",
        )
        writes_before = json.loads((folder / "remote-state.json").read_text())["writes"]
        original_context = initial["context"]
        if case == "retry-cold":
            fixture("quit")
            stdout, stderr = process.communicate(timeout=30)
            check("first_host_exited_normally", process.returncode == 0)
            for name in ("retry-ready.json", "retry-command.json", "retry-command-result.json"):
                (project / name).unlink(missing_ok=True)
            env = dict(env, DELIVERY_FIXTURE_PHASE="restore")
            process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            client = start_client()
            restored = client.context()["context"]
            check(
                "same_owner_and_snapshot_from_real_cold_history",
                restored["owner"] == original_context["owner"]
                and restored["snapshot_id"] == original_context["snapshot_id"],
            )
            check(
                "fresh_process_domain_after_restart",
                restored["host_instance_id"] != original_context["host_instance_id"],
            )
            stale = client.retry_delivery(original_context, "old-process-context")
            check("old_process_context_rejected", stale.get("error") == "chat_instruction_state_changed")
        else:
            stdout = stderr = ""
        manifest = Path(prepared["ready_manifest"])
        manifest.write_bytes(prepared["ready_manifest_bytes"])
        check("exact_original_sidecar_restored", manifest.read_bytes() == prepared["ready_manifest_bytes"])
        managed_registration = None
        if case == "retry-managed":
            helper = Path(prepared["trusted_installation"]) / "tools/editor_candidate_activation.py"
            acceptance_out = Path(env["DELIVERY_FIXTURE_ACCEPTANCE_OUT"])
            registration_path = acceptance_out.with_name(acceptance_out.stem + "-explicit-managed-registration.json")
            import editor_managed_native_entry as managed

            identity = managed.context(
                manifest,
                json.loads(manifest.read_text()),
                {
                    "candidate": prepared["candidate"],
                    "signed_commit": prepared["signed_commit"],
                    "tree": prepared["tree"],
                },
            )
            prepared["managed_payload_directory"] = str(managed.snapshot_directory(identity))
            registration = subprocess.run(
                [
                    env["DELIVERY_FIXTURE_PYTHON"],
                    "-B",
                    str(helper),
                    "--manifest",
                    str(manifest),
                    "--out",
                    str(registration_path),
                    "--entry-type",
                    "managed_native_app_link",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            managed_registration = json.loads(registration_path.read_text()) if registration_path.exists() else {}
            acceptance_out.with_name(acceptance_out.stem + "-managed-cli.json").write_text(
                json.dumps(
                    {
                        "exit_code": registration.returncode,
                        "stdout": registration.stdout,
                        "stderr": registration.stderr,
                        "actual_result": managed_registration,
                    },
                    indent=2,
                )
                + "\n"
            )
            check(
                "explicit_trusted_cli_registered_managed_entry",
                registration.returncode == 0
                and managed_registration.get("ok")
                and managed_registration.get("entry_type") == "managed_native_app_link",
                {"result": managed_registration, "stderr": registration.stderr},
            )
            prepared["managed_payload_directory"] = str(Path(managed_registration["canonical_payload"]).parent)
            logical = folder / "Original Private.app"
            check(
                "logical_entry_is_exact_payload_link",
                logical.is_symlink() and os.readlink(logical) == managed_registration["canonical_payload"],
            )
            for delay in [1, 2]:
                time.sleep(delay)
                strict = subprocess.run(
                    ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(logical)], capture_output=True
                )
                check("registered_link_retains_strict_signature_" + str(delay), strict.returncode == 0)
            check("registration_preserves_original_pending_journal", journal.read_bytes() == before)
        context = client.context()["context"]
        if case == "retry-boundaries":
            for name in ("tools", "automatic", "consultation", "draft"):
                value = "PRIVATE_DRAFT" if name == "draft" else name == "consultation"
                fixture(name, value)
                blocked = client.context()["context"]
                rejected = client.retry_delivery(blocked, "blocked-" + name)
                check("reject_" + name, not rejected.get("ok"))
                fixture(name, "" if name == "draft" else name != "consultation")
            fixture("child")
            blocked = client.context()["context"]
            check(
                "reject_child",
                client.retry_delivery(blocked, "blocked-child").get("error") == "parent_session_required",
            )
            fixture("parent")
            context = client.context()["context"]
            malformed = dict(context, generation=1.5)
            check(
                "reject_changed_live_generation",
                client.retry_delivery(malformed, "wrong-live-generation").get("error")
                == "chat_instruction_state_changed",
            )
            tcp = load_client("editor_control_client").EditorClient(project, process.pid)
            denied = tcp.route({
                "intent": "engine_operation",
                "source": "desktop.codex",
                "request_id": "tcp-retry-denied",
                "operation": {"action": "retry_pending_delivery", "value": {"expected": context}},
            })
            check("tcp_cannot_mint_terminal_capability", denied.get("error") == "trusted_desktop_peer_required")
        if case in {"retry-stop", "retry-interrupted"}:
            (folder / "finalizer-running").unlink(missing_ok=True)
        for attempt in range(10):
            context = client.context()["context"]
            action_id = "real-terminal-retry-" + str(attempt)
            accepted = client.retry_delivery(context, action_id)
            if accepted.get("error") not in {"chat_instruction_state_changed", "editor_busy", "models_loading"}:
                break
            time.sleep(0.2)
        check(
            "real_host_action_started",
            accepted.get("ok")
            and accepted.get("delivery_retry_started")
            and accepted.get("business_completed") is False,
            accepted,
        )
        repeated = client.retry_delivery(context, action_id)
        check("duplicate_request_is_idempotent", repeated.get("idempotent") is True)
        busy = client.context()["context"]
        check("concurrent_new_action_refused", not client.retry_delivery(busy, "concurrent-retry").get("ok"))
        if case in {"retry-stop", "retry-interrupted"}:
            wait(lambda: (folder / "finalizer-running").exists())
            if case == "retry-stop":
                fixture("stop")
                child_pid = int((folder / "finalizer-running").read_text())

                def child_gone():
                    try:
                        os.kill(child_pid, 0)
                    except ProcessLookupError:
                        return True
                    return False

                wait(child_gone, timeout=15)
                check("stop_terminated_actual_retry_child", True)
                stopped = client.status(action_id)
                check(
                    "stop_is_unknown_not_completed",
                    not stopped.get("ok") and stopped.get("delivery_stage") == "unknown",
                )
                denied = client.retry_delivery(client.context()["context"], "new-id-after-stop")
                check(
                    "stop_blocks_new_action_in_same_live_host",
                    denied.get("error") == "terminal_state_requires_readback",
                )
            else:
                stopped = client.status(action_id)
                check(
                    "live_action_still_running_before_normal_close",
                    stopped.get("routing_status") == "running" and not stopped.get("business_completed"),
                )
            check("stop_preserves_original_transaction", journal.read_bytes() == before)
            fixture("quit")
            stdout, stderr = process.communicate(timeout=30)
            for name in ("retry-ready.json", "retry-command.json", "retry-command-result.json"):
                (project / name).unlink(missing_ok=True)
            env = dict(env, DELIVERY_FIXTURE_PHASE="restore")
            process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            client = start_client()
            restored = client.status(action_id)
            check(
                "cold_status_keeps_failed_host_action",
                not restored.get("ok") and restored.get("receipt_restored") is True,
            )
            if case == "retry-interrupted":
                check("cold_started_route_becomes_unknown", restored.get("routing_status") == "execution_unknown")
            check(
                "no_issue_writes_during_stop_or_restore",
                json.loads((folder / "remote-state.json").read_text())["writes"] == writes_before,
            )
            time.sleep(0.5)
            check(
                "cold_history_does_not_dispatch_worker",
                journal.read_bytes() == before
                and len(list((original / ".git/gonggong-delivery-retries").glob("*.json"))) == 0,
            )
            fixture("quit")
            final_stdout, final_stderr = process.communicate(timeout=30)
            check("native_stop_restore_exit_zero", process.returncode == 0)
            return subprocess.CompletedProcess(
                command, process.returncode, stdout + final_stdout, stderr + final_stderr
            ), {
                "checks": checks,
                "host_action_status": stopped,
                "cold_restored_status": restored,
                "production_operations": False,
            }
        terminal = wait(lambda: (lambda v: v if v.get("completion_verified") else None)(client.status(action_id)))
        check(
            "actual_new_worker_and_local_terminal_completed",
            terminal.get("ok") and terminal.get("business_completed") and terminal.get("delivery_stage") == "completed",
        )
        check("original_pending_journal_unchanged", journal.read_bytes() == before)
        state = json.loads((folder / "remote-state.json").read_text())
        check("no_repeat_issue_or_declaration_writes", state["writes"] == writes_before)
        check("no_model_requests_during_recovery", len(model_calls) == model_calls_before_recovery)
        retries = list((original / ".git/gonggong-delivery-retries").glob("*.json"))
        check("one_real_retry_journal", len(retries) == 1)
        actual = json.loads(retries[0].read_text())["result"]
        check("fresh_authorization_separate_from_original", actual["nonce"] != actual["original_transaction"]["nonce"])
        check(
            "same_original_transaction_snapshot", actual["original_transaction"]["snapshot_id"] == actual["snapshot_id"]
        )
        check("actual_activation_not_not_applicable", actual["engine_launch_activation"]["state"] == "activated")
        if case == "retry-managed":
            activation = actual["engine_launch_activation"]
            check(
                "default_retry_reused_registered_managed_mode",
                activation.get("entry_type") == "managed_native_app_link" and activation.get("reused") is True,
            )
            check(
                "same_immutable_payload_and_source_manifest",
                activation.get("canonical_payload") == managed_registration["canonical_payload"]
                and activation.get("source_manifest_sha256") == hashlib.sha256(manifest.read_bytes()).hexdigest(),
            )
        check(
            "target_is_private_fixture_app",
            str(folder / "Original Private.app") == actual["engine_launch_activation"]["entry"],
        )
        signature = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", actual["engine_launch_activation"]["entry"]],
            capture_output=True,
        )
        check("private_updated_entry_strict_signature", signature.returncode == 0)
        check(
            "ordinary_closed_issue_instruction_stays_blocked", not client.context()["context"]["instruction_available"]
        )
        fixture("finish")
        final_stdout, final_stderr = process.communicate(timeout=30)
        check("native_exit_zero", process.returncode == 0)
        completed = subprocess.CompletedProcess(
            command, process.returncode, stdout + final_stdout, stderr + final_stderr
        )
        return completed, {
            "checks": checks,
            "original_journal_sha256": hashlib.sha256(before).hexdigest(),
            "actual_retry_receipt": actual,
            "explicit_managed_registration": managed_registration,
            "recovery_model_requests": len(model_calls) - model_calls_before_recovery,
            "recovery_issue_writes": len(state["writes"]) - len(writes_before),
            "host_action_status": terminal,
            "production_operations": False,
        }
    except BaseException as error:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        stdout, stderr = process.communicate(timeout=15)
        progress = project / "retry-progress.json"
        detail = progress.read_text() if progress.exists() else "No GDScript progress receipt"
        raise RuntimeError(
            str(error)
            + "\nPrivate script progress:\n"
            + detail[-12000:]
            + "\nPrivate stdout:\n"
            + stdout[-12000:]
            + "\nPrivate stderr:\n"
            + stderr[-12000:]
        ) from error
