"""Yanshi proposal validation at the native requirement boundary.

The installed runtime port owns host-http grants and role admission. This adapter
never accepts a grant, executable or product contract from an HTTP caller.
"""

import json
import re

from native_store import NativeStoreError, _digest, _json


def require(ok, message):
    if not ok:
        raise NativeStoreError(message)


def requirement_digest(document):
    # Progress timestamps change when tickets are created; source text/version do not.
    return _digest(_json({k: document[k] for k in ("id", "tenant_id", "version", "title", "body_md", "kind")}).encode())


def validate_plan(value, source, scopes, complexity):
    """Closed DAG; capabilities and finite write sets come from installation."""
    require(isinstance(value, dict) and set(value) == {"source", "tasks"}, "Closed requirement plan required")
    require(value["source"] == source, "Planner source revision changed")
    tasks = value["tasks"]
    require(isinstance(tasks, list) and 1 <= len(tasks) <= 64, "Plan must contain 1..64 tasks")
    names = set()
    normalized = []
    for task in tasks:
        require(
            isinstance(task, dict)
            and set(task) == {"id", "title", "body", "acceptance", "dependencies", "scope", "complexity", "outputs"},
            "Closed task proposal required",
        )
        name = task["id"]
        require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name), "Invalid local task ID")
        require(name not in names, "Duplicate task ID")
        names.add(name)
        for field in ("title", "body", "acceptance"):
            require(isinstance(task[field], str) and 0 < len(task[field]) <= 16000, "Task text/acceptance required")
        require(isinstance(task["scope"], str) and task["scope"] in scopes, "Task scope is not installed")
        require(isinstance(task["complexity"], str) and task["complexity"] in complexity, "Unmapped task complexity")
        scope = scopes[task["scope"]]
        outputs = task["outputs"]
        require(
            isinstance(outputs, list) and outputs and all(isinstance(p, str) for p in outputs),
            "Finite outputs required",
        )
        require(
            len(outputs) == len(set(outputs)) and set(outputs) <= set(scope["outputs"]),
            "Output outside installed scope",
        )
        dependencies = task["dependencies"]
        require(
            isinstance(dependencies, list)
            and all(isinstance(p, str) for p in dependencies)
            and len(dependencies) == len(set(dependencies)),
            "Unique dependency IDs required",
        )
        normalized.append({**task, "capabilities": list(complexity[task["complexity"]])})
    by_id = {t["id"]: t for t in normalized}
    visited, active = set(), set()

    def visit(name):
        require(name in by_id, "Unknown dependency")
        require(name not in active, "Dependency cycle")
        if name in visited:
            return
        active.add(name)
        for dependency in by_id[name]["dependencies"]:
            visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in names:
        visit(name)
    return normalized


class RequirementPlanner:
    def __init__(self, domain, ledger, runtime, scopes, complexity, authorize):
        self.domain, self.ledger, self.runtime = domain, ledger, runtime
        self.scopes, self.complexity, self.authorize = scopes, complexity, authorize

    def current(self, row):
        require(
            self.authorize(row["actor"], row["requirement"], "plan", row["id"]) is True, "Planning authority withdrawn"
        )
        self.domain._require_requirement(row["actor"], row["requirement"], write=True)
        document = self.domain.get_doc_shared(row["actor"], row["requirement"])
        require(requirement_digest(document) == row["source"], "Requirement revision changed")
        return document

    async def propose(self, row, *, recover=False):
        with self.ledger.transaction():
            document = self.current(row)
        choices = json.loads(row["payload"])["choices"]
        require(
            isinstance(choices, dict) and set(choices) in ({"scopes"}, {"scopes", "dependencies"}),
            "Only necessary scope choices are accepted",
        )
        selected = choices["scopes"]
        require(
            isinstance(selected, list) and selected and all(isinstance(s, str) and s in self.scopes for s in selected),
            "Selected installed scopes required",
        )
        scopes = {name: self.scopes[name] for name in selected}
        # This method is entered only after ledger.claim committed held intent.
        runtime = self.runtime.recover if recover else self.runtime
        proposal = await runtime({
            "role": "yanshi",
            "entry": row["id"],
            "tenant": row["tenant"],
            "actor": row["actor"],
            "source": row["source"],
            "document": document,
            "scopes": scopes,
            "complexity": self.complexity,
        })
        tasks = validate_plan(proposal, row["source"], scopes, self.complexity)
        with self.ledger.transaction():
            self.current(row)
        return tasks

    def persist(self, row, tasks):
        """Caller binds task contracts and this receipt in the same transaction.

        plan_tickets uses the existing idempotent domain receipt; no second Issue
        store. Contract authorization is deliberately separate from model output.
        """
        require(self.domain.db.in_transaction, "Plan persistence requires caller transaction")
        self.current(row)
        tickets = [
            {
                "title": t["title"],
                "type": "task",
                "acceptance": t["acceptance"],
                "priority": "normal",
                "body_md": t["body"],
            }
            for t in tasks
        ]
        issues = self.domain.plan_tickets(row["actor"], row["requirement"], tickets, call_id=row["id"])
        return {
            "parent": issues[0]["id"],
            "tasks": {t["id"]: issue["id"] for t, issue in zip(tasks, issues[1:], strict=True)},
        }
