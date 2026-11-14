"""Persistent synthetic Executor provider for M3 tests; no model or network."""

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path


class SyntheticProvider:
    def __init__(self):
        self.root = Path(os.environ["ENGINE_NEXT_M3_TEST_STATE"])
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return self.root / name

    def _read(self, name, default=None):
        path = self._path(name)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def _write(self, name, value):
        path = self._path(name)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def describe(self):
        return {
            "id": "synthetic-m3",
            "version": "1",
            "model": "no-generation-fixture",
            "model_version": "1",
            "available": True,
            "capabilities": ["echo"],
            "context_types": ["text", "image"],
        }

    def submit(self, request, manifest, idempotency_key):
        count = self._read("submit-count.json", 0) + 1
        self._write("submit-count.json", count)
        source = request["inputs"]["source"]
        artifact = next(
            item
            for item in manifest["artifacts"]
            if item["id"] == source["id"] and item["revision"] == source["revision"]
        )
        artifact = copy.deepcopy(artifact)
        artifact["id"] = "synthetic.output"
        artifact["revision"] = "synthetic-r1"
        artifact.setdefault("payload", {})["extension_future"] = {"opaque": [7, "preserve-me"]}
        job = {"job_id": idempotency_key, "state": "queued", "outputs": {}, "error": None}
        self._write("job-" + idempotency_key + ".json", job)
        self._write("artifact-" + idempotency_key + ".json", artifact)
        if self._path("tree").exists():
            subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            time.sleep(30)
        if self._path("flood").exists():
            while True:
                sys.stdout.buffer.write(b"x" * 8192)
                sys.stdout.buffer.flush()
        if self._path("detached").exists():
            child = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._write("detached-pid.json", child.pid)
        if self._path("lost.once").exists():
            self._path("lost.once").unlink()
            raise RuntimeError("synthetic lost receipt")
        return job

    def poll(self, job_id):
        job = self._read("job-" + job_id + ".json")
        if job is None:
            return None
        if job["state"] != "queued":
            return job
        job["state"] = "succeeded"
        job["outputs"] = {"result": {"id": "synthetic.output", "revision": "synthetic-r1"}}
        self._write("job-" + job_id + ".json", job)
        return copy.deepcopy(job)

    def lookup(self, key):
        return self._read("job-" + key + ".json")

    def result_manifest(self, job_id):
        return {"schema_version": 1, "artifacts": [self._read("artifact-" + job_id + ".json")]}

    def cancel(self, job_id):
        job = self._read("job-" + job_id + ".json")
        if job is not None and job["state"] not in {"succeeded", "failed", "cancelled"}:
            job["state"] = "cancelled"
            self._write("job-" + job_id + ".json", job)


def factory():
    from extensions import NodeRegistry

    registry = NodeRegistry()
    registry.register({
        "id": "echo",
        "version": "1",
        "inputs": {"source": {"types": ["image", "mesh"], "required": True}},
        "outputs": {"result": {"types": ["image", "mesh"], "required": True}},
        "context_types": ["text", "image"],
        "parameters": {},
        "capabilities": ["echo"],
    })
    return registry, {"synthetic": SyntheticProvider()}
