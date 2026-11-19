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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("project")
    parser.add_argument("--requirement")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--set", choices=["existing", "tianxuan"])
    action.add_argument("--historical", action="store_true")
    args = parser.parse_args()
    if args.set:
        configure(args.database, args.project, args.requirement, args.set)
    print(
        json.dumps({"entry": select_entry(args.database, args.project, args.requirement, historical=args.historical)})
    )
