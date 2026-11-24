"""Select the entry for newly created tasks. Archived imports never enter a queue."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def select_entry(database, project, requirement=None, *, historical=False):
    if historical:
        return "archive"
    if not Path(database).is_file():
        return "existing"
    with closing(sqlite3.connect(database)) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='routing'").fetchone():
            return "existing"
        for key in (requirement, ""):
            if key is None:
                continue
            row = connection.execute(
                "SELECT entry FROM routing WHERE project=? AND requirement=?", (project, key)
            ).fetchone()
            if row:
                return row[0]
    return "existing"


def configure(database, project, requirement, entry):
    if not project.strip() or (requirement is not None and not requirement.strip()):
        raise ValueError("project and supplied requirement must be nonempty")
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS routing (project TEXT NOT NULL, requirement TEXT NOT NULL,"
            " entry TEXT CHECK(entry IN ('existing','tianxuan')) NOT NULL, PRIMARY KEY(project,requirement))"
        )
        connection.execute(
            "INSERT OR REPLACE INTO routing(project,requirement,entry) VALUES(?,?,?)",
            (project, requirement or "", entry),
        )


def tenant_entry(connection, tenant, project, requirement=None, *, entry=None):
    """Use the authenticated tenant's domain DB transaction, also available to an offline operator."""
    key = (tenant, project, requirement or "")
    if not tenant.strip() or not project.strip() or (requirement is not None and not requirement.strip()):
        raise ValueError("nonempty tenant, project and supplied requirement required")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS migration_entry (tenant TEXT, project TEXT, requirement TEXT, entry TEXT NOT NULL, PRIMARY KEY(tenant,project,requirement))"
    )
    if entry is not None:
        if entry not in ("existing", "tianxuan"):
            raise ValueError("invalid entry")
        connection.execute("INSERT OR REPLACE INTO migration_entry VALUES(?,?,?,?)", (*key, entry))
        return entry
    row = connection.execute(
        "SELECT entry FROM migration_entry WHERE tenant=? AND project=? AND requirement IN (?, '') ORDER BY length(requirement) DESC LIMIT 1",
        key,
    ).fetchone()
    return row[0] if row else "existing"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("project")
    parser.add_argument("--requirement")
    parser.add_argument("--tenant", help="Read or configure the online domain database for this tenant")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--set", choices=["existing", "tianxuan"])
    action.add_argument("--historical", action="store_true")
    args = parser.parse_args()
    if args.historical:
        entry = "archive"
    elif args.tenant:
        with closing(sqlite3.connect(args.database)) as connection, connection:
            entry = tenant_entry(connection, args.tenant, args.project, args.requirement, entry=args.set)
    else:
        if args.set:
            configure(args.database, args.project, args.requirement, args.set)
        entry = select_entry(args.database, args.project, args.requirement)
    print(json.dumps({"entry": entry}))
