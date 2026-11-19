"""Bounded installed Heqi adapter. No producer credentials or synthetic tasks."""

import base64
import binascii
import json

from native_installation import InstalledPlannerRuntime, require
from native_store import _digest, _json
from native_workspace import tree_names


class InstalledResolver:
    def __init__(self, factory):
        self.f = factory

    def binding(self):
        spec = self.f.installation.verify()
        return dict(
            installation=self.f.installation.sha256,
            principal=spec["principals"]["resolver"],
            command=spec["commands"]["resolver"],
        )

    def authorize(self, actor, plan):
        require(plan.get("resolver_binding") == self.binding(), "Frozen resolver installation required")
        integration = self.f.workflow.integration
        with self.f.workflow._transaction():
            integration._load(actor, _digest(_json(plan).encode()))
        principal = plan["principals"]["resolver"]
        require(principal != plan["principals"]["reviewer"], "Independent resolver reviewer required")
        with self.f.native._connection() as db:
            for module in plan["base"]:
                integration.candidates._allow(db, plan["tenant"], principal, module, "receive")
        return True

    def request(self, actor, plan, pending, key):
        self.authorize(actor, plan)
        source = _digest(_json(plan).encode())
        require(key == "resolution-" + source and pending["plan"] == source, "Exact resolver source required")
        conflicts = pending["conflicts"]
        require(
            conflicts and all("path" in c for c in conflicts),
            "Object conflicts only; dependency resolution unsupported",
        )
        slots = sorted({(c["module"], c["path"]) for c in conflicts})
        require(len(slots) <= 64, "Resolver file bound exceeded")
        for module, path in slots:
            tree_names({path: "0" * 64})
        total = 0

        def content(blob):
            nonlocal total
            if blob is None:
                return None
            with self.f.native._connection() as db:
                row = db.execute(
                    "SELECT content FROM native_blobs WHERE tenant=? AND digest=?", (plan["tenant"], blob)
                ).fetchone()
            require(row is not None, "Resolver blob unavailable")
            raw = bytes(row[0])
            require(_digest(raw) == blob, "Resolver blob changed")
            total += len(raw)
            require(
                len(raw) <= 32768 and total <= 65536,
                "Exact resolver input exceeds small-input bound; multi-revision tools unsupported",
            )
            return base64.b64encode(raw).decode("ascii")

        base, contributions = [], []
        for module, path in slots:
            state = self.f.native.revision(plan["tenant"], module, plan["base"][module])
            blob = state["objects"].get(path)
            base.append(
                dict(
                    module=module,
                    revision=state["id"] if "id" in state else plan["base"][module],
                    path=path,
                    blob=blob,
                    content_base64=content(blob),
                )
            )
        for original in plan["originals"]:
            if original["intake"] is None:
                continue
            task = original["contract"]
            terminal = json.loads(self.f.workflow.status(actor, original["task"])["terminal"])
            receipt = self.f.workflow.integration.candidates.receipt_for(
                plan["tenant"], actor, task["producer"], terminal["intake"]["request_key"]
            )
            for module, path in slots:
                if module not in receipt["inputs"]:
                    continue
                before = receipt["inputs"][module]["base"]
                after = receipt["revisions"][module]
                for label, revision in [("base", before), ("contribution", after)]:
                    state = self.f.native.revision(plan["tenant"], module, revision)
                    blob = state["objects"].get(path)
                    contributions.append(
                        dict(
                            task=original["task"],
                            kind=label,
                            module=module,
                            revision=revision,
                            path=path,
                            blob=blob,
                            content_base64=content(blob),
                        )
                    )
        history = []
        continuous = self.f.workflow.integration.continuous
        for reference in plan.get("continuation", {}).get("required_history", []):
            accepted = continuous.history(actor, plan["tenant"], plan["product"], plan["channel"], reference)
            history.append(accepted)
        request = dict(
            role="heqi",
            tenant=plan["tenant"],
            actor=actor,
            source=source,
            document=dict(
                schema=1,
                plan=source,
                conflicts=conflicts,
                conflicts_digest=_digest(_json(conflicts).encode()),
                originals=plan["originals"],
                accepted_history=history,
                request_key=key,
            ),
            scopes=dict(base=base, contributions=contributions),
            complexity=plan["resolver_binding"],
        )
        request["entry"] = _digest(_json(request).encode())
        require(len(_json(request).encode()) <= 100000, "Complete resolver request exceeds installed bound")
        return request

    def intake(self, actor, plan, request, proposal):
        self.authorize(actor, plan)
        require(
            isinstance(proposal, dict) and set(proposal) == {"schema", "plan", "conflicts_digest", "edits", "reason"},
            "Closed resolver proposal required",
        )
        require(
            type(proposal["schema"]) is int
            and proposal["schema"] == 1
            and proposal["plan"] == request["source"]
            and proposal["conflicts_digest"] == request["document"]["conflicts_digest"],
            "Resolver proposal source mismatch",
        )
        require(
            isinstance(proposal["reason"], str) and 0 < len(proposal["reason"]) <= 4000,
            "Bounded resolution reason required",
        )
        required = {(c["module"], c["path"]) for c in request["document"]["conflicts"]}
        require(
            isinstance(proposal["edits"], list) and len(proposal["edits"]) == len(required),
            "Exact resolver edit count required",
        )
        changes, seen, total = {}, set(), 0
        for item in proposal["edits"]:
            require(
                isinstance(item, dict) and set(item) == {"module", "path", "content_base64"},
                "Closed resolver edit required",
            )
            require(isinstance(item["module"], str) and isinstance(item["path"], str), "String resolver path required")
            slot = (item["module"], item["path"])
            require(slot in required and slot not in seen, "Exact unique conflict paths required")
            seen.add(slot)
            raw = item["content_base64"]
            if raw is not None:
                require(isinstance(raw, str) and len(raw) <= 43692, "Bounded base64 required")
                try:
                    raw = base64.b64decode(raw, validate=True)
                except (ValueError, binascii.Error):
                    require(False, "Invalid resolver base64")
                total += len(raw)
                require(len(raw) <= 32768 and total <= 65536, "Resolver output byte bound exceeded")
            changes.setdefault(item["module"], {})[item["path"]] = raw
        items = []
        for module, edits in sorted(changes.items()):
            state = self.f.native.revision(plan["tenant"], module, plan["base"][module])
            items.append(
                dict(
                    module=module,
                    base=plan["base"][module],
                    reads=None,
                    edits=edits,
                    dependencies=state["dependencies"],
                )
            )
        receipt = self.f.workflow.integration.candidates.receive(
            plan["tenant"],
            plan["principals"]["resolver"],
            request["document"]["request_key"],
            items,
            dict(
                source_ref=request["source"],
                worker_ref="heqi-resolution-" + request["source"],
                issue_url=plan["issue_url"],
            ),
        )
        self.authorize(actor, plan)
        return receipt

    def run(self, actor, plan, pending, key, *, recover=False):
        request = self.request(actor, plan, pending, key)
        previous = plan.get("continuation", {}).get("previous_plan")
        if previous:
            integration = self.f.workflow.integration
            with self.f.workflow._transaction():
                _, prior = integration._load(actor, previous)
            if prior.get("resolution"):
                require(
                    prior["conflicts"] == request["document"]["conflicts_digest"],
                    "CAS changed resolution inputs; new explicit resolution authority required",
                )
                edits = []
                receipt = prior["resolution"]
                for module, item in receipt["inputs"].items():
                    old = self.f.native.revision(plan["tenant"], module, receipt["revisions"][module])
                    current = self.f.native.revision(plan["tenant"], module, plan["base"][module])
                    require(old["dependencies"] == current["dependencies"], "CAS changed resolution dependencies")
                    for path in item["edits"]:
                        raw = (
                            self.f.native.read(plan["tenant"], module, receipt["revisions"][module], path)
                            if path in old["objects"]
                            else None
                        )
                        edits.append(
                            dict(
                                module=module,
                                path=path,
                                content_base64=base64.b64encode(raw).decode() if raw is not None else None,
                            )
                        )
                proposal = dict(
                    schema=1,
                    plan=request["source"],
                    conflicts_digest=request["document"]["conflicts_digest"],
                    edits=edits,
                    reason="Reuse authenticated resolution after unrelated channel CAS",
                )
                return self.intake(actor, plan, request, proposal)
        runtime = InstalledPlannerRuntime(self.f.installation, lambda _: self.authorize(actor, plan), role="resolver")
        proposal = runtime.run(request, recover=recover)
        return self.intake(actor, plan, request, proposal)

    def __call__(self, actor, plan, pending, key):
        return self.run(actor, plan, pending, key)

    def recover(self, actor, plan, pending, key):
        return self.run(actor, plan, pending, key, recover=True)
