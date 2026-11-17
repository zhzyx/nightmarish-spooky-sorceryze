"""JSON command boundary for native Duobao, independent of Git and engine hosts."""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
from pathlib import Path

from native_store import NativeStore, NativeStoreError


def load_input(path: str):
    return json.loads(sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Explicit absolute database path")
    parser.add_argument("--tenant", required=True, help="Authenticated host tenant identity")
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--actor", required=True)
    submit.add_argument("--request-key", required=True)
    submit.add_argument("--input", default="-", help="JSON file, or stdin; edits use base64 strings/null")
    for name in ("head", "revision", "read"):
        command = sub.add_parser(name)
        command.add_argument("--module", required=True)
        if name != "head":
            command.add_argument("--revision", required=True)
        if name == "read":
            command.add_argument("--object", required=True)
    compose = sub.add_parser("compose")
    compose.add_argument("--input", default="-", help="JSON mapping module IDs to exact revisions")
    args = parser.parse_args(argv)
    try:
        store = NativeStore(args.db)
        if args.command == "submit":
            changes = load_input(args.input)
            if not isinstance(changes, list):
                raise NativeStoreError("Expected a list of changes")
            decoded = []
            for change in changes:
                if not isinstance(change, dict) or not isinstance(change.get("edits"), dict):
                    raise NativeStoreError("Expected change with edits mapping")
                item = dict(change)
                item["edits"] = {}
                for name, value in change["edits"].items():
                    if value is not None and not isinstance(value, str):
                        raise NativeStoreError("Edits must be base64 strings or null")
                    item["edits"][name] = None if value is None else base64.b64decode(value, validate=True)
                decoded.append(item)
            result = store.submit(args.tenant, args.actor, args.request_key, decoded)
        elif args.command == "head":
            result = {"revision": store.head(args.tenant, args.module)}
        elif args.command == "revision":
            result = store.revision(args.tenant, args.module, args.revision)
        elif args.command == "read":
            result = {
                "base64": base64.b64encode(store.read(args.tenant, args.module, args.revision, args.object)).decode(
                    "ascii"
                )
            }
        else:
            result = store.compose(args.tenant, load_input(args.input))
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, sort_keys=True))
        return 0
    except (NativeStoreError, OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__, "message": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
