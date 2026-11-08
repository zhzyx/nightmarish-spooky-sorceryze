"""Verify an explicitly registered logical App and its immutable sealed copy.

The existing candidate manifest/binding remains the source of provenance. This
module never changes that source, follows a logical link for writes, or signs.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import editor_native_app as native

ENTRY_TYPE = "managed_native_app_link"


class ManagedEntryError(ValueError):
    pass


def require(value, error):
    if not value:
        raise ManagedEntryError(error)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def file_hash(path):
    return native.digest(path)


def rename_exclusive(source, destination):
    """Never overwrite an entry that appeared after our identity check."""
    require(sys.platform == "darwin", "activation_managed_platform_unsupported")
    import ctypes

    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    rename = library.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(os.fsencode(source), os.fsencode(destination), 4):  # RENAME_EXCL
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def create_empty_attribute(path, name):
    """Restore an absent empty value atomically, without following links."""
    require(sys.platform == "darwin", "activation_managed_platform_unsupported")
    import ctypes

    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    create = library.setxattr
    create.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    create.restype = ctypes.c_int
    if create(os.fsencode(path), name.encode("utf-8"), None, 0, 0, 3):  # XATTR_CREATE | XATTR_NOFOLLOW
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def owned_json(path):
    path = Path(path)
    require(
        path.is_file()
        and not path.is_symlink()
        and path.resolve() == path
        and path.stat().st_uid == os.getuid()
        and path.stat().st_size <= 16 * 1024 * 1024,
        "activation_managed_record_invalid",
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "activation_managed_record_invalid")
    return value


def context(manifest_path, manifest, report):
    binding = manifest["binding"]
    for name in ("candidate", "signed_commit", "tree"):
        value = report.get(name)
        require(
            isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value), "activation_managed_acceptance_missing"
        )
    return {
        "schema_version": 2,
        "entry_type": ENTRY_TYPE,
        "source_root": binding["source_root"],
        "common_dir": binding["common_dir"],
        "binding_path": binding["binding_path"],
        "owner": binding["owner"],
        "issue": binding["issue"],
        "request_id": binding["request_id"],
        "repository": binding["repository"],
        "logical_entry": binding["initial_launch_executable"],
        "source_bundle": manifest["native_app"]["bundle_path"],
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": file_hash(manifest_path),
        "source_digest": manifest["source_digest"],
        "artifact_sha256": manifest["artifact_sha256"],
        "candidate": report["candidate"],
        "signed_commit": report["signed_commit"],
        "tree": report["tree"],
    }


def snapshot_directory(identity):
    require(sys.platform == "darwin", "activation_managed_platform_unsupported")
    root = Path(identity["source_root"])
    # native_output_dir uses the real OS user home, never HOME or a free base.
    base = native.native_output_dir(root).parent.parent / "engine-launch-payloads"
    return base / hashlib.sha256(canonical(identity)).hexdigest()


def in_snapshot_store(path, source_root):
    if sys.platform != "darwin":
        return False
    base = native.native_output_dir(source_root).parent.parent / "engine-launch-payloads"
    return Path(path).is_relative_to(base)


def private_directory(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, "activation_managed_store_invalid")
    missing = []
    for item in (path, *path.parents):
        require(not item.is_symlink() and (not item.exists() or item.is_dir()), "activation_managed_store_invalid")
        if not item.exists():
            missing.append(item)
    for item in reversed(missing):
        item.mkdir(mode=0o700)
    require(path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o022, "activation_managed_store_invalid")


def attributes(path):
    result = subprocess.run(["/usr/bin/xattr", "-s", str(path)], capture_output=True, check=True, timeout=30)
    values = {}
    for name in result.stdout.decode("utf-8").splitlines():
        encoded = subprocess.run(
            ["/usr/bin/xattr", "-s", "-p", "-x", name, str(path)], capture_output=True, check=True, timeout=30
        ).stdout
        # Plain xattr -p truncates binary values at NUL. Decode its complete
        # hexadecimal representation, including a genuine zero-length value.
        raw = bytes.fromhex(encoded.decode("ascii"))
        # Only existence/length/digest is retained; never where-from URLs.
        values[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return values


def fingerprint(app):
    result = {}
    for path in (app, *app.rglob("*")):
        info = path.lstat()
        item = {"mode": stat.S_IMODE(info.st_mode), "attrs": attributes(path)}
        if path.is_symlink():
            item.update(kind="link", target=os.readlink(path))
        elif path.is_file():
            item.update(kind="file", sha256=file_hash(path))
        elif path.is_dir():
            item.update(kind="directory")
        else:
            raise ManagedEntryError("activation_managed_payload_file_invalid")
        result[path.relative_to(app).as_posix()] = item
    return result


def copy_metadata(source, copied):
    require(source.keys() == copied.keys(), "activation_managed_copy_changed")
    differences = []
    for name, expected in source.items():
        actual = copied[name]
        require(
            {k: v for k, v in expected.items() if k != "attrs"} == {k: v for k, v in actual.items() if k != "attrs"},
            "activation_managed_copy_changed",
        )
        old = dict(expected["attrs"])
        new = dict(actual["attrs"])
        old_quarantine = old.pop("com.apple.quarantine", None)
        new_quarantine = new.pop("com.apple.quarantine", None)
        require(old == new, "activation_managed_copy_attributes_changed")
        require(old_quarantine is None or new_quarantine is not None, "activation_managed_quarantine_missing")
        if old_quarantine != new_quarantine:
            differences.append({"path": name, "source": old_quarantine, "copy": new_quarantine})
    return differences


def preserve_empty_attributes(stage, source):
    """ditto omits empty xattrs, including ad-hoc non-Mach-O CodeSignature.

    Restore only missing, proven-empty values on this new private copy. Never
    rewrite a value or quarantine, and still require exact raw equality below.
    """
    require(
        stage.is_dir() and not stage.is_symlink() and stage.resolve() == stage and stage.stat().st_uid == os.getuid(),
        "activation_managed_copy_invalid",
    )
    copied = fingerprint(stage)
    require(source.keys() == copied.keys(), "activation_managed_copy_changed")
    restored = []
    for name, expected in source.items():
        actual = copied[name]
        require(
            {k: v for k, v in expected.items() if k != "attrs"} == {k: v for k, v in actual.items() if k != "attrs"},
            "activation_managed_copy_changed",
        )
        for attribute, value in expected["attrs"].items():
            if (
                value == {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}
                and attribute not in actual["attrs"]
                and attribute != "com.apple.quarantine"
            ):
                create_empty_attribute(stage / name, attribute)
                restored.append({"path": name, "attribute": attribute, **value})
    return restored


def verify_snapshot(identity):
    folder = snapshot_directory(identity)
    require(
        folder.is_dir() and not folder.is_symlink() and folder.resolve() == folder,
        "activation_managed_snapshot_missing",
    )
    require(
        folder.stat().st_uid == os.getuid() and not folder.stat().st_mode & 0o022,
        "activation_managed_snapshot_owner_changed",
    )
    record = owned_json(folder / "context.json")
    require(record.get("identity") == identity, "activation_managed_snapshot_identity_changed")
    snapshot = folder / "source-manifest.json"
    require(
        snapshot.is_file()
        and not snapshot.is_symlink()
        and snapshot.resolve() == snapshot
        and snapshot.stat().st_uid == os.getuid(),
        "activation_managed_snapshot_identity_changed",
    )
    require(
        file_hash(snapshot) == identity["source_manifest_sha256"]
        and file_hash(identity["source_manifest"]) == identity["source_manifest_sha256"],
        "activation_managed_source_manifest_changed",
    )
    payload = folder / "Engine.app"
    require(payload.stat().st_uid == os.getuid(), "activation_managed_snapshot_owner_changed")
    manifest = owned_json(identity["source_manifest"])
    expected = native.origin_value(
        identity["source_root"], manifest["binding"], manifest["project_root"], Path(identity["source_bundle"])
    )
    native.verify_bundle(payload, expected, identity["artifact_sha256"])
    require(fingerprint(payload) == record.get("payload_fingerprint"), "activation_managed_payload_changed")
    return payload, record


def create_snapshot(manifest_path, manifest, report):
    identity = context(manifest_path, manifest, report)
    source = Path(identity["source_bundle"])
    require(
        source.parent == native.native_output_dir(identity["source_root"]), "activation_managed_source_not_native_store"
    )
    require(source.stat().st_uid == os.getuid(), "activation_managed_source_owner_changed")
    folder = snapshot_directory(identity)
    private_directory(folder.parent)
    if folder.exists() or folder.is_symlink():
        payload, record = verify_snapshot(identity)
        return identity, payload, record
    expected = native.origin_value(identity["source_root"], manifest["binding"], manifest["project_root"], source)
    before = fingerprint(source)
    with tempfile.TemporaryDirectory(prefix=".launch-snapshot-", dir=folder.parent) as temporary:
        stage = Path(temporary) / "Engine.app"
        native.copy_app(source, stage)
        restored = preserve_empty_attributes(stage, before)
        native.verify_bundle(stage, expected, identity["artifact_sha256"])
        copied = fingerprint(stage)
        differences = copy_metadata(before, copied)
        require(fingerprint(source) == before, "activation_managed_source_changed_during_copy")
        require(
            file_hash(manifest_path) == identity["source_manifest_sha256"], "activation_managed_source_manifest_changed"
        )
        # Reserve the immutable name exclusively. Existing payloads are never
        # replaced or cleaned; only this invocation's unpublished reservation.
        folder.mkdir(mode=0o700)
        reserved = folder.stat()
        complete = False
        try:
            os.replace(stage, folder / "Engine.app")
            with (folder / "source-manifest.json").open("xb") as stream:
                stream.write(Path(manifest_path).read_bytes())
            record = {
                "schema_version": 1,
                "identity": identity,
                "source_fingerprint": before,
                "payload_fingerprint": copied,
                "quarantine_differences": differences,
                "restored_empty_attributes": restored,
            }
            with (folder / "context.json").open("x", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            complete = True
        finally:
            if not complete and folder.is_dir() and not folder.is_symlink() and folder.stat().st_ino == reserved.st_ino:
                shutil.rmtree(folder)
    payload, record = verify_snapshot(identity)
    return identity, payload, record


def verify_link(app, payload, identity=None):
    app = Path(app)
    require(
        app.is_symlink()
        and app.parent.resolve() == app.parent
        and app.lstat().st_uid == os.getuid()
        and os.readlink(app) == str(payload),
        "activation_managed_link_changed",
    )
    require(
        payload.is_absolute() and payload.resolve() == payload and not payload.is_symlink(),
        "activation_managed_payload_invalid",
    )
    if identity is not None:
        verified, _ = verify_snapshot(identity)
        require(verified == payload, "activation_managed_payload_invalid")
    native.verify_signature(app)


def registered_entry(initial, common, *, expected_manifest=None, record=None):
    initial, common = Path(initial), Path(common)
    app = native.app_for_executable(initial)
    require(app is not None, "activation_managed_entry_invalid")
    path = common / "gonggong-engine-launchers" / (hashlib.sha256(str(initial).encode()).hexdigest()[:24] + ".json")
    record = owned_json(path) if record is None else record
    require(
        record.get("state") == "activated" and record.get("entry_type") == ENTRY_TYPE,
        "activation_managed_entry_unregistered",
    )
    identity = record.get("payload_context")
    require(isinstance(identity, dict), "activation_managed_record_invalid")
    mf = Path(identity.get("source_manifest", ""))
    require(expected_manifest is None or mf == Path(expected_manifest), "activation_managed_source_manifest_changed")
    manifest = owned_json(mf)
    report = {
        "candidate": record.get("source_commit"),
        "signed_commit": record.get("signed_commit"),
        "tree": record.get("tree"),
    }
    require(identity == context(mf, manifest, report), "activation_managed_record_changed")
    binding = manifest["binding"]
    require(
        identity["logical_entry"] == str(initial)
        and identity["common_dir"] == str(common)
        and record.get("logical_entry") == str(initial)
        and record.get("entry") == str(app),
        "activation_managed_entry_changed",
    )
    import editor_engine_candidate as candidates
    from editor_source_manifest import verify_source

    source = Path(identity["source_root"])
    actual_common, repository, origin = candidates.identity(source)
    require(actual_common == common and repository == binding["repository"], "activation_managed_binding_changed")
    private = owned_json(binding["binding_path"])
    require(
        private.get("state") == "prepared" and private.get("artifact_manifest") == str(mf),
        "activation_managed_binding_changed",
    )
    for key in (
        "owner",
        "issue",
        "request_id",
        "source_root",
        "common_dir",
        "repository",
        "branch",
        "base_sha",
        "initial_launch_executable",
    ):
        require(private.get(key) == binding.get(key), "activation_managed_binding_changed")
    expected = {
        "version": 1,
        "owner": binding["owner"],
        "issue": binding["issue"],
        "request_id": binding["request_id"],
        "common_dir": str(common),
        "repository": repository,
        "origin": origin,
        "source_root": str(source),
        "branch": binding["branch"],
        "base_sha": binding["base_sha"],
    }
    candidates.validate_source(source, private, expected)
    require(
        candidates.git(source, "rev-parse", identity["candidate"] + "^{tree}").stdout.strip() == identity["tree"],
        "activation_managed_acceptance_changed",
    )
    require(
        candidates.git(source, "merge-base", "--is-ancestor", identity["candidate"], "HEAD", check=False).returncode
        == 0,
        "activation_managed_acceptance_changed",
    )
    verify_source(source, mf)
    native.validate_native_app(source, manifest, mf)
    payload, _ = verify_snapshot(identity)
    require(
        record.get("canonical_payload") == str(payload) and record.get("source_bundle") == identity["source_bundle"],
        "activation_managed_payload_changed",
    )
    verify_link(app, payload)
    return record
