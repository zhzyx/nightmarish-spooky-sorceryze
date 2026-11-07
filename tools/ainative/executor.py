"""SQLite DAG host. Providers are injected objects and never serialized.

Call step in a worker process: provider methods can block. status/cancel do not
call providers. Unknown submission outcomes require lookup, never blind replay.
"""

import base64
import copy
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .contracts import validate
    from .extensions import (
        NodeRegistry,
        canonical,
        provider_manifest,
        require,
        validate_invocation,
        validate_job,
        validate_outputs,
    )
else:
    from contracts import validate
    from extensions import (
        NodeRegistry,
        canonical,
        provider_manifest,
        require,
        validate_invocation,
        validate_job,
        validate_outputs,
    )


def snapshot_file(path):
    """Read once; persist content, not a mutable filename (path relative to caller cwd)."""
    data = Path(path).read_bytes()
    return {
        "content_sha256": hashlib.sha256(data).hexdigest(),
        "content_base64": base64.b64encode(data).decode("ascii"),
    }


def check_content(value):
    if isinstance(value, dict):
        require(
            not set(value) & {"uri", "url", "path", "source_path"}, "external references require snapshot_file content"
        )
        if "content_base64" in value or "content_sha256" in value:
            data = base64.b64decode(value["content_base64"], validate=True)
            require(hashlib.sha256(data).hexdigest() == value["content_sha256"], "content digest mismatch")
        for child in value.values():
            check_content(child)
    elif isinstance(value, list):
        for child in value:
            check_content(child)


def merge_manifest(left, right):
    require(not validate(left) and not validate(right), "invalid manifest")
    result = copy.deepcopy(left)
    index = {a["id"]: a for a in result["artifacts"]}
    for asset in right["artifacts"]:
        if asset["id"] in index:
            require(canonical(index[asset["id"]]) == canonical(asset), "conflicting artifact identity")
        else:
            result["artifacts"].append(copy.deepcopy(asset))
            index[asset["id"]] = asset
    require(not validate(result), "invalid merged manifest")
    return result


