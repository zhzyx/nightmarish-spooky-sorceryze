"""Task-bound object reads and durable host evidence. Never a merge read-set."""

import base64
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from native_store import NativeContextStorage, _object_name
from native_workspace import absolute


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


class NativeContext:
    def __init__(self, store, authorize, binding, ledger):
        if not callable(authorize) or not Path(ledger).is_absolute():
            raise ValueError("Trusted authority and absolute host ledger required")
        self.store, self.authorize = store, authorize
        self.binding = json.loads(encoded(binding))
        for key in (
            "execution",
            "tenant",
            "actor",
            "producer",
            "source_digest",
            "installation_digest",
            "selected",
            "limits",
        ):
            if key not in binding:
                raise ValueError("Missing context binding: " + key)
        self.identity = digest(self.binding)
        self.path = str(ledger)
        self.limit = binding["limits"]
        if not (
            1024 <= self.limit["response_bytes"] <= 16384
            and 1 <= self.limit["chunk_bytes"] <= 8192
            and 1 <= self.limit["total_bytes"] <= 8388608
            and 1 <= self.limit["max_reads"] <= 1024
        ):
            raise ValueError("Invalid immutable context limits")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS context_binding (id TEXT PRIMARY KEY, payload BLOB)")
            db.execute("CREATE TABLE IF NOT EXISTS context_events (seq INTEGER PRIMARY KEY, kind TEXT, payload BLOB)")
            rows = db.execute("SELECT id FROM context_binding").fetchall()
            if rows and rows != [(self.identity,)]:
                raise ValueError("Ledger belongs to another execution")
            db.execute("INSERT OR IGNORE INTO context_binding VALUES (?,?)", (self.identity, encoded(self.binding)))
        self.owner = Path(self.path).stat()

    @contextmanager
    def db(self):
        path = absolute(Path(self.path), missing=True)
        if hasattr(self, "owner"):
            current = path.stat()
            if (current.st_dev, current.st_ino) != (self.owner.st_dev, self.owner.st_ino):
                raise ValueError("Trusted ledger identity changed")
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def events(self):
        with self.db() as db:
            return [
                {"seq": n, "kind": k, "data": json.loads(p)}
                for n, k, p in db.execute("SELECT seq,kind,payload FROM context_events ORDER BY seq")
            ]

    def ledger_budget(self, max_bytes=8388608):
        # Bound response materialization without loading all historical payloads.
        with self.db() as db:
            count, size = db.execute(
                "SELECT count(*),coalesce(sum(length(payload)+length(CAST(kind AS BLOB))+64),0) FROM context_events"
            ).fetchone()
        if count >= 4096 or size >= max_bytes:
            raise ValueError("Context ledger budget exceeded")

    def emit(self, kind, data):
        with self.db() as db:
            db.execute("INSERT INTO context_events(kind,payload) VALUES (?,?)", (kind, encoded(data)))

    def check(self, operation="model_turn"):
        if digest(self.binding) != self.identity:
            raise ValueError("Original context binding changed")
        for module, revision in self._sources():
            self._authorized(module, revision, operation)
        self.storage()  # Fail source admission before launch/model/tool side effects.

    def _sources(self):
        sources = set(self.binding["selected"].items())
        for pair in self.binding.get("allowed_delta_pairs", []):
            sources.update((pair["module"], pair[k]) for k in ("before", "after"))
        return sorted(sources)

    def storage(self):
        if not hasattr(self, "_storage"):
            self._storage = NativeContextStorage(self.store, self.binding["tenant"], self._sources(), self.identity)
            self._manifest = [
                e for e in self._storage.manifest if self.binding["selected"].get(e["module"]) == e["revision"]
            ]
            self._manifest_digest = digest(self._manifest)
            self._deltas = {}
        self._storage._identity()
        return self._storage

    def _authorized(self, module, revision, operation):
        if self.authorize(json.loads(encoded(self.binding)), module, revision, operation) is not True:
            raise ValueError("Current context authority denied")

    def _revision(self, module, revision):
        allowed = self.binding["selected"].get(module) == revision or any(
            p["module"] == module and revision in (p["before"], p["after"])
            for p in self.binding.get("allowed_delta_pairs", [])
        )
        if not allowed:
            raise ValueError("Revision outside original task")
        self._authorized(module, revision, "read")
        return self.storage().states[module, revision]

    def _cursor(self, query, offset):
        return base64.urlsafe_b64encode(
            encoded({"binding": self.identity, "query": digest(query), "offset": offset})
        ).decode()

    def _offset(self, query, cursor, default=0):
        if cursor is None:
            return default
        if not isinstance(cursor, str) or len(cursor) > 1024:
            raise ValueError("Invalid cursor")
        value = json.loads(base64.urlsafe_b64decode(cursor))
        offset = value.get("offset")
        if type(offset) is not int or offset < 0 or cursor != self._cursor(query, offset):
            raise ValueError("Cursor binding mismatch")
        return offset

    def resolve(self, args, call=None):
        if not isinstance(args, dict):
            raise ValueError("Invalid tool arguments")
        self.check("tool_request")
        history = self.events()
        if any(
            e["kind"] == "started"
            and not any(r["kind"] == "resolved" and r["data"]["request_id"] == e["data"]["request_id"] for r in history)
            for e in history
        ):
            raise ValueError("Unknown prior read requires reconciliation")
        if sum(e["kind"] == "started" for e in history) >= self.limit["max_reads"]:
            raise ValueError("Read budget exhausted")
        self.storage()  # Admit all source budgets before starting any operation.
        request_id = digest([self.identity, len(history), args, call])
        self.emit("started", {"request_id": request_id, "arguments": args, "call": call})
        query = {k: v for k, v in args.items() if k != "cursor"}
        op = args.get("op")
        content, source, span, kind = None, None, None, None
        next_cursor = None
        if op == "manifest":
            if set(args) != {"op", "cursor"}:
                raise ValueError("Invalid manifest arguments")
            entries = self._manifest
            kind = "namespace"
            source = {"selected": self.binding["selected"], "map_digest": self._manifest_digest}
        elif op == "delta":
            if set(args) != {"op", "module", "before", "after", "cursor"} or {
                k: args[k] for k in ("module", "before", "after")
            } not in self.binding.get("allowed_delta_pairs", []):
                raise ValueError("Delta pair not authorized")
            before = self._revision(args["module"], args["before"])
            after = self._revision(args["module"], args["after"])
            pair_key = (args["module"], args["before"], args["after"])
            if pair_key not in self._deltas:
                self._deltas.clear()  # One bounded delta index, never one per arbitrary pair.
                self._deltas[pair_key] = [
                    {"name": n, "before": before["objects"].get(n), "after": after["objects"].get(n)}
                    for n in sorted(set(before["objects"]) | set(after["objects"]))
                    if before["objects"].get(n) != after["objects"].get(n)
                ]
            entries = self._deltas[pair_key]
            kind, source = (
                "revision_metadata",
                {"module": args["module"], "before": args["before"], "after": args["after"]},
            )
        elif op == "read":
            if set(args) != {
                "op",
                "module",
                "revision",
                "name",
                "object_digest",
                "offset",
                "length",
                "cursor",
                "known_receipt",
            }:
                raise ValueError("Invalid read arguments")
            _object_name(args["name"])
            state = self._revision(args["module"], args["revision"])
            source = {k: args[k] for k in ("module", "revision", "name", "object_digest")}
            source["tenant"] = self.binding["tenant"]
            if (
                type(args["offset"]) is not int
                or args["offset"] < 0
                or type(args["length"]) is not int
                or not 1 <= args["length"] <= self.limit["chunk_bytes"]
            ):
                raise ValueError("Invalid exact byte range")
            if args["known_receipt"] is not None:
                raise ValueError("Receipt deduplication requires retained session evidence; resend explicitly")
            actual = state["objects"].get(args["name"])
            if actual is None:
                source["object_digest"] = None
                kind, content = "absence", {"exists": False, "revision_map_digest": digest(state)}
            else:
                if actual != args["object_digest"]:
                    raise ValueError("Object source mismatch")
                offset = self._offset(query, args["cursor"], args["offset"])
                chunk, total = self.storage().read_range(
                    args["module"], args["revision"], args["name"], offset, args["length"]
                )
                span = dict(offset=offset, returned_bytes=len(chunk), total_bytes=total)
                content, kind = base64.b64encode(chunk).decode(), "object"
                if offset + len(chunk) < total:
                    next_cursor = self._cursor(query, offset + len(chunk))
        else:
            raise ValueError("Unknown context operation")
        if op in {"manifest", "delta"}:
            offset = self._offset(query, args["cursor"])
            if offset > len(entries):
                raise ValueError("Cursor outside manifest")
            content = []
            while offset < len(entries) and len(content) < 100:
                if len(encoded(content + [entries[offset]])) > self.limit["response_bytes"] - 1024:
                    break
                content.append(entries[offset])
                offset += 1
            if offset < len(entries):
                if not content:
                    raise ValueError("Manifest item exceeds response budget")
                next_cursor = self._cursor(query, offset)
        result = dict(
            schema=2,
            execution=self.binding["execution"],
            binding_digest=self.identity,
            request_id=request_id,
            request_digest=digest(args),
            result_id=request_id,
            status="resolved",
            dependency_kind=kind,
            source=source,
            range=span,
            content=content,
            encoding="base64" if kind == "object" else "json",
            complete=next_cursor is None,
            next_cursor=next_cursor,
            content_omitted=kind in {"namespace", "revision_metadata"},
            object_complete=kind == "object" and span["offset"] == 0 and next_cursor is None,
        )
        result["response_sha256"] = digest(result)
        size = len(encoded(result))
        if (
            size > self.limit["response_bytes"]
            or size + sum(len(encoded(e["data"])) for e in history if e["kind"] == "resolved")
            > self.limit["total_bytes"]
        ):
            raise ValueError("Context response budget exceeded")
        self.check("tool_response")
        self.emit("resolved", result)
        return result

    def delivery(self, call, messages, status):
        if status not in {"included_in_call", "transport_received", "unknown"}:
            raise ValueError("Invalid delivery state")
        self.check("model_turn")
        resolved = {e["data"]["result_id"]: e["data"] for e in self.events() if e["kind"] == "resolved"}
        results = []
        for message in messages:
            if message.get("role") != "user":
                continue
            try:
                payload = json.loads(message["content"])
            except (ValueError, TypeError):
                continue
            result = payload.get("tool_result") if isinstance(payload, dict) else None
            if isinstance(result, dict) and result.get("schema") == 2:
                if resolved.get(result.get("result_id")) != result:
                    raise ValueError("Tool response is not a durable resolved fact")
                results.append(result["result_id"])
        self.emit(
            status,
            {
                "call": call,
                "input_digest": digest(messages),
                "input_bytes": len(encoded(messages)),
                "result_ids": results,
            },
        )

    def receipt(self):
        events = self.events()
        models = [e["data"] for e in events if e["kind"] == "model_receipt"]
        started = {e["data"]["request_id"] for e in events if e["kind"] == "started"}
        resolved = {e["data"]["request_id"] for e in events if e["kind"] == "resolved"}
        included = {e["data"]["call"] for e in events if e["kind"] == "included_in_call"}
        received = {e["data"]["call"] for e in events if e["kind"] == "transport_received"}
        final = bool(
            events
            and events[-1]["kind"] == "process_closed"
            and events[-1]["data"]["exit_code"] == 0
            and models
            and models[-1]["status"] == "final"
            and started == resolved
            and included == received
            and not any(e["kind"] in {"unknown", "model_unknown"} for e in events)
        )
        return {
            "schema": 2,
            "execution": self.binding["execution"],
            "source_digest": self.binding["source_digest"],
            "tenant": self.binding["tenant"],
            "binding_digest": self.identity,
            "events": events,
            "ledger_digest": digest(events),
            "terminal": "final" if final else "incomplete",
            "reads": None,
        }
