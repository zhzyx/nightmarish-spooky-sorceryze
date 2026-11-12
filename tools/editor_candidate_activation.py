"""Activate an accepted engine artifact after authoritative PR/main readback.

Called by writer_submit's post-acceptance readback, never by a timer. Paths and
artifact provenance come from the host's private candidate binding, not PR prose.
"""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path


class ActivationError(ValueError):
    pass


def command(arguments, *, binary=False, check=True):
    result = subprocess.run(arguments, capture_output=True, timeout=120)
    if check and result.returncode:
        raise ActivationError("activation_command_failed")
    return result if binary else result.stdout.decode("utf-8").strip()


def git(root, *args, binary=False):
    return command([os.environ.get("GONGGONG_GIT", "git"), "-C", str(root), *args], binary=binary)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise ActivationError("activation_record_invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ActivationError("activation_record_invalid")
    return value


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".activation-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def lock(path):
    if os.name == "nt":
        raise ActivationError("activation_platform_not_supported")
    import fcntl

    if path.is_symlink():
        raise ActivationError("activation_record_invalid")
    with path.open("a+b") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ActivationError("activation_busy") from None
        yield


def source_matches(root, revision, inputs):
    if not isinstance(inputs, dict) or not inputs:
        raise ActivationError("activation_source_manifest_missing")
    tree = git(root, "ls-tree", "-rz", revision, binary=True).stdout
    entries = {}
    for raw in tree.split(b"\0"):
        if raw:
            meta, name = raw.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            entries[name.decode("utf-8")] = (mode, kind, oid)
    blobs = {}
    for name, expected in inputs.items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != name
            or not isinstance(expected, dict)
        ):
            raise ActivationError("activation_source_manifest_invalid")
        entry = entries.get(name)
        if expected.get("absent") is True:
            if entry is not None:
                raise ActivationError("activation_source_not_committed")
            continue
        if entry is None or entry[1] != "blob" or entry[0] != str(expected.get("mode")):
            raise ActivationError("activation_source_not_committed")
        blobs.setdefault(entry[2], []).append((name, expected.get("sha256")))
    # A Godot tree has many thousands of files. Batch object reads into a
    # temporary stream rather than spawning one Git process per source file or
    # holding the complete source tree in memory.
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(
            [os.environ.get("GONGGONG_GIT", "git"), "-C", str(root), "cat-file", "--batch"],
            input=("\n".join(blobs) + "\n").encode(),
            stdout=output,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if result.returncode:
            raise ActivationError("activation_source_not_committed")
        output.seek(0)
        for oid, expected_files in blobs.items():
            header = output.readline().decode().split()
            if len(header) != 3 or header[:2] != [oid, "blob"]:
                raise ActivationError("activation_source_not_committed")
            remaining = int(header[2])
            value = hashlib.sha256()
            while remaining:
                block = output.read(min(1024 * 1024, remaining))
                if not block:
                    raise ActivationError("activation_source_not_committed")
                remaining -= len(block)
                value.update(block)
            if output.read(1) != b"\n":
                raise ActivationError("activation_source_not_committed")
            raw_hash = value.hexdigest()
            for name, expected_hash in expected_files:
                if raw_hash == expected_hash:
                    continue
                # Git stores normalized blobs while .gitattributes can check out
                # CRLF build inputs, even on macOS. Ask Git for that exact path's
                # checkout representation only on a raw-byte mismatch. Batch
                # --filters reports unfiltered sizes, so it cannot frame this
                # stream safely. The common case still uses one batched read.
                converted = git(root, "cat-file", "--filters", "--path=" + name, oid, binary=True).stdout
                if hashlib.sha256(converted).hexdigest() != expected_hash:
                    raise ActivationError("activation_source_not_committed")


def verified_manifest(manifest_path, report):
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = read_json(manifest_path)
    binding = manifest["binding"]
    root = Path(binding["source_root"]).resolve(strict=True)
    common = (root / git(root, "rev-parse", "--git-common-dir")).resolve()
    binding_path = Path(binding["binding_path"])
    if binding_path.parent != common / "gonggong-engine-candidates":
        raise ActivationError("activation_binding_invalid")
    trusted = read_json(binding_path)
    for key in (
        "source_root",
        "issue",
        "request_id",
        "owner",
        "branch",
        "base_sha",
        "common_dir",
        "repository",
        "initial_launch_executable",
    ):
        if binding.get(key) != trusted.get(key):
            raise ActivationError("activation_binding_changed")
    if (
        trusted.get("state") != "prepared"
        or binding.get("repository") != report.get("repository")
        or binding.get("issue") != report.get("issue")
        or binding.get("request_id") != report.get("request_id")
    ):
        raise ActivationError("activation_delivery_identity_mismatch")
    receipt = report.get("issue_receipt", {})
    if (
        report.get("pr_state") != "MERGED"
        or receipt.get("state") != "CLOSED"
        or receipt.get("reason") != "COMPLETED"
        or "status:done" not in receipt.get("labels", [])
    ):
        raise ActivationError("activation_awaiting_acceptance")
    if report.get("delivered_paths_differ") != []:
        raise ActivationError("activation_delivered_source_changed")
    candidate, main = report.get("candidate", ""), report.get("current_main", "")
    if not re.fullmatch("[a-f0-9]{40,64}", candidate) or not re.fullmatch("[a-f0-9]{40,64}", main):
        raise ActivationError("activation_main_receipt_missing")
    if command(
        [os.environ.get("GONGGONG_GIT", "git"), "-C", str(root), "merge-base", "--is-ancestor", candidate, main],
        binary=True,
        check=False,
    ).returncode:
        raise ActivationError("activation_candidate_not_in_main")
    inputs = manifest.get("source_inputs")
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(canonical).hexdigest() != manifest.get("source_digest"):
        raise ActivationError("activation_source_manifest_changed")
    source_matches(root, candidate, inputs)
    for name, expected in inputs.items():
        path = root / name
        if expected.get("absent") is True:
            if path.exists() or path.is_symlink():
                raise ActivationError("activation_source_changed_after_build")
        elif (
            path.is_symlink()
            or not path.is_file()
            or digest(path) != expected.get("sha256")
            or ("100755" if path.stat().st_mode & 0o111 else "100644") != str(expected.get("mode"))
        ):
            raise ActivationError("activation_source_changed_after_build")
    artifact = Path(manifest["executable"])
    if not artifact.is_absolute() or artifact.is_symlink() or digest(artifact) != manifest.get("artifact_sha256"):
        raise ActivationError("activation_artifact_changed")
    from package_tianshu_ui import verify_candidate_package

    try:
        verify_candidate_package(manifest)
    except ValueError as error:
        raise ActivationError(str(error)) from None
    if not os.access(artifact, os.X_OK):
        raise ActivationError("activation_artifact_not_executable")
    if "native_app" in manifest:
        from editor_native_app import validate_native_app

        try:
            validate_native_app(root, manifest, manifest_path)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            raise ActivationError("activation_native_app_invalid: " + str(error)) from None
    project = Path(manifest["project_root"])
    if not project.is_absolute() or not (project / "project.godot").is_file():
        raise ActivationError("activation_project_missing")
    return manifest, common, trusted


def launcher_text(executable, project):
    target, project = shlex.quote(str(executable)), shlex.quote(str(project))
    return (
        "#!/bin/sh\n# GongGong verified engine launcher; see private activation receipt.\n"
        'if [ "$#" -eq 0 ]; then\n  exec ' + target + " --editor --path " + project + "\nfi\n"
        "exec " + target + ' "$@"\n'
    )


def install_app(manifest, journal_path, prior=None, *, entry_type=None, manifest_path=None, report=None):
    initial = Path(manifest["binding"]["initial_launch_executable"])
    if (
        sys.platform != "darwin"
        or initial.parent.name != "MacOS"
        or initial.parent.parent.name != "Contents"
        or initial.parent.parent.parent.suffix != ".app"
    ):
        raise ActivationError("activation_original_entry_not_managed_app")
    app = initial.parent.parent.parent
    if "native_app" in manifest:
        if entry_type == "native_app_copy" and prior and prior.get("entry_type") == "managed_native_app_link":
            raise ActivationError("activation_entry_type_changed")
        if entry_type == "managed_native_app_link" or (prior and prior.get("entry_type") == "managed_native_app_link"):
            return install_managed_native_link(manifest, manifest_path, report, app, journal_path, prior)
        if entry_type not in (None, "native_app_copy"):
            raise ActivationError("activation_entry_type_invalid")
        if app.is_symlink() or initial.is_symlink():
            raise ActivationError("activation_original_entry_invalid")
        return install_native_app(manifest, app, journal_path, prior)
    if entry_type not in (None, "native_app_copy") or app.is_symlink() or initial.is_symlink():
        raise ActivationError("activation_original_entry_invalid")
    wanted = launcher_text(manifest["executable"], manifest["project_root"])
    if prior and prior.get("state") == "activated" and initial.is_file() and initial.read_bytes() == wanted.encode():
        command(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
        return dict(prior, state="activated", reused=True)
    # Recover an interrupted directory swap before attempting another activation.
    if prior and prior.get("state") in ("prepared", "old_saved"):
        backup, stage = Path(prior["backup"]), Path(prior["stage"])
        if (
            backup.parent != app.parent
            or stage.parent != app.parent
            or not backup.name.startswith(app.stem + "-previous-")
            or not stage.name.startswith("." + app.stem + "-activate-")
        ):
            raise ActivationError("activation_recovery_record_invalid")
        if not app.exists() and backup.exists():
            os.replace(backup, app)
        elif (
            prior.get("state") == "old_saved"
            and initial.is_file()
            and initial.read_bytes() == wanted.encode()
            and backup.exists()
        ):
            command(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
            result = dict(prior, state="activated", reused=True)
            atomic_json(journal_path, result)
            return result
        if stage.exists():
            shutil.rmtree(stage)
    if not initial.is_file():
        raise ActivationError("activation_original_entry_missing")
    token = uuid.uuid4().hex
    stage = app.with_name("." + app.stem + "-activate-" + token + ".app")
    backup = app.with_name(app.stem + "-previous-" + token + ".app")
    state = {
        "state": "prepared",
        "entry": str(app),
        "stage": str(stage),
        "backup": str(backup),
        "artifact_sha256": manifest["artifact_sha256"],
        "executable": manifest["executable"],
    }
    try:
        shutil.copytree(app, stage, symlinks=True)
        replacement = stage / initial.relative_to(app)
        replacement.write_text(wanted)
        replacement.chmod(0o755)
        # Sign and verify our owned local bundle BEFORE replacing the working entry.
        command(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(stage)])
        command(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(stage)])
        atomic_json(journal_path, state)
        os.replace(app, backup)
        state["state"] = "old_saved"
        atomic_json(journal_path, state)
        os.replace(stage, app)
        state["state"] = "activated"
        atomic_json(journal_path, state)
        return state
    except Exception:
        if not app.exists() and backup.exists():
            os.replace(backup, app)
        if stage.exists():
            shutil.rmtree(stage)
        raise


def install_native_app(manifest, app, journal_path, prior=None):
    """Swap a complete signed candidate; never write or re-sign its contents."""
    from editor_native_app import EXECUTABLE_RELATIVE, copy_app, origin_value, verify_bundle

    source = Path(manifest["native_app"]["bundle_path"])
    expected = origin_value(manifest["binding"]["source_root"], manifest["binding"], manifest["project_root"], source)

    def verified(target):
        try:
            verify_bundle(target, expected, manifest["artifact_sha256"])
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise ActivationError("activation_native_app_invalid: " + str(error)) from None

    initial = app / EXECUTABLE_RELATIVE
    if Path(manifest["binding"]["initial_launch_executable"]) != initial or source == app:
        raise ActivationError("activation_original_entry_invalid")
    if (
        prior
        and prior.get("state") == "activated"
        and initial.is_file()
        and digest(initial) == manifest["artifact_sha256"]
    ):
        verified(app)
        return dict(prior, state="activated", reused=True)
    if prior and prior.get("state") in ("prepared", "old_saved"):
        backup, stage = Path(prior["backup"]), Path(prior["stage"])
        if (
            backup.parent != app.parent
            or stage.parent != app.parent
            or not backup.name.startswith(app.stem + "-previous-")
            or not stage.name.startswith("." + app.stem + "-activate-")
        ):
            raise ActivationError("activation_recovery_record_invalid")
        if not app.exists() and backup.exists():
            os.replace(backup, app)
        elif (
            prior.get("state") == "old_saved"
            and initial.is_file()
            and digest(initial) == manifest["artifact_sha256"]
            and backup.exists()
        ):
            verified(app)
            result = dict(prior, state="activated", reused=True)
            atomic_json(journal_path, result)
            return result
        if stage.exists():
            shutil.rmtree(stage)
    if not initial.is_file():
        raise ActivationError("activation_original_entry_missing")
    token = uuid.uuid4().hex
    stage = app.with_name("." + app.stem + "-activate-" + token + ".app")
    backup = app.with_name(app.stem + "-previous-" + token + ".app")
    state = {
        "state": "prepared",
        "entry": str(app),
        "stage": str(stage),
        "backup": str(backup),
        "artifact_sha256": manifest["artifact_sha256"],
        "executable": manifest["executable"],
    }
    try:
        copy_app(source, stage)
        verified(stage)
        atomic_json(journal_path, state)
        os.replace(app, backup)
        state["state"] = "old_saved"
        atomic_json(journal_path, state)
        os.replace(stage, app)
        state["state"] = "activated"
        atomic_json(journal_path, state)
        return state
    except Exception:
        if not app.exists() and backup.exists():
            os.replace(backup, app)
        if stage.exists():
            shutil.rmtree(stage)
        raise


def install_managed_native_link(manifest, manifest_path, report, app, journal_path, prior=None):
    import editor_managed_native_entry as managed
    from editor_native_app import EXECUTABLE_RELATIVE

    initial = app / EXECUTABLE_RELATIVE
    if str(initial) != manifest["binding"]["initial_launch_executable"] or app.parent.resolve() != app.parent:
        raise ActivationError("activation_original_entry_invalid")

    def identity(path):
        info = path.lstat()
        return [info.st_dev, info.st_ino, info.st_uid]

    def same(path, expected):
        return (path.exists() or path.is_symlink()) and identity(path) == expected

    def remove_new_link(path, expected):
        if path.is_symlink() and same(path, expected):
            path.unlink()

    try:
        if prior and prior.get("state") in ("prepared", "old_saved"):
            if prior.get("entry_type") != managed.ENTRY_TYPE:
                raise ActivationError("activation_previous_copy_recovery_required")
            backup, stage = Path(prior["backup"]), Path(prior["stage"])
            if (
                backup.parent != app.parent
                or stage.parent != app.parent
                or not backup.name.startswith(app.stem + "-previous-")
                or not stage.name.startswith("." + app.stem + "-activate-")
            ):
                raise ActivationError("activation_recovery_record_invalid")
            payload = Path(prior["canonical_payload"])
            if prior.get("payload_context") != managed.context(manifest_path, manifest, report):
                raise ActivationError("activation_recovery_context_changed")
            if same(app, prior.get("new_link_identity")):
                managed.verify_link(app, payload, prior["payload_context"])
                result = dict(prior, state="activated", reused=True)
                atomic_json(journal_path, result)
                return result
            if not (app.exists() or app.is_symlink()) and same(backup, prior.get("old_entry_identity")):
                managed.rename_exclusive(backup, app)
            if not same(app, prior.get("old_entry_identity")):
                raise ActivationError("activation_recovery_entry_changed")
            remove_new_link(stage, prior.get("new_link_identity"))
            prior = prior.get("previous")
        if app.is_symlink():
            old = managed.registered_entry(initial, Path(manifest["binding"]["common_dir"]), record=prior)
        else:
            if prior and prior.get("entry_type") == managed.ENTRY_TYPE:
                raise ActivationError("activation_managed_entry_changed")
            old = prior
            if not app.is_dir() or app.lstat().st_uid != os.getuid() or initial.is_symlink() or not initial.is_file():
                raise ActivationError("activation_original_entry_invalid")
        accepted, payload, snapshot = managed.create_snapshot(manifest_path, manifest, report)
        if old and old.get("entry_type") == managed.ENTRY_TYPE and old.get("payload_context") == accepted:
            managed.verify_link(app, payload, accepted)
            return dict(old, state="activated", reused=True)
        token = uuid.uuid4().hex
        stage = app.with_name("." + app.stem + "-activate-" + token + ".app")
        backup = app.with_name(app.stem + "-previous-" + token + ".app")
        os.symlink(str(payload), stage, target_is_directory=True)
        link_identity = identity(stage)
        old_identity = identity(app)
        state = {
            "state": "prepared",
            "entry_type": managed.ENTRY_TYPE,
            "entry": str(app),
            "logical_entry": str(initial),
            "canonical_payload": str(payload),
            "payload_executable": str(payload / EXECUTABLE_RELATIVE),
            "source_bundle": accepted["source_bundle"],
            "source_manifest": accepted["source_manifest"],
            "source_manifest_sha256": accepted["source_manifest_sha256"],
            "source_digest": accepted["source_digest"],
            "payload_context": accepted,
            "quarantine_differences": snapshot["quarantine_differences"],
            "restored_empty_attributes": snapshot.get("restored_empty_attributes", []),
            "artifact_sha256": manifest["artifact_sha256"],
            "executable": manifest["executable"],
            "stage": str(stage),
            "backup": str(backup),
            "new_link_identity": link_identity,
            "old_entry_identity": old_identity,
            "previous": {k: v for k, v in old.items() if k != "previous"} if old else None,
            "source_commit": report["candidate"],
            "signed_commit": report["signed_commit"],
            "tree": report["tree"],
        }
        try:
            managed.verify_link(stage, payload, accepted)
            atomic_json(journal_path, state)
            if not same(app, old_identity):
                raise ActivationError("activation_original_entry_changed")
            managed.rename_exclusive(app, backup)
            if not same(backup, old_identity):
                # Preserve an entry swapped into the source between our check
                # and rename; restore only into an unoccupied logical name.
                if not (app.exists() or app.is_symlink()):
                    managed.rename_exclusive(backup, app)
                raise ActivationError("activation_original_entry_changed")
            state["state"] = "old_saved"
            atomic_json(journal_path, state)
            managed.rename_exclusive(stage, app)
            if not same(app, link_identity):
                raise ActivationError("activation_managed_entry_changed")
            managed.verify_link(app, payload, accepted)
            state["state"] = "activated"
            atomic_json(journal_path, state)
            return state
        except Exception:
            if same(app, link_identity):
                managed.rename_exclusive(app, stage)
            if not (app.exists() or app.is_symlink()) and same(backup, old_identity):
                managed.rename_exclusive(backup, app)
            remove_new_link(stage, link_identity)
            raise
    except managed.ManagedEntryError as error:
        raise ActivationError(str(error)) from None


def activate(manifest_path, report, entry_type=None):
    manifest, common, binding = verified_manifest(manifest_path, report)
    folder = common / "gonggong-engine-launchers"
    if folder.is_symlink():
        raise ActivationError("activation_record_invalid")
    folder.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(binding["initial_launch_executable"].encode()).hexdigest()[:24]
    journal_path = folder / (key + ".json")
    with lock(folder / (key + ".lock")):
        prior = read_json(journal_path) if journal_path.exists() else None
        result = install_app(
            manifest, journal_path, prior, entry_type=entry_type, manifest_path=manifest_path, report=report
        )
        result.update(
            activation_mode="accepted_candidate",
            main_commit=report["current_main"],
            source_commit=report["candidate"],
            signed_commit=report.get("signed_commit"),
            tree=report.get("tree"),
            main_advanced=report["current_main"] != report["candidate"],
            version_description="Startup is pinned to the accepted candidate contained in main; later main commits are not claimed to be in this artifact.",
            repository=report["repository"],
            issue=report["issue"],
            request_id=report["request_id"],
        )
        atomic_json(journal_path, result)
    return dict(ok=True, **result)


def after_delivery(repo, report, entry_type=None):
    """Only pass reports returned by writer_submit.inspect_pr's real readback."""
    if report.get("pr_state") != "MERGED":
        return {"state": "awaiting_main"}
    root = Path(repo).resolve()
    common = (root / git(root, "rev-parse", "--git-common-dir")).resolve()
    matches = []
    for path in (common / "gonggong-engine-candidates").glob("*.json"):
        binding = read_json(path)
        if (
            binding.get("issue") == report.get("issue")
            and binding.get("request_id") == report.get("request_id")
            and binding.get("repository") == report.get("repository")
            and binding.get("artifact_manifest")
        ):
            matches.append(binding["artifact_manifest"])
    if not matches:
        return {"state": "not_applicable"}
    if len(matches) != 1:
        return {"state": "pending", "error": "activation_candidate_ambiguous"}
    try:
        return activate(matches[0], report, entry_type=entry_type)
    except (ActivationError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Never let a secondary activation error turn a confirmed merge into an unknown merge.
        return {"state": "pending", "error": str(error) if isinstance(error, ActivationError) else "activation_failed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--entry-type", choices=("native_app_copy", "managed_native_app_link"))
    args = parser.parse_args()
    try:
        manifest = read_json(args.manifest)
        root = Path(manifest["binding"]["source_root"])
        repository = manifest["binding"]["repository"]
        adapter = Path(__file__).resolve().parents[1] / "customizations/components/issue-workorders"
        sys.path.insert(0, str(adapter))
        import writer_submit

        # GitHub associates commits with their PRs; no user-selected path/branch/PR is needed.
        head = git(root, "rev-parse", "HEAD")
        prs = json.loads(writer_submit.work_items.gh("api", f"repos/{repository}/commits/{head}/pulls"))
        accepted = [p for p in prs if p.get("merged_at") and p.get("base", {}).get("ref") == "main"]
        if len(accepted) != 1:
            raise ActivationError("activation_main_receipt_missing")
        result = activate(
            args.manifest, writer_submit.inspect_pr(root, repository, accepted[0]["number"]), entry_type=args.entry_type
        )
    except (ActivationError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {
            "ok": False,
            "state": "pending",
            "error": str(error) if isinstance(error, ActivationError) else "activation_failed",
        }
    atomic_json(args.out, result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
