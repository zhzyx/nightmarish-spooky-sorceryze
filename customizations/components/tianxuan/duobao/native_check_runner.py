"""Trusted installed checks over immutable native compositions; no OS sandbox."""

from __future__ import annotations

import base64
import importlib.util
import json
import math
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from native_check_inputs import CONTRACT, CheckInputView
from native_evidence import EvidenceCache
from native_store import Conflict, NativeStoreError, _digest, _identifier, _json, _revision_id
from native_workspace import absolute


def _process_helper(path=None):
    path = (
        absolute(path) if path is not None else Path(__file__).resolve().parents[4] / "tools/ainative/owned_process.py"
    )
    spec = importlib.util.spec_from_file_location("_native_owned_process", path)
    if spec is None or spec.loader is None:
        raise NativeStoreError("Owned process helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeCheckRunner:
    """Host supplies authenticated identities, registry and installation verifier.

    Keys are unique per tenant (including across actors). Reserved/running rows
    are never stolen. Only persisted results can be replayed into EvidenceCache.
    """

    def __init__(
        self,
        cache: EvidenceCache,
        root: str | Path,
        registry: Mapping[str, dict[str, Any]],
        authorize: Callable[[str, str, str, str], bool],
        verify_installation: Callable[[str, dict[str, Any]], bool],
        process_helper_path: str | Path | None = None,
    ):
        if not callable(authorize) or not callable(verify_installation) or not registry:
            raise NativeStoreError("Explicit authority and installation verifier required")
        self.history_provider: Any | None = None
        self.cache = cache
        self.store = cache.store
        self.root = absolute(root)
        self.authorize = authorize
        self.verify_installation = verify_installation
        self._registry = json.loads(_json(dict(registry)))
        self.helper = _process_helper(process_helper_path)
        for check, spec in self._registry.items():
            _identifier(check)
            if set(spec) != {"argv", "env", "toolchain", "environment", "timeout", "log_bytes"}:
                raise NativeStoreError("Invalid installed registry fields")
            argv = spec["argv"]
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
                raise NativeStoreError("Fixed argument vector required")
            executable = absolute(argv[0])
            if not executable.is_file() or executable.suffix.lower() in {".bat", ".cmd"}:
                raise NativeStoreError("Direct executable required")
            if not isinstance(spec["env"], dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in spec["env"].items()
            ):
                raise NativeStoreError("Fixed environment required")
            _revision_id(spec["toolchain"])
            _revision_id(spec["environment"])
            timeout = spec["timeout"]
            if (
                isinstance(timeout, bool)
                or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout)
                or not 0 < timeout <= 86400
            ):
                raise NativeStoreError("Invalid timeout")
            if type(spec["log_bytes"]) is not int or not 1 <= spec["log_bytes"] <= 900000:
                raise NativeStoreError("Invalid log limit")
            cache._policy(check)
        with self.store._connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS native_check_runs (tenant TEXT NOT NULL, run_key TEXT NOT NULL, "
                "request TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant,run_key))"
            )

    def _allow(self, tenant, actor, check):
        for value in (tenant, actor, check):
            _identifier(value)
        if self.authorize(tenant, actor, check, "execute") is not True:
            raise NativeStoreError("Authenticated actor is not authorized to execute check")

    def context(self, check: str, candidate: str) -> dict[str, Any]:
        _revision_id(candidate)
        if check not in self._registry:
            raise NativeStoreError("Check is not installed")
        spec = self._registry[check]
        return {
            "toolchain": spec["toolchain"],
            "environment": spec["environment"],
            "parameters": {
                "registry": _digest(_json(spec).encode()),
                "execution_contract": CONTRACT,
                "input_view": _digest(Path(__file__).with_name("native_check_inputs.py").read_bytes()),
                "workspace_helpers": _digest(Path(__file__).with_name("native_workspace.py").read_bytes()),
                "process_helper": self.helper.implementation_fingerprint(),
                "runner": _digest(Path(__file__).read_bytes()),
                **({"history_provider": self.history_provider.fingerprint()} if self.history_provider else {}),
            },
        }

    def _save(self, tenant, key, value: dict[str, Any]) -> dict[str, Any]:
        with self.store._connection(write=True) as db:
            db.execute(
                "UPDATE native_check_runs SET payload=? WHERE tenant=? AND run_key=?", (_json(value), tenant, key)
            )
        return value

    def status(self, tenant, actor, key):
        _identifier(key)
        with self.store._connection() as db:
            row = db.execute(
                "SELECT payload FROM native_check_runs WHERE tenant=? AND run_key=?", (tenant, key)
            ).fetchone()
        if row is None:
            raise NativeStoreError("Run unavailable")
        value = json.loads(row["payload"])
        self._allow(tenant, actor, value["check"])
        return value

    def _record_result(self, tenant, key, value) -> dict[str, Any]:
        # Deliberately separate transactions: a crash here replays the identical
        # EvidenceCache request, never the subprocess.
        receipt = self.cache.record(
            tenant,
            value["actor"],
            value["evidence_request"],
            value["candidate"],
            value["check"],
            **value["context"],
            outcome=value["outcome"],
            log=value["log"].encode("utf-8"),
            expected_binding=value["binding"],
        )
        return self._save(tenant, key, {**value, "state": "complete", "evidence": receipt["id"]})

    def execute(
        self, tenant: str, actor: str, key: str, candidate: str, check: str, cancel: threading.Event | None = None
    ) -> dict[str, Any]:
        self._allow(tenant, actor, check)
        _identifier(key)
        context = self.context(check, candidate)
        spec = self._registry[check]
        if self.verify_installation(check, json.loads(_json(spec))) is not True:
            raise NativeStoreError("Host installation verification failed")
        binding = self.cache.binding(tenant, candidate, check, **context)
        request = _json(dict(actor=actor, candidate=candidate, check=check, context=context, binding=binding))
        value = dict(
            state="reserved",
            actor=actor,
            candidate=candidate,
            check=check,
            context=context,
            binding=binding,
            evidence_request="native-run-" + _digest(_json([tenant, key]).encode()),
            workspace=str(self.root / ("native-check-" + _digest(_json([tenant, key]).encode()))),
        )
        with self.store._connection(write=True) as db:
            row = db.execute(
                "SELECT request,payload FROM native_check_runs WHERE tenant=? AND run_key=?", (tenant, key)
            ).fetchone()
            if row is not None:
                if row["request"] != request:
                    raise Conflict("Stable run key is bound to another request")
                previous: dict[str, Any] | None = json.loads(row["payload"])
            else:
                db.execute("INSERT INTO native_check_runs VALUES (?,?,?,?)", (tenant, key, request, _json(value)))
                previous = None
        if previous is not None:
            if self.history_provider:
                self.history_provider.prepare(tenant, actor, candidate, check, materialize=False)
            if previous["state"] == "result":
                return self._record_result(tenant, key, previous)
            return previous
        try:
            hit = self.cache.lookup(tenant, candidate, check, **context)
            history: dict[str, Any] = (
                self.history_provider.prepare(tenant, actor, candidate, check, materialize=hit is None)
                if self.history_provider
                else dict(env={}, binding={})
            )
            value = self._save(tenant, key, {**value, "history_binding": history["binding"]})
            if hit is not None:
                if hit["evidence"]["binding"] != binding["binding"]:
                    raise Conflict("Check policy changed during cache lookup")
                return self._save(tenant, key, {**value, "state": "cached", "evidence": hit["evidence"]["id"]})
            view = CheckInputView.from_binding(self.store, tenant, binding)
            folder = Path(value["workspace"])
            folder.mkdir()
            inputs, outputs = folder / "input", folder / "output"
            outputs.mkdir()
            view.materialize(self.store, tenant, inputs)
            stamps = view.snapshot(inputs)
            value = self._save(tenant, key, {**value, "state": "running", "workspace": str(folder)})
            args = [arg.replace("{input}", str(inputs)).replace("{output}", str(outputs)) for arg in spec["argv"]]
            env = dict(spec["env"], **history["env"], DUOBAO_INPUT=str(inputs), DUOBAO_OUTPUT=str(outputs))
            reasons: list[str] = []

            def active():
                if cancel is not None and cancel.is_set():
                    if "cancelled" not in reasons:
                        reasons.append("cancelled")
                    return False
                return True

            with (folder / "process.log").open("w+b") as log:
                code = self.helper.run_owned(
                    args,
                    stdout=log,
                    env=env,
                    limit=spec["log_bytes"],
                    timeout=spec["timeout"],
                    active=active,
                    fail=reasons.append,
                    cwd=outputs,
                )
                log.seek(0)
                raw = log.read(spec["log_bytes"])
            try:
                if view.snapshot(inputs) != stamps:
                    reasons.append("input_pollution")
            except (OSError, NativeStoreError):
                reasons.append("input_pollution")
            if self.verify_installation(check, json.loads(_json(spec))) is not True:
                reasons.append("installation_changed")
            if self.history_provider:
                try:
                    if self.history_provider.prepare(tenant, actor, candidate, check, materialize=False) != history:
                        reasons.append("history_pollution")
                except (OSError, NativeStoreError):
                    reasons.append("history_pollution")
            outcome = "passed" if code == 0 and not reasons else "failed"
            # Bound the EvidenceCache envelope independently of arbitrary binary
            # output; the complete capped raw log remains in the owned workspace.
            facts = dict(
                exit_code=code,
                history_binding=history["binding"],
                reasons=reasons,
                raw_log_sha256=_digest(raw),
                output_base64=base64.b64encode(raw[:600000]).decode("ascii"),
                transcript_truncated=len(raw) > 600000,
            )
            value = self._save(
                tenant,
                key,
                {
                    **value,
                    "state": "result",
                    "outcome": outcome,
                    "log": _json(facts),
                    "exit_code": code,
                    "reasons": reasons,
                },
            )
            return self._record_result(tenant, key, value)
        except Exception as exc:
            # Includes uncertain spawn/cleanup and storage failures. Never retry
            # execution from this state; preserve files and ownership evidence.
            current = self.status(tenant, actor, key)
            if current["state"] not in {"result", "complete"}:
                self._save(tenant, key, {**current, "state": "held", "error": type(exc).__name__})
            raise
