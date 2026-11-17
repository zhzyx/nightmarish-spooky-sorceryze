"""Reproducible CLI process test; not a production throughput benchmark."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def verify() -> dict[str, Any]:
    source = Path(__file__).resolve().parent
    cli = source / "native_cli.py"
    environment = {**os.environ, "PATH": "", "PYTHONPATH": "", "PYTHONIOENCODING": "utf-8"}
    checks = {}
    with tempfile.TemporaryDirectory(prefix="duobao-process-proof-") as directory:
        root = Path(directory)
        database = root / "state.sqlite"

        def call(command, payload=None, expected=0):
            started = time.perf_counter()
            result = subprocess.run(
                [sys.executable, "-B", str(cli), "--db", str(database), "--tenant", "proof", *command],
                input=None if payload is None else json.dumps(payload),
                text=True,
                capture_output=True,
                encoding="utf-8",
                env=environment,
                cwd=root,
                timeout=60,
            )
            if result.returncode != expected:
                raise AssertionError(f"CLI exited {result.returncode}: {result.stdout} {result.stderr}")
            response = json.loads(result.stdout)
            if response["ok"] != (expected == 0):
                raise AssertionError(response)
            return response, time.perf_counter() - started

        def change(module, base, edits, reads=None):
            return {
                "module": module,
                "base": base,
                "reads": [] if reads is None else reads,
                "edits": {name: base64.b64encode(value).decode("ascii") for name, value in edits.items()},
            }

        initial, _ = call(
            ["submit", "--actor", "writer", "--request-key", "initial"],
            [change("content", None, {"original": b"immutable"})],
        )
        base = initial["data"]["revisions"]["content"]

        def independent(index):
            return call(
                ["submit", "--actor", "writer", "--request-key", f"task-{index}"],
                [change("content", base, {f"item-{index}": str(index).encode()})],
            )

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(independent, range(250)))
        elapsed = time.perf_counter() - started
        head, _ = call(["head", "--module", "content"])
        current = head["data"]["revision"]
        state, _ = call(["revision", "--module", "content", "--revision", current])
        expected_objects = {"original": hashlib.sha256(b"immutable").hexdigest()}
        expected_objects.update({f"item-{i}": hashlib.sha256(str(i).encode()).hexdigest() for i in range(250)})
        assert state["data"]["objects"] == expected_objects
        assert len({result[0]["data"]["revisions"]["content"] for result in results}) == 250
        checks["250_old_base_disjoint_writes_preserved_without_producer_retry"] = True
        history, _ = call(["read", "--module", "content", "--revision", base, "--object", "original"])
        assert base64.b64decode(history["data"]["base64"]) == b"immutable"
        checks["history_read_in_new_process"] = True
        replay, _ = independent(0)
        assert replay == results[0][0]
        checks["receipt_replay_in_new_process"] = True
        call(
            ["submit", "--actor", "writer", "--request-key", "winner"],
            [change("content", current, {"original": b"changed"})],
        )
        rejected, _ = call(
            ["submit", "--actor", "writer", "--request-key", "stale-reader"],
            [change("content", current, {"derived": b"invalid"}, ["original"])],
            expected=2,
        )
        assert rejected["error"] == "Conflict"
        checks["changed_read_rejected"] = True
        composition, _ = call(["compose"], {"content": base})
        assert composition["data"]["modules"] == {"content": base}
        checks["immutable_composition"] = True
        checks["working_directory_has_no_git_metadata"] = not (root / ".git").exists()
        durations = sorted(result[1] for result in results)
        timings = {
            "wall_seconds": elapsed,
            "cli_seconds_p50": durations[124],
            "cli_seconds_p95": durations[237],
            "cli_seconds_p99": durations[247],
            "cli_seconds_max": durations[-1],
        }
    assert not root.exists()
    return {
        "schema_version": 1,
        "issue": 1386,
        "request_id": "duobao-native-store-20261117",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "python": sys.version,
        "requests": 250,
        "maximum_concurrent_cli_processes": 16,
        "producer_retries": 0,
        "child_PATH": "",
        "checks": checks,
        "timings": timings,
        "temporary_database_removed": True,
        "source_sha256": {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in ("native_store.py", "native_cli.py", "verify_native_processes.py")
        },
        "limits": [
            "Local CLI process and SQLite semantics only; not server capacity or token savings.",
            "250 requests share an old base; at most 16 child processes execute concurrently.",
            "Empty PATH removes executable discovery; API unit tests separately forbid process/network calls.",
            "Caller read declarations require trusted host completeness enforcement.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify()
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output)
