"""Coordinator handoff uses exact policy CAS and immutable publication readback."""

import json

import pytest
from native_integration import digest
from native_store import NativeStoreError
from test_native_continuous import continuous
from test_native_workflow import fixture  # noqa: F401

# ruff: noqa: F811


def member(f):
    w, actor, _, req, *_ = f
    other = w.domain.add_member(actor, "handoff@example.invalid", "password")["user_id"]
    w.domain.share_doc(actor, req["id"], other, "write")
    return other


def test_idle_handoff_cas_and_audit(fixture):
    w, actor, tenant, *_ = fixture
    integration, _, policy, lane = continuous(fixture)
    other = member(fixture)
    result = integration.continuous.handoff(other, tenant, "joint", "stable", digest(policy))
    assert result["old_actor"] == actor and result["actor"] == other
    with w.domain._connection_lock:
        row = w.domain.db.execute("SELECT * FROM native_continuous_lanes WHERE id=?", (lane,)).fetchone()
        assert row["actor"] == other
        assert json.loads(row["policy"])["base"] == policy["base"]
    with pytest.raises(NativeStoreError, match="CAS"):
        integration.continuous.handoff(actor, tenant, "joint", "stable", digest(policy))


def test_unknown_publication_handoff_keeps_original(fixture):
    w, actor, tenant, *_ = fixture
    integration, keys, policy, lane = continuous(fixture)
    other = member(fixture)
    batch = integration.continuous.freeze(actor, lane, policy, [keys[0]])
    with pytest.raises(NativeStoreError, match="unknown"):
        integration.continuous.handoff(other, tenant, "joint", "stable", digest(policy))
    row = w.domain.db.execute("SELECT * FROM native_continuous_lanes WHERE id=?", (lane,)).fetchone()
    assert row["actor"] == actor and row["active"] == batch


def test_accepted_unreconciled_handoff_reads_physical_publication(fixture):
    w, actor, tenant, *_ = fixture
    integration, _, policy, lane = continuous(fixture)
    result = integration.continue_lane(actor, lane)
    assert result["state"] == "accepted"
    with w._transaction() as db:
        db.execute("UPDATE native_continuous_lanes SET active=? WHERE id=?", (result["batch"], lane))
    received = integration.continuous.handoff(actor, tenant, "joint", "stable", digest(policy))
    assert received["reconciled"] == result["batch"]
    assert w.domain.db.execute("SELECT active FROM native_continuous_lanes WHERE id=?", (lane,)).fetchone()[0] is None


def test_cross_tenant_handoff_denied(fixture):
    w, _, tenant, *_ = fixture
    integration, _, policy, _ = continuous(fixture)
    outsider = w.domain.register("other", "outside@example.invalid", "password")["user_id"]
    with pytest.raises(NativeStoreError, match="same-tenant"):
        integration.continuous.handoff(outsider, tenant, "joint", "stable", digest(policy))
