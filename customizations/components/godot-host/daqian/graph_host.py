"""Godot's local plan source. An applied plan can be consumed on its plan event by a bound host."""
import argparse
import json
import os
import sqlite3
from pathlib import Path
import sys

import plan_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("action", choices=["read", "apply"])
    parser.add_argument("--request", type=Path)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    args.repo = args.repo.resolve()
    try:
        if args.number < 1:
            raise ValueError("工单编号无效")
        source = plan_store.read_source(args.repo, args.number)
        with plan_store.connect(args.repo) as db:
            result = plan_store.snapshot(db, source) if args.action == "read" else plan_store.apply(db, source, json.loads(args.request.read_text(encoding="utf-8")))
    except (ValueError, KeyError, OSError, RuntimeError, sqlite3.Error) as error:
        result = {"ok": False, "error": str(error)}
    temporary = args.result.with_suffix(".partial")
    temporary.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
    os.replace(temporary, args.result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
