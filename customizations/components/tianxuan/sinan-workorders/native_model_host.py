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
            "executables": [
                hashlib.sha256(Path(profile[k]).read_bytes()).hexdigest() for k in ("node", "entry", "python")
            ],
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
                except (ValueError, KeyError, TypeError):
                    terminal["process_reasons"].append("response_contract")
        terminal["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        terminal["remote_cancellation"] = "unknown"
        return terminal

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
            or set(candidate) != keys
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
