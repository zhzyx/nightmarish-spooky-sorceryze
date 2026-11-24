"""Short central transactions reserve budgets; model execution only holds task locks.

Reservations never refund calls or rebind task identity, including after crashes.
A crashed active lease needs host reconciliation; this module never guesses closure.
"""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


@contextmanager
def reservation(grant, state):
    from runner import canonical, digest, jid_for, require

    p = grant["payload"]
    budget = p.get("central_budget")
    if budget is None:
        require(
            not any(
                m["protocol"] in {"codex-native-proposal", "codex-native-role", "local-agent-proposal"}
                for m in p["profiles"]
            ),
            "Native tasks require admitted central budget",
        )
        yield
        return
    require(set(budget) == {"state_dir", "max_calls", "max_concurrent", "authority_ref"}, "Invalid central budget")
    require(
        all(type(budget[k]) is int and budget[k] > 0 for k in ("max_calls", "max_concurrent")),
        "Invalid central ceilings",
    )
    require(bool(budget["authority_ref"]), "Central budget authority missing")
    root = Path(budget["state_dir"])
    require(root.is_absolute(), "Central ledger must be absolute")
    task = jid_for(p["task"])
    require(state.resolve() == (root / "tasks" / task).resolve(), "Task cannot change budget directory")
    root.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(root / "budget.sqlite", timeout=10)) as db:
        db.executescript(
            "CREATE TABLE IF NOT EXISTS authority (id INTEGER PRIMARY KEY, contract TEXT); CREATE TABLE IF NOT EXISTS reservations (task TEXT PRIMARY KEY, binding TEXT, calls INTEGER, active INTEGER);"
        )
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO authority VALUES (1,?)", (canonical(budget),))
        require(
            db.execute("SELECT contract FROM authority WHERE id=1").fetchone()[0] == canonical(budget),
            "Central admission changed",
        )
        binding = digest({k: v for k, v in p.items() if k not in {"expires_at", "replaces_grant"}})
        old = db.execute("SELECT binding,active FROM reservations WHERE task=?", (task,)).fetchone()
        if old:
            require(old[0] == binding, "Task cannot reset reserved budget by reauthorization")
            require(not old[1], "Original execution closure unknown; reconcile active lease")
        else:
            consumed = db.execute("SELECT COALESCE(SUM(calls),0) FROM reservations").fetchone()[0]
            require(consumed + p["limits"]["max_calls"] <= budget["max_calls"], "Central call budget exhausted")
            db.execute("INSERT INTO reservations VALUES (?,?,?,0)", (task, binding, p["limits"]["max_calls"]))
        require(
            db.execute("SELECT COUNT(*) FROM reservations WHERE active=1").fetchone()[0] < budget["max_concurrent"],
            "Central concurrency exhausted",
        )
        db.execute("UPDATE reservations SET active=1 WHERE task=?", (task,))
        db.commit()
    try:
        yield
    finally:
        with closing(sqlite3.connect(root / "budget.sqlite", timeout=10)) as db:
            db.execute("UPDATE reservations SET active=0 WHERE task=?", (task,))
            db.commit()
