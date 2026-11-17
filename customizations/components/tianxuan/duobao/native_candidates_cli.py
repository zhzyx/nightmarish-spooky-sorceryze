"""Local-owner CLI for immutable candidates; database/identity flags are trusted host inputs.

Never expose this process as an unauthenticated network service. The OS owner of
this database is the authority, as for native_cli; remote hosts use the library
with their own transaction-aware authorization callback.
"""

import argparse
import base64
import json
import sqlite3
import sys
from pathlib import Path

from native_candidates import NativeCandidates
from native_store import NativeStore, NativeStoreError
from native_workspace import Limits


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("db", "tenant", "actor", "request-key"):
        parser.add_argument("--" + name, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    receive = sub.add_parser("receive")
    receive.add_argument("--input", default="-")
    for name in ("source-ref", "worker-ref", "issue-url"):
        receive.add_argument("--" + name, required=True)
    sub.add_parser("receipt")
    args = parser.parse_args(argv)
    try:
        candidates = NativeCandidates(NativeStore(args.db), lambda *_: True)
        if args.command == "receipt":
            result = candidates.receipt(args.tenant, args.actor, args.request_key)
        else:
            if args.input == "-":
                raw = sys.stdin.buffer.read(Limits().request_bytes + 1)
            else:
                with Path(args.input).open("rb") as stream:
                    raw = stream.read(Limits().request_bytes + 1)
            if len(raw) > Limits().request_bytes:
                raise NativeStoreError("CLI request exceeds limit")
            changes = json.loads(raw)
            if not isinstance(changes, list):
                raise NativeStoreError("Expected changes list")
            for change in changes:
                if not isinstance(change, dict) or not isinstance(change.get("edits"), dict):
                    raise NativeStoreError("Expected edits mapping")
                for name, value in change["edits"].items():
                    if value is not None:
                        if not isinstance(value, str):
                            raise NativeStoreError("Expected base64 string or null")
                        change["edits"][name] = base64.b64decode(value, validate=True)
            origin = {name: getattr(args, name) for name in ("source_ref", "worker_ref", "issue_url")}
            result = candidates.receive(args.tenant, args.actor, args.request_key, changes, origin)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, sort_keys=True))
        return 0
    except (NativeStoreError, OSError, ValueError, sqlite3.Error, RecursionError) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__, "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
