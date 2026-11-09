"""Keep active work-order provenance present while an approved command runs.

Only the command child inherits the optional macOS profile. Before-images and
recovery remain outside that child. This is provenance protection, not a shell
sandbox or evidence of Git publication.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import editor_engine_candidate as candidates
import editor_provenance_process as processes

EXIT_VIOLATION = 76
PREFIX = "GONGGONG_PROVENANCE_GUARD "
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_FILES = 4096
MAX_SCAN = 50000
MAX_PROFILE = 200000
MAX_REGEX = 768
STORE = "gonggong-provenance-guards"
_EVENT_MODULE = None


class GuardError(ValueError):
    pass


def events_module():
    global _EVENT_MODULE
    if _EVENT_MODULE is None:
        path = (
            Path(__file__).resolve().parents[1]
            / "customizations/platforms/data-collection/git-files/storage/diting_files.py"
        )
        spec = importlib.util.spec_from_file_location("provenance_diting", path)
        if spec is None or spec.loader is None:
            raise GuardError("provenance_storage_unavailable")
        _EVENT_MODULE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_EVENT_MODULE)
    return _EVENT_MODULE


def checked(root, name):
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != str(name):
        raise GuardError("provenance_path_invalid")
    path = root / relative
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise GuardError("provenance_path_linked")
    if path.exists() and not path.is_file():
        raise GuardError("provenance_path_conflict")
    return path


def read_bytes(path, limit=MAX_FILE):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise GuardError("provenance_file_invalid_or_oversized")
    data = path.read_bytes()
    if len(data) > limit:
        raise GuardError("provenance_file_invalid_or_oversized")
    return data


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path, limit=MAX_FILE):
    read_bytes(path, limit)
    return events_module().read(path)


def bound(binding_path):
    path = Path(binding_path).absolute()
    if path.is_symlink() or path.resolve() != path:
        raise GuardError("provenance_binding_invalid")
    binding = read_json(path)
    if not isinstance(binding, dict) or binding.get("state") != "prepared":
        raise GuardError("provenance_binding_invalid")
    source = Path(binding.get("source_root", ""))
    common, repository, origin = candidates.identity(source)
    issue, request, owner = binding.get("issue"), binding.get("request_id"), binding.get("owner")
    if (
        type(issue) is not int
        or issue < 1
        or not isinstance(request, str)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request)
        or not isinstance(owner, str)
        or not owner
    ):
        raise GuardError("provenance_binding_invalid")
    digest = candidates.candidate_digest(common, repository, issue, request, owner)
    if path != common / "gonggong-engine-candidates" / (digest + ".json") or source.name != "godot-candidate-" + digest:
        raise GuardError("provenance_binding_invalid")
    expected = {
        "version": 1,
        "owner": owner,
        "issue": issue,
        "request_id": request,
        "common_dir": str(common),
        "repository": repository,
        "origin": origin,
        "source_root": str(source),
        "branch": "codex/engine-candidate/" + request + "-" + digest,
    }
    candidates.validate_source(source, binding, expected)
    settings = read_json(source / "work-items.json")
    tenant = settings.get("tenant_id")
    if not isinstance(tenant, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", tenant):
        raise GuardError("provenance_tenant_invalid")
    return dict(expected, base_sha=binding["base_sha"], binding_path=str(path), tenant_id=tenant), digest


def directory(root, relative):
    path = root / relative
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise GuardError("provenance_path_linked")
    if path.exists() and not path.is_dir():
        raise GuardError("provenance_path_conflict")
    return path


def walk_json(root, relative):
    folder = directory(root, relative)
    if not folder.exists():
        return
    seen = 0
    for base, folders, names in os.walk(folder, followlinks=False):
        for name in folders + names:
            path = Path(base) / name
            seen += 1
            if seen > MAX_SCAN:
                raise GuardError("provenance_scan_limit")
            if path.is_symlink():
                raise GuardError("provenance_path_linked")
        for name in names:
            if name.endswith(".json"):
                yield Path(base) / name


def normal_event(path, persisted=False):
    value = read_json(path)
    if persisted and (not isinstance(value, dict) or "sha256" not in value):
        raise GuardError("provenance_event_checksum_missing")
    return events_module().event(value)


def collection_candidates(root, request):
    # Git identifies already-committed matching records without parsing every
    # historical JSON in Python. Read only those plus changed/new candidates.
    names = set()
    # Search the quoted value rather than a same-line key/value pair: JSON
    # permits a newline between the request_id key and its value.
    pattern = '"' + request + '"'
    found = candidates.git(root, "grep", "-I", "-l", "-z", "-F", pattern, "HEAD", "--", "data-collection", check=False)
    if found.returncode not in (0, 1):
        raise GuardError("provenance_collection_discovery_failed")
    names.update(name.removeprefix("HEAD:") for name in found.stdout.split("\0") if name)
    for arguments in (
        ("diff", "--name-only", "-z", "HEAD", "--", "data-collection"),
        ("ls-files", "--others", "--exclude-standard", "-z", "--", "data-collection"),
    ):
        names.update(name for name in candidates.git(root, *arguments).stdout.split("\0") if name)
    if len(names) > MAX_SCAN:
        raise GuardError("provenance_scan_limit")
    for name in sorted(names):
        if name.endswith(".json"):
            yield checked(root, name)


def capture_entries(binding):
    root = Path(binding["source_root"])
    request, tenant = binding["request_id"], binding["tenant_id"]
    entries = {}
    total = 0

    def add(path, kind, event=None):
        nonlocal total
        name = path.relative_to(root).as_posix()
        path = checked(root, name)
        data = read_bytes(path)
        total += len(data)
        if len(entries) >= MAX_FILES or total > MAX_TOTAL:
            raise GuardError("provenance_snapshot_limit")
        item = {
            "kind": kind,
            "sha256": fingerprint(data),
            "mode": stat.S_IMODE(path.stat().st_mode),
            "content_base64": base64.b64encode(data).decode("ascii"),
        }
        if event is not None:
            item["event"] = {key: event[key] for key in ("tenant_id", "request_id", "event_id", "sha256")}
        entries[name] = item

    add(root / "design-docs" / (request + ".md"), "doc")
    # Dataset metadata is immutable too; otherwise an apparently stored event
    # could no longer be consumed by the real storage adapter.
    for name in ("gonggong-diting-data/dataset.json", "gonggong-diting-data/.gitattributes"):
        path = checked(root, name)
        if path.exists():
            add(path, "immutable")
    found_request = False
    for path in walk_json(root, Path("gonggong-diting-data/events") / tenant / request):
        event = normal_event(path, persisted=True)
        if event["tenant_id"] != tenant or event["request_id"] != request:
            raise GuardError("provenance_event_identity_mismatch")
        if event["kind"] == "request" and event["source_ref"] in {
            f"https://github.com/{binding['repository']}/issues/{binding['issue']}",
            f"github:{binding['repository']}:issue:{binding['issue']}",
        }:
            found_request = True
        add(path, "immutable")
    if not found_request:
        raise GuardError("provenance_request_source_missing")
    for path in collection_candidates(root, request):
        value = read_json(path)
        if isinstance(value, dict) and value.get("request_id") == request:
            add(path, "immutable")
    for path in walk_json(root, Path(".gonggong-outbox/chat")):
        # A flush consumes the shared queue, so retain every pending envelope
        # observed here, including one belonging to another bound request.
        event = normal_event(path)
        if path.name != event["event_id"] + ".json":
            raise GuardError("provenance_pending_identity_mismatch")
        add(path, "pending", event)
    return entries


def process_identity(pid):
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return {"pid": pid, "birth": "unknown"} if ctypes.get_last_error() == 5 else None
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
                return {"pid": pid, "birth": "unknown"}
            return {"pid": pid, "birth": str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)}
        finally:
            kernel.CloseHandle(handle)
    proc = Path("/proc") / str(pid) / "stat"
    try:
        fields = proc.read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else {"pid": pid, "birth": fields[19]}
    except (OSError, IndexError):
        pass
    try:
        result = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "lstart=", "-o", "state="], capture_output=True, text=True, timeout=3
        )
        parts = result.stdout.strip().rsplit(None, 1)
        if result.returncode == 0 and len(parts) == 2:
            return None if parts[1].startswith("Z") else {"pid": pid, "birth": parts[0]}
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        os.kill(pid, 0)
        return {"pid": pid, "birth": "unknown"}
    except ProcessLookupError:
        return None
    except PermissionError:
        return {"pid": pid, "birth": "unknown"}


def alive(identity):
    if not isinstance(identity, dict):
        return False
    current = process_identity(identity.get("pid"))
    return bool(
        current and (identity.get("birth") == "unknown" or current["birth"] == "unknown" or current == identity)
    )


def guard_folder(binding, digest):
    common = Path(binding["common_dir"])
    folder = common / STORE / digest
    for path in (common / STORE, folder):
        if path.is_symlink():
            raise GuardError("provenance_private_path_linked")
        path.mkdir(mode=0o700, exist_ok=True)
    return folder


@contextmanager
def outbox_snapshot(root):
    folder = directory(root, Path(".gonggong-outbox/chat"))
    folder.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 15
    while True:
        try:
            with candidates.binding_lock(folder / ".flush.lock"):
                yield
                return
        except candidates.CandidateError as error:
            if str(error) != "candidate_binding_busy":
                raise
            if time.monotonic() >= deadline:
                raise GuardError("provenance_delivery_busy") from None
            time.sleep(0.05)


def capture(binding, digest):
    with outbox_snapshot(Path(binding["source_root"])):
        entries = capture_entries(binding)
    record = {
        "schema_version": 1,
        "token": uuid.uuid4().hex,
        "binding": binding,
        "entries": entries,
        "state": "captured",
        "runner": process_identity(os.getpid()),
        "child": None,
        "created_at": time.time(),
    }
    pending = guard_folder(binding, digest) / "pending"
    if pending.is_symlink():
        raise GuardError("provenance_private_path_linked")
    pending.mkdir(mode=0o700, exist_ok=True)
    path = pending / (record["token"] + ".json")
    candidates.atomic_json(path, record)
    return path, record


def checkpoint_token(digest):
    return fingerprint(("checkpoint:" + digest).encode())[:32]


@contextmanager
def checkpoint_lock(binding, digest):
    folder = guard_folder(binding, digest)
    deadline = time.monotonic() + 15
    while True:
        try:
            with candidates.binding_lock(folder / ".checkpoint.lock"):
                yield folder
                return
        except candidates.CandidateError as error:
            if str(error) != "candidate_binding_busy":
                raise
            if time.monotonic() >= deadline:
                raise GuardError("provenance_checkpoint_busy") from None
            time.sleep(0.05)


def checkpoint_sync(binding, digest, seed=None, create=False):
    # Always take the private lock before the real delivery lock. A command's
    # journal can close while this checkpoint keeps the same before-images
    # available for a detached descendant's later deletion.
    with checkpoint_lock(binding, digest) as folder:
        pending = folder / "pending"
        if pending.is_symlink():
            raise GuardError("provenance_private_path_linked")
        token = checkpoint_token(digest)
        path = pending / (token + ".json")
        if path.is_symlink():
            raise GuardError("provenance_journal_invalid")
        with outbox_snapshot(Path(binding["source_root"])):
            if path.exists():
                record = read_json(path, 192 * 1024 * 1024)
                if not isinstance(record, dict) or record.get("state") != "checkpoint" or record.get("token") != token:
                    raise GuardError("provenance_checkpoint_invalid")
            elif not create:
                return None
            else:
                pending.mkdir(mode=0o700, exist_ok=True)
                record = {
                    "schema_version": 1,
                    "token": token,
                    "binding": binding,
                    "entries": dict(seed) if seed is not None else capture_entries(binding),
                    "state": "checkpoint",
                    "created_at": time.time(),
                }
            result = verify_record_locked(path, record, binding)
            conflicts = [item for item in result["violations"] if not item.get("restored", False)]
            if not conflicts:
                retained = dict(record["entries"])
                for name in result["consumed"]:
                    retained.pop(name, None)
                # Retain existing proof even if Git discovery later ignores
                # a restored collection path. Only verified consumption drops
                # a pending envelope; an allowed document edit saves new bytes.
                fresh = capture_entries(binding)
                if seed is not None:
                    for name, item in seed.items():
                        if name not in retained and name not in result["consumed"]:
                            retained[name] = item
                for name, item in fresh.items():
                    if name not in retained or item["kind"] == "doc":
                        retained[name] = item
                if len(retained) > MAX_FILES or sum(len(entry_bytes(item)) for item in retained.values()) > MAX_TOTAL:
                    raise GuardError("provenance_snapshot_limit")
                record["entries"] = retained
            record["original_command_result_unchanged"] = True
            record["updated_at"] = time.time()
            candidates.atomic_json(path, record)
            return {
                "token": token,
                "checkpoint": True,
                **result,
                "can_flush": not conflicts,
                "original_command_result_unchanged": True,
            }


def entry_bytes(item):
    try:
        data = base64.b64decode(item["content_base64"], validate=True)
    except (KeyError, TypeError, ValueError):
        raise GuardError("provenance_journal_invalid") from None
    if (
        len(data) > MAX_FILE
        or fingerprint(data) != item.get("sha256")
        or type(item.get("mode")) is not int
        or not 0 <= item["mode"] <= 0o7777
    ):
        raise GuardError("provenance_journal_invalid")
    return data


def persisted_pending(root, item, cache=None):
    expected = item.get("event")
    if not isinstance(expected, dict):
        raise GuardError("provenance_journal_invalid")
    original = events_module().event(json.loads(entry_bytes(item)))
    if expected != {key: original[key] for key in ("tenant_id", "request_id", "event_id", "sha256")}:
        raise GuardError("provenance_journal_invalid")
    cache = {} if cache is None else cache
    for dataset in ("gonggong-diting-data", "olympus-hermes-data"):
        name = f"{dataset}/events/{original['tenant_id']}/{original['request_id']}/{original['event_id']}.json"
        path = checked(root, name)
        if not path.exists():
            continue
        # A schema/hash-valid event is not consumable when its evidence graph
        # is invalid. Use the actual adapter for both datasets, once per check.
        if dataset not in cache:
            try:
                cache[dataset] = events_module().load(root, historical=dataset == "olympus-hermes-data")[3]
            except (OSError, ValueError, TypeError, KeyError):
                cache[dataset] = None
        if cache[dataset] is None:
            raise GuardError("provenance_persisted_dataset_invalid")
        actual = cache[dataset].get((original["tenant_id"], original["event_id"]))
        if actual == original:
            return True
        raise GuardError("provenance_persisted_event_conflict")
    return False


def restore_absent(root, name, data, mode):
    destination = checked(root, name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = checked(root, name)
    descriptor, temporary = tempfile.mkstemp(prefix=".provenance-restore-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.link(temporary, destination)  # Never overwrite a concurrently created file.
    except FileExistsError:
        if read_bytes(destination) != data:
            raise GuardError("provenance_restore_conflict") from None
    finally:
        Path(temporary).unlink(missing_ok=True)


def verify_record(path, record, binding):
    with outbox_snapshot(Path(binding["source_root"])):
        return verify_record_locked(path, record, binding)


def validate_entry_scope(name, item, data, binding):
    request, tenant = binding["request_id"], binding["tenant_id"]
    relative = Path(name)
    if item["kind"] == "doc":
        valid = name == "design-docs/" + request + ".md"
    elif item["kind"] == "pending":
        value = events_module().event(json.loads(data))
        valid = relative.parent == Path(".gonggong-outbox/chat") and relative.name == value["event_id"] + ".json"
    elif name in {"gonggong-diting-data/dataset.json", "gonggong-diting-data/.gitattributes"}:
        valid = True
    elif relative.parent == Path("gonggong-diting-data/events") / tenant / request:
        value = events_module().event(json.loads(data))
        valid = (
            value["tenant_id"] == tenant
            and value["request_id"] == request
            and relative.name == value["event_id"] + ".json"
            and "sha256" in json.loads(data)
        )
    elif relative.parts[:1] == ("data-collection",) and relative.suffix == ".json":
        value = json.loads(data)
        valid = isinstance(value, dict) and value.get("request_id") == request
    else:
        valid = False
    if not valid:
        raise GuardError("provenance_journal_scope_invalid")


def verify_record_locked(path, record, binding):
    if (
        record.get("schema_version") != 1
        or record.get("binding") != binding
        or not isinstance(record.get("entries"), dict)
        or len(record["entries"]) > MAX_FILES
    ):
        raise GuardError("provenance_journal_binding_mismatch")
    if path.name != str(record.get("token")) + ".json" or not re.fullmatch(r"[a-f0-9]{32}", str(record.get("token"))):
        raise GuardError("provenance_journal_invalid")
    root = Path(binding["source_root"])
    violations, restored, consumed = [], [], []
    total = 0
    persisted = {}
    for name, item in record["entries"].items():
        if (
            not isinstance(name, str)
            or not isinstance(item, dict)
            or item.get("kind") not in {"doc", "immutable", "pending"}
        ):
            raise GuardError("provenance_journal_invalid")
        data = entry_bytes(item)
        validate_entry_scope(name, item, data, binding)
        total += len(data)
        if total > MAX_TOTAL:
            raise GuardError("provenance_snapshot_limit")
        try:
            destination = checked(root, name)
            if destination.exists():
                current = read_bytes(destination)
                if item["kind"] != "doc" and fingerprint(current) != item["sha256"]:
                    violations.append({"path": name, "reason": "content_changed"})
            else:
                delivered = False
                if item["kind"] == "pending":
                    try:
                        delivered = persisted_pending(root, item, persisted)
                    except (OSError, ValueError, TypeError, KeyError):
                        violations.append({"path": name, "reason": "persisted_event_conflict"})
                if delivered:
                    consumed.append(name)
                    continue
                missing = {"path": name, "reason": "missing", "restored": False}
                violations.append(missing)
                restore_absent(root, name, data, item["mode"])
                missing["restored"] = True
                restored.append(name)
        except (OSError, ValueError, TypeError, KeyError) as error:
            reason = str(error) if isinstance(error, GuardError) else "path_or_storage_conflict"
            violations.append({"path": name, "reason": reason})
    record["violations"] = violations
    record["restored"] = restored
    record["consumed"] = consumed
    record["checked_at"] = time.time()
    return {"ok": not violations, "violations": violations, "restored": restored, "consumed": consumed}


def profile_for(base, record):
    if not isinstance(base, str) or not base.strip() or len(base.encode()) > MAX_PROFILE:
        raise GuardError("provenance_profile_invalid")
    root = Path(record["binding"]["source_root"])
    common = Path(record["binding"]["common_dir"])
    journal = Path(record["binding"]["binding_path"])
    private = common / STORE / journal.stem
    immutable = {}
    # Keep the flush lock inode and its directory stable, while pending JSON
    # files remain consumable by the real storage adapter.
    unlink = {
        str(root / name) for name in (".gonggong-outbox", ".gonggong-outbox/chat", ".gonggong-outbox/chat/.flush.lock")
    }
    for name, item in record["entries"].items():
        if item["kind"] == "pending":
            continue
        path = root / name
        if item["kind"] == "immutable":
            immutable.setdefault(str(path.parent), []).append(path.name)
        else:
            unlink.add(str(path))
        for parent in path.parents:
            if parent == root.parent:
                break
            unlink.add(str(parent))

    # Group exact existing filenames under each parent. These expressions match
    # no new filename, so trusted writers can still append fresh evidence.
    def escape(value):
        special = set(".[]{}()*+?^$|") | {chr(92)}
        return "".join(chr(92) + char if char in special else char for char in value)

    extra = (
        "(deny file-write* (subpath "
        + json.dumps(str(private), ensure_ascii=False)
        + ") (literal "
        + json.dumps(str(journal), ensure_ascii=False)
        + "))"
    )
    for path in (private, private.parent, common, journal.parent):
        unlink.add(str(path))
    if record.get("cancel_file"):
        marker = Path(record["cancel_file"])
        extra += "(deny file-write* (literal " + json.dumps(str(marker), ensure_ascii=False) + "))"
        unlink.update(str(parent) for parent in marker.parents)
    for parent, names in sorted(immutable.items()):
        prefix = "^" + escape(parent) + "/("
        grouped = []
        for name in sorted(names):
            candidate = prefix + "|".join([*grouped, escape(name)]) + ")$"
            # Seatbelt's string reader rejects a single long regex even when
            # the complete profile is within the command-line byte budget.
            if len(json.dumps(candidate, ensure_ascii=False).encode()) > MAX_REGEX:
                if grouped:
                    extra += (
                        "(deny file-write* (regex "
                        + json.dumps(prefix + "|".join(grouped) + ")$", ensure_ascii=False)
                        + "))"
                    )
                    grouped = []
                single = prefix + escape(name) + ")$"
                if len(json.dumps(single, ensure_ascii=False).encode()) > MAX_REGEX:
                    extra += (
                        "(deny file-write* (literal " + json.dumps(str(Path(parent) / name), ensure_ascii=False) + "))"
                    )
                    continue
            grouped.append(escape(name))
        if grouped:
            extra += (
                "(deny file-write* (regex " + json.dumps(prefix + "|".join(grouped) + ")$", ensure_ascii=False) + "))"
            )
    if unlink:
        extra += (
            "(deny file-write-unlink "
            + " ".join("(literal " + json.dumps(name, ensure_ascii=False) + ")" for name in sorted(unlink))
            + ")"
        )
    result = base + extra
    if len(result.encode()) > MAX_PROFILE:
        raise GuardError("provenance_profile_limit")
    return result


def archive(path, record):
    closed = path.parent.parent / "closed"
    if closed.is_symlink():
        raise GuardError("provenance_private_path_linked")
    closed.mkdir(mode=0o700, exist_ok=True)
    candidates.atomic_json(path, record)
    os.replace(path, closed / path.name)


def compact_result(value):
    result = {key: item for key, item in value.items() if key not in {"violations", "consumed", "restored"}}
    violations = value.get("violations", [])
    restored = value.get("restored", [])
    result["violation_count"] = len(violations)
    result["restored_count"] = len(restored)
    result["consumed_count"] = len(value.get("consumed", []))
    result["restored"] = [name[:240] for name in restored[:24]]
    result["conflicts"] = [{"path": item["path"][:240], "reason": item["reason"][:120]} for item in violations[:24]]
    result["details_truncated"] = len(violations) > 24 or len(restored) > 24
    return result


def emit(value):
    print(
        PREFIX + json.dumps(compact_result(value), ensure_ascii=False, separators=(",", ":")),
        file=sys.stderr,
        flush=True,
    )


def publish_result(path, value):
    if path is not None:
        candidates.atomic_json(Path(path), compact_result(value))


def cancel_path(value, source):
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path or path.is_symlink() or not path.parent.is_dir():
        raise GuardError("provenance_cancel_path_invalid")
    if path == source or source in path.parents:
        raise GuardError("provenance_cancel_path_invalid")
    if path.exists() and not path.is_file():
        raise GuardError("provenance_cancel_path_invalid")
    return path


def windows_taskkill(child):
    if child.poll() is not None:
        return
    system = os.environ.get("SystemRoot", "")
    executable = os.path.join(system, "System32", "taskkill.exe")
    if not os.path.isabs(system) or not os.path.isfile(executable):
        raise GuardError("provenance_windows_taskkill_unavailable")
    try:
        result = subprocess.run([executable, "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        raise GuardError("provenance_windows_taskkill_failed") from None
    if result.returncode and child.poll() is None:
        raise GuardError("provenance_windows_taskkill_failed")


def process_group_members(pgid):
    if type(pgid) is not int or pgid <= 1:
        raise GuardError("provenance_owned_group_invalid")
    try:
        result = subprocess.run(["/bin/ps", "-axo", "pid=,pgid=,stat="], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        raise GuardError("provenance_group_query_failed") from None
    if result.returncode or len(result.stdout) > 8 * 1024 * 1024:
        raise GuardError("provenance_group_query_failed")
    members = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
            raise GuardError("provenance_group_query_failed")
        if int(parts[1]) == pgid and not parts[2].startswith("Z"):
            members.append(int(parts[0]))
    return members


def quiesce_owned_group(pgid, expected_identity):
    # Only groups created by this runner's start_new_session child are passed
    # here. Zombies cannot perform a late write and do not keep recovery busy.
    if not process_group_members(pgid):
        return False
    for number, grace in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        current = process_identity(pgid)
        if current is not None and (
            current != expected_identity or current.get("birth") in {"unknown", "already_exited"}
        ):
            raise GuardError("provenance_owned_group_owner_changed")
        try:
            os.killpg(pgid, number)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not process_group_members(pgid):
                return True
            time.sleep(0.05)
    raise GuardError("provenance_group_termination_unverified")


def run_guard(
    binding_path, argv, profile=None, timeout=None, cwd=None, result_path=None, cancel_file=None, invocation=None
):
    owned_jobs = []
    try:
        try:
            return _run_guard(
                binding_path, argv, profile, timeout, cwd, result_path, cancel_file, owned_jobs, invocation
            )
        finally:
            for job in reversed(owned_jobs):
                job.close()
    except processes.ProcessError as error:
        raise GuardError(str(error)) from None


def checkpoint_failure(result, result_path):
    diagnostic = dict(
        result,
        ok=False,
        state="checkpoint_violation",
        error="provenance_checkpoint_violation",
        command_exit_code=None,
        started=False,
        commands_replayed=False,
    )
    publish_result(result_path, diagnostic)
    emit(diagnostic)
    return EXIT_VIOLATION


def _run_guard(binding_path, argv, profile, timeout, cwd, result_path, cancel_file, owned_jobs, invocation):
    binding, digest = bound(binding_path)
    if invocation is not None and not re.fullmatch("[a-f0-9]{64}", invocation):
        raise GuardError("invalid_command_invocation")
    if not argv or (timeout is not None and not 0 < timeout <= 86400):
        raise GuardError("provenance_command_invalid")
    marker = cancel_path(cancel_file, Path(binding["source_root"]))
    if marker is not None and marker.exists():
        diagnostic = {
            "ok": True,
            "state": "cancelled",
            "command_exit_code": 143,
            "cancelled": True,
            "started": False,
            "commands_replayed": False,
        }
        publish_result(result_path, diagnostic)
        return 143
    previous = checkpoint_sync(binding, digest)
    if previous is not None and not previous["ok"]:
        return checkpoint_failure(previous, result_path)
    path, record = capture(binding, digest)
    proof = checkpoint_sync(binding, digest, record["entries"], create=True)
    if not proof["ok"]:
        record.update(state="violated", started=False)
        archive(path, record)
        return checkpoint_failure(proof, result_path)
    if invocation is not None:
        record["invocation"] = invocation
    if marker is not None:
        record["cancel_file"] = str(marker)
        candidates.atomic_json(path, record)
    if invocation is not None:
        publish_result(result_path, {"state": "running", "token": record["token"]})
    job = None
    if os.name == "nt":
        job = processes.WindowsJob(record["token"])
        owned_jobs.append(job)
        record["windows_job"] = job.name
        candidates.atomic_json(path, record)
    command = list(argv)
    if profile is not None:
        if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
            raise GuardError("provenance_profile_unavailable")
        command = ["/usr/bin/sandbox-exec", "-p", profile_for(profile, record), *command]
    child = None
    cancelled = None
    started = time.monotonic()
    terminating = None
    old_handlers = {}
    runtime_error = None

    def cancel(number, _frame):
        nonlocal cancelled, terminating
        cancelled = number
        terminating = terminating or time.monotonic()
        if job is not None and job.assigned:
            job.cancel()
        elif child is not None and child.poll() is None:
            if os.name == "nt":
                windows_taskkill(child)
            else:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    try:
        for number in (signal.SIGTERM, signal.SIGINT):
            old_handlers[number] = signal.signal(number, cancel)
        # A hard kill between spawn and the next journal write cannot prove
        # that no child survived. Persist that uncertainty before spawning.
        record.update(state="launching", started_at=time.time())
        candidates.atomic_json(path, record)
        if marker is not None and marker.exists():
            cancelled = signal.SIGTERM
            code = 143
            record.update(state="captured", cancelled=True, started=False)
        else:
            child = (
                job.spawn(command, cwd=cwd)
                if job is not None
                else subprocess.Popen(command, cwd=cwd, start_new_session=True)
            )
            identity = process_identity(child.pid) or {"pid": child.pid, "birth": "already_exited"}
            record.update(state="running", child=identity, started_at=time.time())
            if os.name != "nt":
                record["owned_pgid"] = child.pid
            candidates.atomic_json(path, record)
            if cancelled is not None or (marker is not None and marker.exists()):
                cancel(signal.SIGTERM, None)
        while child is not None:
            try:
                code = child.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if marker is not None and marker.exists() and cancelled is None:
                    cancel(signal.SIGTERM, None)
                if timeout is not None and time.monotonic() - started >= timeout and cancelled is None:
                    cancel(signal.SIGTERM, None)
                if terminating is not None and time.monotonic() - terminating > 2 and child.poll() is None:
                    if os.name == "nt":
                        job.cancel()
                    else:
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
        record["child_exit_code"] = code
        record["cancelled"] = cancelled is not None
    except OSError:
        if child is None:
            record["child_exit_code"] = 127
            record["start_failed"] = True
            code = 127
        else:
            # A failed child-identity journal write must not turn a live
            # command into a harmless start failure followed by archiving.
            runtime_error = "provenance_child_tracking_failed"
            record["runtime_error"] = runtime_error
            cancel(signal.SIGTERM, None)
            try:
                code = child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    job.cancel()
                else:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    code = child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    raise GuardError("provenance_child_termination_unverified") from None
            record["child_exit_code"] = code
    except processes.ProcessError as error:
        if job is None or not job.cleanup_verified:
            raise
        child = job.child
        code = child.poll()
        if code is None:
            raise GuardError("provenance_windows_suspended_cleanup_unverified") from None
        record.update(child={"pid": child.pid, "birth": "already_exited"}, child_exit_code=code)
        runtime_error = str(error)
        record["runtime_error"] = runtime_error
    finally:
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
    background = (
        job.quiesce() if job is not None else child is not None and quiesce_owned_group(child.pid, record["child"])
    )
    if background:
        record["background_descendants_terminated"] = True
        runtime_error = runtime_error or "provenance_background_descendants_terminated"
        record["runtime_error"] = runtime_error
    result = verify_record(path, record, binding)
    proof = checkpoint_sync(binding, digest, record["entries"], create=True)
    result["ok"] = result["ok"] and proof["ok"]
    for key in ("violations", "restored", "consumed"):
        result[key].extend(proof[key])
    successful = result["ok"] and runtime_error is None
    diagnostic = dict(
        result,
        ok=successful,
        state="guard_error" if runtime_error else "verified" if result["ok"] else "violation",
        token=record["token"],
        command_exit_code=code,
        cancelled=cancelled is not None,
        commands_replayed=False,
    )
    if not successful:
        diagnostic["error"] = runtime_error or "provenance_violation"
    if record.get("background_descendants_terminated"):
        diagnostic["background_descendants_terminated"] = True
    publish_result(result_path, diagnostic)
    conflicts = [item for item in result["violations"] if not item.get("restored", False)]
    record["state"] = "completed" if successful else "recovery_failed" if conflicts else "violated"
    if conflicts:
        candidates.atomic_json(path, record)
    else:
        archive(path, record)
    if not successful:
        emit(diagnostic)
        return EXIT_VIOLATION
    return 128 + cancelled if cancelled is not None else code if code >= 0 else 128 - code


def recover(binding_path):
    binding, digest = bound(binding_path)
    folder = guard_folder(binding, digest) / "pending"
    if folder.is_symlink():
        raise GuardError("provenance_private_path_linked")
    if not folder.exists():
        return {"ok": True, "state": "ready", "guards": [], "commands_replayed": False}
    proof = checkpoint_sync(binding, digest)
    fixed = checkpoint_token(digest) + ".json"
    pending, active, blockers = [], [], []
    for path in sorted(folder.glob("*.json")):
        if path.is_symlink():
            raise GuardError("provenance_journal_invalid")
        record = read_json(path, 192 * 1024 * 1024)
        if not isinstance(record, dict) or record.get("binding") != binding:
            raise GuardError("provenance_journal_binding_mismatch")
        if path.name == fixed:
            if record.get("state") != "checkpoint":
                raise GuardError("provenance_checkpoint_invalid")
            continue
        if record.get("state") in {"completed", "recovered"}:
            archive(path, record)
            continue
        if record.get("state") not in {"captured", "launching", "running", "violated", "recovery_failed"}:
            raise GuardError("provenance_journal_invalid")
        if alive(record.get("runner")):
            active.append({"state": "active", "token": record.get("token")})
            continue
        if alive(record.get("child")):
            blockers.append({"state": "orphan_child_alive", "token": record.get("token")})
            continue
        if os.name == "nt" and record.get("windows_job") is not None:
            if record["windows_job"] != processes.job_name(record["token"]):
                raise GuardError("provenance_windows_job_name_invalid")
            if not processes.job_is_quiet(record["token"]):
                blockers.append({"state": "orphan_job_alive", "token": record.get("token")})
                continue
        if os.name != "nt" and record.get("owned_pgid") is not None:
            if not isinstance(record.get("child"), dict) or record["owned_pgid"] != record["child"].get("pid"):
                raise GuardError("provenance_owned_group_invalid")
            if process_group_members(record["owned_pgid"]):
                blockers.append({"state": "orphan_group_alive", "token": record.get("token")})
                continue
        if record.get("state") == "launching":
            blockers.append({"state": "orphan_child_unknown", "token": record.get("token")})
            continue
        pending.append((path, record))
    results = [proof] if proof is not None else []
    for path, record in pending:
        result = verify_record(path, record, binding)
        # Recovery answers whether receipt delivery may continue now, not
        # whether the original command was successful or violated protection.
        current_conflicts = [item for item in result["violations"] if not item.get("restored", False)]
        record["state"] = "recovered" if not current_conflicts else "recovery_failed"
        record["original_command_result_unchanged"] = True
        if current_conflicts:
            candidates.atomic_json(path, record)
        else:
            archive(path, record)
        results.append({"token": record["token"], **result, "can_flush": not current_conflicts})
    ok = not blockers and all(item["can_flush"] for item in results)
    state = (
        blockers[0]["state"]
        if len(blockers) == 1
        else "blocked"
        if blockers
        else "recovery_failed"
        if not ok
        else "active"
        if active
        else "recovered"
        if results
        else "ready"
    )
    response = {
        "ok": ok,
        "state": state,
        "guards": results,
        "active": active,
        "blockers": blockers,
        "commands_replayed": False,
    }
    if len(blockers) == 1:
        response["token"] = blockers[0]["token"]
    elif len(active) == 1 and ok:
        response["token"] = active[0]["token"]
    return response


def completed_command(binding_path, result_path, invocation):
    """Recover only a terminal receipt from this exact guarded invocation."""
    binding, digest = bound(binding_path)
    receipt = read_json(result_path)
    token = receipt.get("token", "")
    if not isinstance(token, str) or not re.fullmatch("[a-f0-9]{32}", token):
        raise GuardError("command_outcome_unknown")
    folder = guard_folder(binding, digest)
    closed = folder / "closed" / (token + ".json")
    pending = folder / "pending" / (token + ".json")
    record = read_json(closed if closed.exists() else pending)
    if (
        not isinstance(invocation, str)
        or not re.fullmatch("[a-f0-9]{64}", invocation)
        or record.get("invocation") != invocation
        or record.get("token") != token
        or record.get("binding") != binding
        or record.get("cancel_file") != str(Path(str(result_path) + ".cancel"))
    ):
        raise GuardError("command_outcome_unknown")
    if not closed.exists():
        if alive(record.get("runner")):
            return {"pending": True, "runner_pid": record["runner"]["pid"]}
        raise GuardError("command_outcome_unknown")
    code = record.get("child_exit_code")
    if (
        record.get("state") != "completed"
        or type(code) is not int
        or code < 0
        or receipt.get("ok") is not True
        or receipt.get("state") != "verified"
        or receipt.get("cancelled") is not False
        or receipt.get("command_exit_code") != code
    ):
        raise GuardError("command_outcome_unknown")
    return {
        "exit_code": code,
        "provenance_guard": {"ok": True, "state": "verified", "token": token},
        "output_available": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true")
    action.add_argument("--recover", action="store_true")
    action.add_argument("--completed-command", type=Path)
    parser.add_argument("--invocation")
    parser.add_argument("--profile")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--cancel-file", type=Path)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.completed_command:
            print(json.dumps(completed_command(args.binding, args.completed_command, args.invocation)), flush=True)
            return 0
        if args.recover:
            result = recover(args.binding)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0 if result["ok"] else EXIT_VIOLATION
        argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        return run_guard(
            args.binding,
            argv,
            args.profile,
            args.timeout_seconds,
            result_path=args.result,
            cancel_file=args.cancel_file,
            invocation=args.invocation,
        )
    except Exception as error:
        code = str(error) if isinstance(error, (GuardError, candidates.CandidateError)) else "provenance_guard_failed"
        result = {"ok": False, "state": "guard_error", "error": code, "commands_replayed": False}
        try:
            publish_result(args.result, result)
        except Exception:
            result["result_write_failed"] = True
        if args.recover:
            print(json.dumps(result), flush=True)
        else:
            emit(result)
        return EXIT_VIOLATION


if __name__ == "__main__":
    raise SystemExit(main())
