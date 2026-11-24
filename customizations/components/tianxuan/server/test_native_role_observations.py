"""Projection from fixed role receipts and authorized original entry references."""

import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from native_entry_factory import OrdinaryEntry
from native_execution_host import EntryLedger
from native_installation import InstalledPlannerRuntime
from native_store import NativeStoreError, _digest, _json


def test_private_requested_name_does_not_discard_completed_role():
    observed = []
    installation = SimpleNamespace(
        spec={"mode": "production"}, command=lambda _: {"argv": ["fixture"], "env": {}}, verify=lambda: True
    )
    runtime = InstalledPlannerRuntime(
        installation, lambda _: True, observe=lambda request, digest, calls: observed.extend(calls)
    )
    request = {"entry": "fixture", "source": "source"}

    def completed(*args, stdout, **kwargs):
        stdout.write(
            _json({
                "input_digest": _digest(_json(request).encode()),
                "source": "source",
                "proposal": {"accepted": True},
                "runtime_state": "private-fixture-state",
                "model_calls": [
                    {
                        "requested_model": "team/model_v2",
                        "provider_model": "reported.model",
                        "usage": {"last": {"totalTokens": 0}},
                    }
                ],
            }).encode()
        )
        return 0

    runtime.helper = SimpleNamespace(run_owned=completed)
    assert runtime.run(request) == {"accepted": True}
    assert observed == [
        {"requested_model": None, "provider_model": "reported.model", "usage": {"last": {"totalTokens": 0}}}
    ]


def test_joint_review_refs_recovery_and_tenant_scope():
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        domain = SimpleNamespace(db=db, _connection_lock=threading.RLock())
        entry = OrdinaryEntry.__new__(OrdinaryEntry)
        entry.domain, entry.ledger = domain, EntryLedger(domain)
        entry.install_role_observations()
        for identifier, tenant, actor in [("a", "team", "alice"), ("b", "team", "ben"), ("c", "other", "charlie")]:
            db.execute(
                "INSERT INTO native_entry_intents VALUES (?,?,?,?,?,?,?,NULL)",
                (identifier, tenant, actor, "req", "source", "{}", "delivered"),
            )
        db.commit()
        originals = [
            {"contract": {"mandate": m, "tenant": "team", "actor": actor}}
            for m, actor in [("a", "alice"), ("b", "ben")]
        ]
        request = {
            "role": "reviewer",
            "tenant": "team",
            "actor": "reviewer",
            "document": {"mandate": "a", "integration_plan": {"originals": originals}},
        }
        digest = _digest(_json(request).encode())
        calls = [{"requested_model": "requested", "provider_model": None, "usage": None}]
        entry.observe_role_calls(request, digest, calls)
        entry.observe_role_calls(request, digest, calls)
        primary, secondary = entry.role_calls("a"), entry.role_calls("b")
        assert len(primary) == 1 and primary[0]["usage_attribution"] == "original"
        assert secondary == [{**primary[0], "usage_attribution": "reference"}]
        assert not entry.role_calls("c")
        assert db.execute("SELECT COUNT(*) FROM native_role_calls").fetchone()[0] == 1
        with pytest.raises(NativeStoreError, match="observation changed"):
            entry.observe_role_calls(request, digest, [{**calls[0], "provider_model": "changed"}])
        request["document"]["integration_plan"]["originals"].append({
            "contract": {"mandate": "c", "tenant": "other", "actor": "charlie"}
        })
        with pytest.raises(NativeStoreError, match="matching original"):
            entry.observe_role_calls(request, "invalid-cross-tenant", calls)
        assert db.execute("SELECT COUNT(*) FROM native_role_calls").fetchone()[0] == 1
        originals.pop()
        db.execute("DROP TABLE native_review_observation_refs")
        db.execute("CREATE TABLE native_entry_reviews(id TEXT PRIMARY KEY,request TEXT NOT NULL,receipt TEXT)")
        db.execute("INSERT INTO native_entry_reviews VALUES (?,?,?)", (digest, json.dumps(request), "{}"))
        db.commit()
        entry.install_role_observations()
        entry.install_role_observations()
        assert entry.role_calls("b") == secondary
        assert not entry.role_calls("c")
