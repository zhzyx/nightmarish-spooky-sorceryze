"""Bounded metadata export from private native receipt/outbox fixtures.

Never export file bodies, raw exception messages, paths or untrusted identifiers.
"""

import hashlib
import json
from pathlib import Path

MAX_FILES = 64
MAX_BYTES = 1024 * 1024
STATUSES = {"valid", "missing", "read_failed", "oversized", "invalid_utf8", "parse_failed", "invalid_schema"}


def file_metadata(path):
    result = {}
    try:
        if path.is_symlink():
            return {"state": "symlink_skipped"}
        result["size"] = path.stat().st_size
        if result["size"] > MAX_BYTES:
            return dict(result, state="oversized")
        with path.open("rb") as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            return dict(result, state="oversized")
        result["sha256"] = hashlib.sha256(content).hexdigest()
        try:
            value = json.loads(content)
        except (ValueError, UnicodeError) as error:
            result["state"] = "parse_failed"
            if isinstance(error, json.JSONDecodeError):
                result["parse_line"] = error.lineno
                result["parse_column"] = error.colno
            return result
        result["state"] = "json_object" if isinstance(value, dict) else "invalid_schema"
        if not isinstance(value, dict):
            return result
        if type(value.get("ok")) is bool:
            result["ok"] = value["ok"]
        # Preserve correlation without copying arbitrary user-controlled strings.
        result["identity_sha256"] = {
            key: hashlib.sha256(value[key].encode("utf-8", errors="surrogatepass")).hexdigest()
            for key in ("event_id", "request_id", "tenant_id", "source_ref")
            if isinstance(value.get(key), str)
        }
        if isinstance(value.get("status"), str) and value["status"] in STATUSES:
            result["native_status"] = value["status"]
        for key in ("exit_code", "read_attempts", "io_error", "parse_line"):
            if type(value.get(key)) is int:
                result[key] = value[key]
        if type(value.get("temporary_present")) is bool:
            result["temporary_present"] = value["temporary_present"]
    except OSError as error:
        result.update(state="read_failed", errno=error.errno, winerror=getattr(error, "winerror", None))
    return result


def collect_receipt_diagnostics(root, installation):
    root, installation = Path(root), Path(installation)
    result = {"receipts": [], "outbox": [], "limit_per_group": MAX_FILES, "raw_content_exported": False}
    # Portable editor cache location varies by platform. Only inspect fixture-owned
    # directories; never scan the user's global editor cache.
    candidates = installation.joinpath("editor_data").rglob("gonggong-receipt-*")
    for path in candidates:
        if path.is_dir():
            continue
        if len(result["receipts"]) == MAX_FILES:
            result["receipts_truncated"] = True
            break
        kind = (
            "diagnostic"
            if path.name.endswith(".diagnostic.json")
            else "temporary"
            if path.suffix == ".tmp"
            else "final"
        )
        identity = path.name.removesuffix(".diagnostic.json").removesuffix(".json").removesuffix(".tmp")
        result["receipts"].append(
            dict(
                file_metadata(path),
                kind=kind,
                identity_sha256=hashlib.sha256(identity.encode("utf-8", errors="surrogatepass")).hexdigest(),
            )
        )
    for path in root.joinpath(".gonggong-outbox/chat").glob("*"):
        if path.suffix not in (".json", ".tmp") or path.is_dir():
            continue
        if len(result["outbox"]) == MAX_FILES:
            result["outbox_truncated"] = True
            break
        result["outbox"].append(dict(file_metadata(path), kind="temporary" if path.suffix == ".tmp" else "pending"))
    return result
