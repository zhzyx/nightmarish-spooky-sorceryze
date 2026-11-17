"""Physical closure releases capacity without granting content authority."""

import json

import pytest

# pytest imports this fixture registration, then injects it by argument.
# ruff: noqa: F811
from native_store import NativeStoreError
from test_native_workflow import fixture, reserve, task  # noqa: F401
from tianxuan_core import PermissionDenied


def denied_after_close(f):
    w, actor, *_ = f
    w.principals = lambda a, i, role: "execution-producer" if role == "producer" else actor
    key, _ = task(f, "a")
    reserve(f, key)
    original_allow = w.worker.intake.authorize
    original_receive = w.worker.intake.receive
    denied = {"value": False}
    w.worker.intake.authorize = lambda db, t, a, m, op: (
        original_allow(db, t, a, m, op) and not (a == "execution-producer" and denied["value"])
    )

    def withdraw(*args, **kwargs):
        denied["value"] = True
        return original_receive(*args, **kwargs)

    w.worker.intake.receive = withdraw
    with pytest.raises(NativeStoreError, match="authorization denied"):
        w.execute(actor, key)
    w.worker.intake.receive = original_receive
    contract = json.loads(w.status(actor, key)["task"])
    assert w.worker.process_closed(contract, key)
    assert w.status(actor, key)["state"] == "held"
    return key, contract, denied


def test_closed_denied_output_frees_capacity_and_recovers_without_producer(fixture):
    w, actor, *_ = fixture
    key, original, denied = denied_after_close(fixture)
    assert w.reconcile(actor, key)["state"] == "closed-unresolved"
    row = w.status(actor, key)
    assert row["terminal"] is None and row["acceptance"] is None
    assert w.domain.get_issue(original["issue"])["status"] != "done"
    assert not w.inspect(actor)["environment"]["active"]
    other, _ = task(fixture, "b")
    reserve(fixture, other)
    # Restoring content permission consumes the already closed spool; it must
    # neither re-enter the producer nor mistake the physical receipt for output.
    w.worker.run = lambda *args: pytest.fail("Closed producer must not be relaunched")
    denied["value"] = False
    recovered = w.reconcile(actor, key)
    assert recovered["state"] == "produced"
    terminal = json.loads(recovered["terminal"])
    assert terminal["intake"]["actor"] == "execution-producer"
    assert w.domain.get_issue(original["issue"])["status"] == "in-review"
    assert w.reconcile(actor, key) == recovered
    assert recovered["acceptance"] is None


def test_corrupt_physical_closure_cannot_free_held_capacity(fixture):
    w, actor, *_ = fixture
    key, _, _ = denied_after_close(fixture)
    with w.worker.store._connection(write=True) as db:
        db.execute("UPDATE native_worker_process_closures SET digest=? WHERE execution=?", ("0" * 64, key))
    with pytest.raises(NativeStoreError, match="closure integrity"):
        w.reconcile(actor, key)
    assert w.status(actor, key)["state"] == "held"
    assert len(w.inspect(actor)["environment"]["active"]) == 1


def test_coordinator_permission_required_even_for_physical_closure(fixture):
    w, actor, *_ = fixture
    key, _, _ = denied_after_close(fixture)
    w.authorize = lambda a, i, action: action != "reconcile"
    with pytest.raises(PermissionDenied, match="authority denied"):
        w.reconcile(actor, key)
    assert w.status(actor, key)["state"] == "held"
    assert len(w.inspect(actor)["environment"]["active"]) == 1


def test_unknown_process_keeps_capacity(fixture):
    w, actor, *_ = fixture
    key, _ = task(fixture, "a")
    reserve(fixture, key)
    # Trusted coordinator fixture models loss of the launcher receipt, not a
    # completed process; the absence of a physical record must retain the slot.
    with w._transaction() as db:
        db.execute("UPDATE native_tasks SET state='held' WHERE id=?", (key,))
    assert w.reconcile(actor, key)["state"] == "held"
    assert len(w.inspect(actor)["environment"]["active"]) == 1


def test_replaced_unresolved_contract_cannot_close_new_issue(fixture):
    w, actor, *_ = fixture
    key, original, _ = denied_after_close(fixture)
    assert w.reconcile(actor, key)["state"] == "closed-unresolved"
    new = w.authorize_task(
        actor,
        original["issue"],
        selected=original["selected"],
        writes=original["writes"],
        dependencies=original["dependencies"],
        profile=original["profile"],
        product=original["product"],
        checks=original["checks"],
        mandate="explicit-replacement",
        expected=key,
    )
    assert w.reconcile(actor, key)["state"] == "superseded"
    assert w.status(actor, new)["state"] == "ready"
    assert w.domain.get_issue(original["issue"])["status"] == "planned"