class Executor:
    def __init__(self, database, registry, providers):
        self.registry, self.providers = registry, providers
        self.db = sqlite3.connect(str(Path(database).resolve()), timeout=10, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets(id TEXT, revision TEXT, body TEXT NOT NULL,
              PRIMARY KEY(id,revision));
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, body TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _read(self, run_id):
        row = self.db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        require(row is not None, "unknown run")
        return json.loads(row[0])

    def _write(self, run):
        self.db.execute("UPDATE runs SET body=? WHERE id=?", (canonical(run), run["id"]))

    def _assets(self, manifest):
        require(not validate(manifest), "invalid manifest")
        check_content(manifest)
        for asset in manifest["artifacts"]:
            body = canonical(asset)
            row = self.db.execute(
                "SELECT body FROM assets WHERE id=? AND revision=?", (asset["id"], asset["revision"])
            ).fetchone()
            require(row is None or row[0] == body, "immutable artifact revision changed")
            self.db.execute("INSERT OR IGNORE INTO assets VALUES(?,?,?)", (asset["id"], asset["revision"], body))

    def create(self, graph, manifest, run_id=None):
        """graph: [{id, provider, request, links:{input:{node,port}}}]."""
        graph = json.loads(canonical(graph))
        require(isinstance(graph, list) and bool(graph), "nonempty graph required")
        require(
            all(
                isinstance(n, dict)
                and set(n) == {"id", "provider", "request", "links"}
                and isinstance(n["id"], str)
                and n["id"]
                for n in graph
            ),
            "invalid graph node",
        )
        nodes = {n["id"]: n for n in graph}
        require(len(nodes) == len(graph), "duplicate node")
        definitions = {n["id"]: self.registry.get(n["request"]["node"], n["request"]["version"]) for n in graph}
        pending, visited = set(nodes), set()
        for node in graph:
            require(node["provider"] in self.providers, "unknown provider")
            require(isinstance(node["links"], dict), "invalid links")
            definition = definitions[node["id"]]
            require(not set(node["links"]) & set(node["request"]["inputs"]), "duplicate input binding")
            for port, link in node["links"].items():
                require(
                    isinstance(link, dict) and set(link) == {"node", "port"} and link["node"] in nodes,
                    "missing dependency",
                )
                require(port in definition["inputs"], "unknown linked input")
                source = definitions[link["node"]]["outputs"]
                require(link["port"] in source, "unknown source port")
                require(source[link["port"]]["required"], "linked source output must be required")
                require(
                    set(source[link["port"]]["types"]) <= set(definition["inputs"][port]["types"]),
                    "incompatible linked types",
                )
            node.update(state="pending", attempt=0, job=None, result=None, error=None)
            node["provider_manifest"] = provider_manifest(self.providers[node["provider"]].describe())
            node["definition"] = definition
        while pending:
            ready = {n for n in pending if {link["node"] for link in nodes[n]["links"].values()} <= visited}
            require(bool(ready), "DAG cycle")
            pending -= ready
            visited |= ready
        run = {
            "id": run_id or uuid.uuid4().hex,
            "cancelled": False,
            "manifest": json.loads(canonical(manifest)),
            "nodes": nodes,
        }
        # Validate static portions now; linked inputs are validated again when resolved.
        for node in graph:
            partial = copy.deepcopy(node["definition"])
            for port in node["links"]:
                partial["inputs"][port]["required"] = False
            partial_registry = NodeRegistry()
            partial_registry.register(partial)
            validate_invocation(partial_registry, node["request"], manifest, node["provider_manifest"])
        with self.transaction():
            self._assets(manifest)
            self.db.execute("INSERT INTO runs VALUES(?,?)", (run["id"], canonical(run)))
        return run["id"]

    def status(self, run_id):
        run = self._read(run_id)
        states = [n["state"] for n in run["nodes"].values()]
        run["state"] = (
            "cancelled"
            if run["cancelled"] or "cancelled" in states
            else "succeeded"
            if all(s == "succeeded" for s in states)
            else "failed"
            if "failed" in states
            else "reconcile"
            if "reconcile" in states
            else "running"
        )
        return run

    def cancel(self, run_id):
        """Local durable cancellation is immediate; remote cancellation is best effort in step."""
        with self.transaction():
            run = self._read(run_id)
            run["cancelled"] = True
            for node in run["nodes"].values():
                node["state"] = "cancelled"
                node["result"] = None
            self._write(run)
        return self.status(run_id)

    def retry(self, run_id, node_id):
        with self.transaction():
            run = self._read(run_id)
            node = run["nodes"][node_id]
            require(
                not run["cancelled"] and node["state"] == "failed" and node["job"] and node["job"]["state"] == "failed",
                "only confirmed provider failure can retry",
            )
            node.update(state="pending", attempt=node["attempt"] + 1, job=None, error=None, result=None)
            self._write(run)

    def export(self, run_id):
        run = self.status(run_id)
        require(run["state"] == "succeeded", "run is not publishable")
        return {"manifest": run["manifest"], "outputs": {k: n["job"]["outputs"] for k, n in run["nodes"].items()}}

    def export_node(self, run_id, node_id):
        """Read a successful node for preview without relaxing run publication."""
        run = self.status(run_id)
        require(not run["cancelled"], "run is cancelled")
        require(node_id in run["nodes"], "unknown node")
        node = run["nodes"][node_id]
        require(node["state"] == "succeeded" and node["job"] is not None, "node has no successful result")
        registry = NodeRegistry()
        registry.register(node["definition"])
        validate_outputs(
            registry, node["request"]["node"], node["request"]["version"], node["job"]["outputs"], run["manifest"]
        )
        check_content(run["manifest"])
        return {"manifest": run["manifest"], "outputs": {node_id: node["job"]["outputs"]}}

    def step(self, run_id):
        """Perform at most one external operation; transactions never cover provider I/O."""
        with self.transaction():
            run = self._read(run_id)
            selected = None
            for node_id, node in run["nodes"].items():
                if run["cancelled"]:
                    if node["job"] and not node.get("cancel_sent"):
                        selected = (node_id, node, "cancel")
                        node["cancel_sent"] = True
                        break
                    continue
                if node["state"] in ("succeeded", "failed", "cancelled"):
                    continue
                if node["state"] == "pending":
                    deps = [run["nodes"][link["node"]] for link in node["links"].values()]
                    if not all(d["state"] == "succeeded" for d in deps):
                        continue
                    request = copy.deepcopy(node["request"])
                    for port, link in node["links"].items():
                        request["inputs"][port] = run["nodes"][link["node"]]["job"]["outputs"][link["port"]]
                    require(
                        canonical(self.registry.get(request["node"], request["version"]))
                        == canonical(node["definition"]),
                        "registered definition changed since create",
                    )
                    key = validate_invocation(self.registry, request, run["manifest"], node["provider_manifest"])
                    node.update(
                        resolved=request,
                        input_manifest=copy.deepcopy(run["manifest"]),
                        key=key,
                        idempotency_key=hashlib.sha256(
                            canonical([run_id, node_id, node["attempt"], key]).encode()
                        ).hexdigest(),
                    )
                    cached = self.db.execute("SELECT body FROM cache WHERE key=?", (key,)).fetchone()
                    if cached:
                        result = json.loads(cached[0])
                        validate_outputs(
                            self.registry,
                            request["node"],
                            request["version"],
                            result["job"]["outputs"],
                            result["manifest"],
                        )
                        run["manifest"] = merge_manifest(run["manifest"], result["manifest"])
                        node.update(state="succeeded", job=result["job"], result=result["manifest"])
                        self._write(run)
                        return self.status(run_id)
                    # Durable intent. A crash anywhere after this point must reconcile.
                    node["state"] = "reconcile"
                    selected = (node_id, node, "submit")
                else:
                    selected = (node_id, node, "lookup" if node["state"] == "reconcile" else "poll")
                break
            self._write(run)
        if selected is None:
            return self.status(run_id)
        node_id, node, action = selected
        provider = self.providers[node["provider"]]
        snapshot, result, error = None, None, None
        raw = None
        try:
            if action != "cancel":
                require(
                    canonical(self.registry.get(node["request"]["node"], node["request"]["version"]))
                    == canonical(node["definition"]),
                    "registered definition changed since create",
                )
            require(
                canonical(provider_manifest(provider.describe())) == canonical(node["provider_manifest"]),
                "provider changed",
            )
            if action == "cancel":
                provider.cancel(node["job"]["job_id"])
            elif action == "lookup":
                raw = provider.lookup(node["idempotency_key"]) if hasattr(provider, "lookup") else None
            elif action == "submit":
                raw = provider.submit(
                    copy.deepcopy(node["resolved"]), copy.deepcopy(node["input_manifest"]), node["idempotency_key"]
                )
            else:
                raw = provider.poll(node["job"]["job_id"])
            if raw is not None:
                validate_job(raw, node["job"])
                snapshot = copy.deepcopy(raw)
                if snapshot["state"] == "failed":
                    snapshot["error"] = "provider_failed"  # Never persist provider error text.
                if snapshot["state"] == "succeeded":
                    result = provider.result_manifest(snapshot["job_id"])
                    validate_outputs(
                        self.registry, node["request"]["node"], node["request"]["version"], snapshot["outputs"], result
                    )
                    check_content(result)
        except Exception:
            error = "provider_operation_failed"  # Safe fixed code; exception messages may contain secrets.
        with self.transaction():
            run = self._read(run_id)
            current = run["nodes"][node_id]
            if run["cancelled"]:
                # Remember a late receipt only for best-effort cancellation, never its outputs.
                if snapshot and not current["job"]:
                    current["job"] = {"job_id": snapshot["job_id"], "state": "queued", "outputs": {}, "error": None}
                self._write(run)
                return self.status(run_id)
            if current["attempt"] != node["attempt"] or current["state"] in ("succeeded", "failed", "cancelled"):
                return self.status(run_id)
            current["error"] = error
            if snapshot is not None:
                # Persist a known job even if fetching/validating its result failed.
                if error:
                    if current["job"] is None:
                        current["job"] = {"job_id": snapshot["job_id"], "state": "queued", "outputs": {}, "error": None}
                    current["state"] = "running"
                else:
                    validate_job(snapshot, current["job"])
                    if result is not None:
                        self.db.execute("SAVEPOINT result_assets")
                        try:
                            merged = merge_manifest(run["manifest"], result)
                            self._assets(result)
                            self.db.execute(
                                "INSERT OR IGNORE INTO cache VALUES(?,?)",
                                (current["key"], canonical({"job": snapshot, "manifest": result})),
                            )
                        except (ValueError, KeyError, TypeError):
                            self.db.execute("ROLLBACK TO result_assets")
                            current.update(state="running", error="invalid_result", result=None)
                            if current["job"] is None:
                                current["job"] = {
                                    "job_id": snapshot["job_id"],
                                    "state": "queued",
                                    "outputs": {},
                                    "error": None,
                                }
                            self._write(run)
                            return self.status(run_id)
                        finally:
                            self.db.execute("RELEASE result_assets")
                        run["manifest"] = merged
                    current.update(job=snapshot, state=snapshot["state"], result=result)
            self._write(run)
        return self.status(run_id)
