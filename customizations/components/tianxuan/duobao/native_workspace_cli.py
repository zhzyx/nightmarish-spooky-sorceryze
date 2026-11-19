"""Trusted local JSON adapter. Parameters are identities, not authentication."""

import argparse
import base64
import json
import sqlite3
import subprocess
import sys
import zipfile

from native_store import NativeStore, NativeStoreError
from native_workspace import Limits, NativeWorkspace, absolute


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db")
    parser.add_argument("--tenant")
    parser.add_argument("command", choices=("materialize", "collect", "submit", "delta", "godot-import"))
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(Limits().request_bytes + 1)
        if len(raw) > Limits().request_bytes:
            raise NativeStoreError("Request exceeds limit")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise NativeStoreError("Expected JSON object")
        if args.command == "godot-import":
            from native_godot_import import import_issue

            if args.db is not None or args.tenant is not None or request.keys() != {"issue_id", "destination"}:
                raise NativeStoreError("Godot import requires only issue_id and destination")
            result = import_issue(**request)
            print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, sort_keys=True))
            return 0
        if not args.db or not args.tenant:
            raise NativeStoreError("Native database and tenant required")
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
    except (
        NativeStoreError,
        OSError,
        ValueError,
        TypeError,
        sqlite3.Error,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__, "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
