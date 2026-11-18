"""Exact-candidate independent review with durable, non-replayed external intent.

The installed reviewer is an admitted role runtime. The host checks coverage and
identity, while that runtime inspects content and makes the semantic decision.
"""

import base64
import json

from native_installation import InstalledPlannerRuntime, require
from native_store import _digest, _json


class IndependentReview:
    def __init__(self, domain, native, installation, authorize):
        self.domain, self.native = domain, native
        self.installation, self.authorize = installation, authorize
        with domain._connection_lock, domain.db:
            domain.db.execute(
                "CREATE TABLE IF NOT EXISTS native_entry_reviews ("
                "id TEXT PRIMARY KEY, request TEXT NOT NULL, receipt TEXT)"
            )

    def __call__(self, actor, task, terminal):
        return self.evaluate(actor, task, terminal, allow_start=True)

    def reconcile(self, actor, task, terminal):
        return self.evaluate(actor, task, terminal, allow_start=False)

    def evaluate(self, actor, task, terminal, *, allow_start):
        originals = [original["contract"] for original in task["originals"]] if "originals" in task else [task]

        def authority(_=None):
            for original in originals:
                self.authorize(original["actor"], original["issue"], "review")
            return True

        authority()
        if "originals" in task:
            plan = task
            task = dict(plan["originals"][0]["contract"])
            task["integration_plan"] = plan
            task["source"] = json.loads(_json(task["source"]))
            task["source"]["definition"]["acceptance"] = "\n".join(
                original["contract"]["source"]["definition"]["acceptance"] for original in plan["originals"]
            )
        self.authorize(actor, task["issue"], "review")
        spec = self.installation.verify()
        candidate, tenant = terminal["candidate"], task["tenant"]
        with self.native._connection() as db:
            row = db.execute(
                "SELECT payload FROM native_compositions WHERE tenant=? AND id=?", (tenant, candidate)
            ).fetchone()
        require(row is not None and _digest(row[0].encode()) == candidate, "Exact candidate unavailable")
        composition = json.loads(row[0])
        files = {}
        for module, revision in composition["modules"].items():
            for name in self.native.revision(tenant, module, revision)["objects"]:
                files[module + "/" + name] = base64.b64encode(self.native.read(tenant, module, revision, name)).decode()
        request = dict(
            role="reviewer",
            entry=_digest(_json(task).encode()),
            tenant=tenant,
            actor=actor,
            source=candidate,
            document=task,
            scopes=files,
            complexity={"installation": spec["identity"], "reviewer": spec["principals"]["reviewer"]},
        )
        encoded = _json(request)
        require(
            len(encoded.encode()) <= 100000,
            "Exact review context exceeds installed 100000-byte bound; candidate has not been reviewed",
        )
        key = _digest(encoded.encode())
        with self.domain._connection_lock, self.domain.db:
            old = self.domain.db.execute(
                "SELECT request,receipt FROM native_entry_reviews WHERE id=?", (key,)
            ).fetchone()
            if old:
                require(old[0] == encoded, "Review binding changed")
                require(
                    old[1] is not None or spec.get("mode") == "production",
                    "Review outcome unknown; no automatic replay",
                )
                receipt = json.loads(old[1]) if old[1] else None
            else:
                require(allow_start, "Review receipt unavailable; no replay")
                self.domain.db.execute("INSERT INTO native_entry_reviews VALUES (?,?,NULL)", (key, encoded))
                receipt = None
        if receipt is None:
            runtime = InstalledPlannerRuntime(self.installation, authority, role="reviewer")
            receipt = runtime.run(request, recover=old is not None)
            self.validate(receipt, request)
            with self.domain._connection_lock, self.domain.db:
                self.domain.db.execute("UPDATE native_entry_reviews SET receipt=? WHERE id=?", (_json(receipt), key))
        self.validate(receipt, request)
        self.authorize(actor, task["issue"], "review")
        authority()
        return True

    @staticmethod
    def validate(receipt, request):
        require(
            isinstance(receipt, dict)
            and set(receipt) == {"candidate", "accepted", "reviewer", "criteria", "inspected", "reason"},
            "Closed semantic review required",
        )
        require(
            receipt["candidate"] == request["source"] and receipt["accepted"] is True, "Independent candidate rejected"
        )
        require(receipt["reviewer"] == request["complexity"]["reviewer"], "Reviewer identity mismatch")
        require(
            receipt["criteria"] == request["document"]["source"]["definition"]["acceptance"],
            "Review does not bind original acceptance",
        )
        require(
            isinstance(receipt["inspected"], dict)
            and receipt["inspected"]
            == {path: _digest(base64.b64decode(value, validate=True)) for path, value in request["scopes"].items()},
            "Review does not cover exact candidate content",
        )
        require(isinstance(receipt["reason"], str) and receipt["reason"].strip(), "Semantic review rationale required")
