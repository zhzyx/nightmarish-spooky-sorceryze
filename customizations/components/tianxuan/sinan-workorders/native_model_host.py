"""Trusted installed host port; request data cannot select execution configuration.

The callback authenticates the *installed* profile. It is not a model approval.
No proposal path is written. Remote cancellation is deliberately unknown.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path


def executable_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class NativeContextSession:
    """Private bounded mailbox; the existing owned-process helper owns all children."""

    def __init__(self, host, request, authority, max_calls):
        if type(max_calls) is not int or not 1 <= max_calls <= 16:
            raise ValueError("Native context session requires 1..16 cumulative calls")
        if request.get("request_id") != authority.binding["execution"]:
            raise ValueError("Context session task identity mismatch")
        if any(e["kind"] == "model_call_start" for e in authority.events()):
            raise ValueError("Existing model execution cannot restart; reconcile durable receipts")
        self.host, self.request, self.authority = host, request, authority
        self.profile, self.config = host.configuration()
        self.binding = digest([request, authority.identity, self.config])
        self.sequence, self.max_calls, self.total_bytes = 0, max_calls, 0
        self.command = None
        self.last_diagnostic = None
        self.temp = tempfile.TemporaryDirectory(prefix="native-context-")
        self.mailbox = Path(self.temp.name).resolve()
        self.owner = self.mailbox.stat()
        self.streams = [tempfile.TemporaryFile() for _ in range(3)]
        self.deadline = time.monotonic() + self.profile["timeout"]

    def _check(self, authority=True, installation=True):
        stat = self.mailbox.lstat()
        if self.mailbox.is_symlink() or (stat.st_dev, stat.st_ino) != (self.owner.st_dev, self.owner.st_ino):
            raise ValueError("Private mailbox identity changed")
        if installation and self.host.configuration()[1] != self.config:
            raise ValueError("Installed session changed")
        if authority:
            self.authority.check("model_turn")
        if time.monotonic() >= self.deadline:
            raise ValueError("Cumulative session deadline exceeded")
        if self.command and (self.command.overflow.is_set() or self.command.read_error.is_set()):
            raise ValueError("Session output invalid")

    def turn(self, messages):
        self._check()
        self.sequence += 1
        size = len(encoded(messages))
        self.total_bytes += size
        if self.sequence > self.max_calls or size > 1048576 or self.total_bytes > 8388608:
            raise ValueError("Cumulative session input ceiling exceeded")
        if self.command is None:
            source, out, err = self.streams
            source.write(
                encoded(
                    dict(
                        schema=2,
                        request=self.request,
                        installed={
                            **{k: v for k, v in self.profile.items() if k not in {"node", "timeout"}},
                            "config_digest": self.config,
                        },
                        mailbox=str(self.mailbox),
                        binding=self.binding,
                        max_calls=self.max_calls,
                    )
                )
            )
            source.seek(0)
            self.command = self.host.helper.OwnedCommand(
                [self.profile["node"], str(self.host.wrapper)],
                stdin=source,
                stdout=out,
                stderr=err,
                env=self.profile["env"],
                limit=524288,
                cwd=self.host.wrapper.parent,
            )
        packet = dict(binding=self.binding, sequence=self.sequence, messages=messages, input_digest=digest(messages))
        tmp = self.mailbox / (str(self.sequence) + ".input.tmp")
        with tmp.open("xb") as f:
            f.write(encoded(packet))
            f.flush()
            os.fsync(f.fileno())
        self._check()
        self.authority.emit(
            "model_call_start",
            {
                "sequence": self.sequence,
                "binding": self.binding,
                "input_digest": digest(messages),
                "messages": messages,
            },
        )
        tmp.replace(self.mailbox / (str(self.sequence) + ".input.json"))
        output = self.mailbox / (str(self.sequence) + ".output.json")
        while True:
            self._check(authority=False, installation=False)
            if output.exists():
                if output.is_symlink() or output.stat().st_size > 524288:
                    raise ValueError("Invalid mailbox response")
                receipt = json.loads(output.read_bytes())
                if (
                    receipt.get("binding") != self.binding
                    or receipt.get("sequence") != self.sequence
                    or receipt.get("input_digest") != digest(messages)
                ):
                    raise ValueError("Session response binding mismatch")
                if receipt.get("status") not in {"tool_requested", "final"}:
                    self.host._validate_diagnostic(receipt.get("diagnostic"))
                    self.last_diagnostic = receipt["diagnostic"]
                    self.authority.emit("model_unknown", receipt)
                    raise ValueError("Unknown model turn; no replay")
                action = receipt["action"]
                if (
                    receipt.get("output_digest") != digest(action)
                    or receipt.get("original_request_digest") != digest(self.request)
                    or receipt.get("config_digest") != self.config
                ):
                    raise ValueError("Invalid session receipt")
                if receipt.get("wire_input", {}).get("bytes") != receipt.get("inputTextBytes"):
                    raise ValueError("Actual model input bytes not bound")
                metadata = dict(
                    request_id=self.request["request_id"],
                    input_digest=digest(self.request),
                    config_digest=self.config,
                    requested_model=self.profile["model"],
                    execution_authority=False,
                    status="unknown",
                    proposal=None,
                    output_digest=None,
                    usage=receipt["usage"],
                    elapsed_ms=0,
                    timing=receipt["timing"],
                )
                self.host._validate(metadata, self.request, self.config)
                if action.get("action") == "final":
                    candidate = dict(
                        request_id=self.request["request_id"],
                        input_digest=digest(self.request),
                        config_digest=self.config,
                        requested_model=self.profile["model"],
                        execution_authority=False,
                        status="proposed",
                        proposal=action["value"],
                        output_digest=digest(action["value"]),
                        usage=receipt["usage"],
                        elapsed_ms=0,
                    )
                    self.host._validate(candidate, self.request, self.config)
                elif (
                    set(action) != {"action", "name", "arguments"}
                    or action["action"] != "tool"
                    or action["name"] != "native_context"
                    or not isinstance(action["arguments"], dict)
                ):
                    raise ValueError("Invalid host tool action")
                self.authority.emit("model_receipt", receipt)
                self._check()
                if receipt["status"] == "final":
                    while self.command.poll() is None:
                        self._check(authority=False, installation=False)
                        time.sleep(0.01)
                    code = self.command.poll()
                    self.command.close()
                    if code != 0 or self.command.overflow.is_set() or self.command.read_error.is_set():
                        raise ValueError("Session final drain failed")
                    receipt["process_tree_closed"] = True
                    receipt["process_exit_code"] = code
                return receipt
            if self.command.poll() is not None:
                raise ValueError("Session exited without response")
            time.sleep(0.01)

    def close(self):
        try:
            if self.command:
                self.command.close()
                self.authority.emit("process_closed", {"physical": True, "exit_code": self.command.process.returncode})
        finally:
            for stream in self.streams:
                stream.close()
            self.temp.cleanup()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


class NativeModelHost:
    def __init__(self, installed, verify_installation, process_helper_path):
        self.installed = json.loads(json.dumps(installed, ensure_ascii=False, sort_keys=True, allow_nan=False))
        self.verify = verify_installation
        required = {"node", "entry", "python", "model", "reasoning_effort", "env", "timeout"}
        if set(self.installed) != required or not callable(self.verify):
            raise ValueError("Invalid trusted model installation")
        for name in ("node", "entry", "python"):
            path = Path(self.installed[name])
            if not path.is_absolute() or not path.is_file() or path.suffix.lower() in {".cmd", ".bat"}:
                raise ValueError("Absolute installed executable required")
        if not isinstance(self.installed["env"], dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in self.installed["env"].items()
        ):
            raise ValueError("Fixed environment required")
        secret = os.environ.get("GONGGONG_HOST_KEY")
        if any(k.upper() == "GONGGONG_HOST_KEY" or (secret and secret in v) for k, v in self.installed["env"].items()):
            raise ValueError("Authority key forbidden in model environment")
        timeout = self.installed["timeout"]
        if type(timeout) not in {float, int} or not math.isfinite(timeout) or not 0 < timeout <= 600:
            raise ValueError("Invalid timeout")
        helper = Path(process_helper_path)
        if not helper.is_absolute() or not helper.is_file():
            raise ValueError("Installed process helper required")
        spec = importlib.util.spec_from_file_location("native_model_owned_process", helper)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.wrapper = Path(__file__).with_name("native_model_proposal.cjs")

    def context_session(self, request, authority, max_calls):
        return NativeContextSession(self, request, authority, max_calls)

    def configuration(self):
        profile = json.loads(encoded(self.installed))
        if self.verify(profile) is not True:
            raise ValueError("Model installation rejected")
        # Include channel and local dependencies in the host-private installation identity.
        root = self.wrapper.parents[4]
        sources = [
            Path(__file__),
            self.wrapper,
            root / "tools/codex_cli/subscription_session.js",
            root / "tools/codex_cli/content_preview.js",
            root / "tools/codex_cli/subscription_profile.py",
        ]
        binding = digest({
            "profile": profile,
            "sources": [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources],
            "executables": [executable_sha256(profile[k]) for k in ("node", "entry", "python")],
            "helper": self.helper.implementation_fingerprint(),
        })
        return profile, binding

    def run(self, request, cancel=None):
        # Construct the exact ordered immutable input hashed by the JS contract.
        keys = ("request_id", "task", "context", "write_allowlist", "acceptance")
        if not isinstance(request, dict) or set(request) != set(keys):
            raise ValueError("Invalid proposal request")
        request = json.loads(encoded({k: request[k] for k in keys}))
        if len(encoded(request)) > 131072:
            raise ValueError("Proposal request too large")
        for field, limit in (("request_id", 128), ("task", 32768), ("context", 65536), ("acceptance", 16384)):
            if not isinstance(request[field], str) or not 0 < len(request[field].encode("utf-8")) <= limit:
                raise ValueError("Proposal request field too large or invalid: " + field)
        paths = request["write_allowlist"]
        if (
            not isinstance(paths, list)
            or len(paths) > 64
            or any(
                not isinstance(p, str)
                or not 0 < len(p.encode("utf-8")) <= 512
                or not re.fullmatch(r"[a-zA-Z0-9_./-]+", p)
                or p.startswith("/")
                or any(part in {"", ".", ".."} for part in p.split("/"))
                for p in paths
            )
            or len(set(paths)) != len(paths)
        ):
            raise ValueError("Invalid proposal write allowlist")
        profile, binding = self.configuration()
        started = time.monotonic()
        terminal = {
            "request_id": request["request_id"],
            "input_digest": digest(request),
            "config_digest": binding,
            "requested_model": profile["model"],
            "status": "unknown",
            "proposal": None,
            "output_digest": None,
            "usage": {"raw": None, "status": "unknown"},
            "execution_authority": False,
        }
        reasons = []
        owned_closed_ms = None
        validated_ms = None
        protocol_elapsed_ms = None
        private = {"request": request, "installed": {k: v for k, v in profile.items() if k not in {"node", "timeout"}}}
        private["installed"]["config_digest"] = binding
        with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            source.write(encoded(private))
            source.seek(0)
            code = self.helper.run_owned(
                [profile["node"], str(self.wrapper)],
                stdin=source,
                stdout=out,
                stderr=err,
                env=profile["env"],
                limit=524288,
                timeout=profile["timeout"],
                active=lambda: cancel is None or not cancel.is_set(),
                fail=reasons.append,
                cwd=self.wrapper.parent,
            )
            # run_owned has closed and verified the owned tree before any successful return.
            owned_closed_ms = round((time.monotonic() - started) * 1000)
            terminal["process_tree_closed"] = True
            terminal["process_exit_code"] = code
            terminal["process_reasons"] = reasons
            if code == 0 and not reasons and (cancel is None or not cancel.is_set()):
                out.seek(0)
                try:
                    candidate = json.loads(out.read())
                    self._validate(candidate, request, binding)
                    if candidate["requested_model"] != profile["model"]:
                        raise ValueError("Requested model binding changed")
                    if self.configuration()[1] != binding:
                        raise ValueError("Installation changed")
                    terminal.update(candidate)
                    protocol_elapsed_ms = candidate["elapsed_ms"]
                    validated_ms = round((time.monotonic() - started) * 1000)
                except (ValueError, KeyError, TypeError):
                    terminal["process_reasons"].append("response_contract")
        terminal["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        # This clock starts after installation validation, separately from the JS clock.
        # Only the owned-process helper can establish physical closure.
        terminal["host_timing"] = {
            "clock": "monotonic",
            "origin": "after_installation_validation",
            "owned_process_closed_ms": owned_closed_ms,
            "receipt_validated_ms": validated_ms,
            "protocol_elapsed_ms": protocol_elapsed_ms,
            "total_ms": terminal["elapsed_ms"],
        }
        terminal["remote_cancellation"] = "unknown"
        return terminal

    @staticmethod
    def _validate_diagnostic(value):
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "phase", "terminal", "reason"}
            or type(value["version"]) is not int
            or value["version"] != 1
            or value["phase"] not in {"schema_preflight", "transport", "proposal_validation"}
            or value["terminal"] not in {"unknown", "completed", "failed", "interrupted"}
            or value["reason"]
            not in {"schema_preflight", "terminal_failure", "proposal_rejection", "missing_output", "unknown"}
        ):
            raise ValueError("Invalid bounded diagnostic")

    @staticmethod
    def _validate(candidate, request, binding):
        keys = {
            "request_id",
            "input_digest",
            "config_digest",
            "requested_model",
            "execution_authority",
            "status",
            "proposal",
            "output_digest",
            "usage",
            "elapsed_ms",
        }
        if (
            not isinstance(candidate, dict)
            or not keys <= set(candidate) <= keys | {"timing", "diagnostic"}
            or candidate["request_id"] != request["request_id"]
            or candidate["input_digest"] != digest(request)
            or candidate["config_digest"] != binding
            or candidate["execution_authority"] is not False
        ):
            raise ValueError("Invalid private response")
        if (
            not isinstance(candidate["requested_model"], str)
            or not 0 < len(candidate["requested_model"].encode()) <= 128
            or type(candidate["elapsed_ms"]) is not int
            or not 0 <= candidate["elapsed_ms"] <= 86400000
        ):
            raise ValueError("Invalid response metadata")
        if "diagnostic" in candidate:
            NativeModelHost._validate_diagnostic(candidate["diagnostic"])
        if "timing" in candidate:
            NativeModelHost._validate_timing(candidate["timing"])
        p = candidate["proposal"]
        usage = candidate["usage"]
        if (
            not isinstance(usage, dict)
            or not set(usage)
            <= {"thread_id", "turn_id", "observed_model", "raw", "status", "updates", "source", "normalized_usage"}
            or usage.get("normalized_usage") is not None
            or usage.get("status") not in {"observed", "unknown", "invalid"}
        ):
            raise ValueError("Invalid usage envelope")
        if "updates" in usage and (type(usage["updates"]) is not int or not 0 <= usage["updates"] <= 32):
            raise ValueError("Invalid usage update count")
        if "source" in usage and usage["source"] != "thread/tokenUsage/updated":
            raise ValueError("Invalid usage source")
        for key in ("thread_id", "turn_id", "observed_model"):
            if usage.get(key) is not None and (
                not isinstance(usage[key], str) or not 0 < len(usage[key].encode()) <= 256
            ):
                raise ValueError("Invalid usage identity")
        raw = usage.get("raw")
        if raw is None and usage["status"] == "observed":
            raise ValueError("Missing observed usage")
        if raw is not None:
            fields = {"cachedInputTokens", "inputTokens", "outputTokens", "reasoningOutputTokens", "totalTokens"}
            if (
                usage["status"] != "observed"
                or not usage.get("thread_id")
                or not usage.get("turn_id")
                or not isinstance(raw, dict)
                or not {"last", "total"} <= set(raw) <= {"last", "total", "modelContextWindow"}
            ):
                raise ValueError("Invalid raw usage")
            for key in ("last", "total"):
                if (
                    not isinstance(raw[key], dict)
                    or not fields <= set(raw[key]) <= fields | {"cacheWriteInputTokens"}
                    or any(type(n) is not int or not 0 <= n <= 2**53 - 1 for n in raw[key].values())
                ):
                    raise ValueError("Invalid raw usage counters")
            window = raw.get("modelContextWindow")
            if window is not None and (type(window) is not int or not 0 <= window <= 2**53 - 1):
                raise ValueError("Invalid context window")
        if candidate["status"] == "unknown":
            if p is not None or candidate["output_digest"] is not None:
                raise ValueError("Unknown response has results")
            return
        if (
            candidate["status"] != "proposed"
            or not isinstance(p, dict)
            or set(p) != {"request_id", "input_digest", "summary", "files"}
            or p["request_id"] != request["request_id"]
            or p["input_digest"] != digest(request)
            or candidate["output_digest"] != digest(p)
        ):
            raise ValueError("Proposal binding rejected")
        if (
            not isinstance(p["summary"], str)
            or not 0 < len(p["summary"].encode()) <= 4096
            or not isinstance(p["files"], list)
            or len(p["files"]) > 64
            or len(encoded(p)) > 262144
        ):
            raise ValueError("Proposal bounds rejected")
        seen = set()
        for f in p["files"]:
            if (
                not isinstance(f, dict)
                or set(f) != {"path", "content"}
                or not isinstance(f["path"], str)
                or f["path"] not in request["write_allowlist"]
                or f["path"] in seen
                or not isinstance(f["content"], str)
                or len(f["content"].encode()) > 131072
            ):
                raise ValueError("Proposal file rejected")
            seen.add(f["path"])

    @staticmethod
    def _validate_timing(timing):
        names = {
            "session_ready",
            "thread_start_sent",
            "thread_start_received",
            "turn_start_sent",
            "turn_start_received",
            "first_response",
            "first_text",
            "last_text",
            "turn_completed",
            "proposal_validated",
            "receipt_ready",
        }
        if (
            not isinstance(timing, dict)
            or set(timing) != {"version", "clock", "marks", "rpc"}
            or type(timing["version"]) is not int
            or timing["version"] != 1
            or timing["clock"] != "monotonic"
            or not isinstance(timing["marks"], dict)
            or set(timing["marks"]) != names
            or not isinstance(timing["rpc"], dict)
            or set(timing["rpc"]) != {"thread_start_calls", "turn_start_calls"}
        ):
            raise ValueError("Invalid timing envelope")
        marks = timing["marks"]
        if any(
            value is not None and (type(value) is not int or not 0 <= value <= 86400000) for value in marks.values()
        ):
            raise ValueError("Invalid timing mark")
        if any(type(value) is not int or not 0 <= value <= 1 for value in timing["rpc"].values()):
            raise ValueError("Invalid timing call count")
        ready = marks["receipt_ready"]
        if ready is None or any(value is not None and value > ready for value in marks.values()):
            raise ValueError("Timing extends beyond receipt")
        for phase in ("thread", "turn"):
            sent = marks[phase + "_start_sent"]
            received = marks[phase + "_start_received"]
            count = timing["rpc"][phase + "_start_calls"]
            if (sent is not None) != (count == 1) or (received is not None and sent is None):
                raise ValueError("Timing request binding missing")
        # Notifications may arrive before the turn/start reply. Compare them to
        # the request, never require receipt order to match event order.
        edges = (
            ("session_ready", "thread_start_sent"),
            ("thread_start_sent", "thread_start_received"),
            ("thread_start_received", "turn_start_sent"),
            ("turn_start_sent", "turn_start_received"),
            ("turn_start_sent", "first_response"),
            ("turn_start_sent", "first_text"),
            ("turn_start_sent", "turn_completed"),
            ("first_response", "first_text"),
            ("first_response", "turn_completed"),
            ("first_text", "last_text"),
            ("last_text", "turn_completed"),
            ("turn_completed", "proposal_validated"),
        )
        for before, after in edges:
            if marks[before] is not None and marks[after] is not None and marks[before] > marks[after]:
                raise ValueError("Timing marks out of order")
        if any(marks[name] is not None for name in ("first_response", "first_text", "last_text", "turn_completed")):
            if marks["turn_start_sent"] is None:
                raise ValueError("Timing event has no request")
        if (marks["first_text"] is None) != (marks["last_text"] is None):
            raise ValueError("Incomplete text timing bounds")
