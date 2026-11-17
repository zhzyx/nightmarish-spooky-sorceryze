"""Trusted local JSON adapter. Parameters are identities, not authentication."""

import argparse
import base64
import json
import sqlite3
import sys

from native_store import NativeStore, NativeStoreError
from native_workspace import Limits, NativeWorkspace, absolute


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("command", choices=("materialize", "collect", "submit", "delta"))
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(Limits().request_bytes + 1)
        if len(raw) > Limits().request_bytes:
            raise NativeStoreError("Request exceeds limit")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise NativeStoreError("Expected JSON object")
        fields = {
            "materialize": {"selected", "destination"},
            "collect": {"selected", "workspace"},
            "submit": {"selected", "workspace", "actor", "request_key"},
            "delta": {"module", "before", "after"},
        }[args.command]
        optional = {"limits"} | ({"cursor"} if args.command == "delta" else set())
        if not fields <= request.keys() or request.keys() - fields - optional:
            raise NativeStoreError("Invalid or missing request fields")
        limits = Limits(**request.pop("limits", {}))
        absolute(args.db, missing=True)
        adapter = NativeWorkspace(NativeStore(args.db), limits)
        result = getattr(adapter, args.command)(args.tenant, **request)
        if args.command == "collect":
            result = {
                "state": "candidate",
                "changes": [
                    dict(
                        change,
                        edits={
                            name: None if data is None else base64.b64encode(data).decode("ascii")
                            for name, data in change["edits"].items()
                        },
                    )
                    for change in result
                ],
            }
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, sort_keys=True))
        return 0
    except (NativeStoreError, OSError, ValueError, TypeError, sqlite3.Error) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__, "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
