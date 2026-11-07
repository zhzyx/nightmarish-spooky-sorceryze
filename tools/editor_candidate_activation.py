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
        blobs.setdefault(entry[2], set()).add(expected.get("sha256"))
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
        for oid, expected_hashes in blobs.items():
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
            if output.read(1) != b"\n" or expected_hashes != {value.hexdigest()}:
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
    if not os.access(artifact, os.X_OK):
        raise ActivationError("activation_artifact_not_executable")
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


def install_app(manifest, journal_path, prior=None):
    initial = Path(manifest["binding"]["initial_launch_executable"])
    if (
        sys.platform != "darwin"
        or initial.parent.name != "MacOS"
        or initial.parent.parent.name != "Contents"
        or initial.parent.parent.parent.suffix != ".app"
    ):
        raise ActivationError("activation_original_entry_not_managed_app")
    app = initial.parent.parent.parent
    if app.is_symlink() or initial.is_symlink():
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


def activate(manifest_path, report):
    manifest, common, binding = verified_manifest(manifest_path, report)
    folder = common / "gonggong-engine-launchers"
    if folder.is_symlink():
        raise ActivationError("activation_record_invalid")
    folder.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(binding["initial_launch_executable"].encode()).hexdigest()[:24]
    journal_path = folder / (key + ".json")
    with lock(folder / (key + ".lock")):
        prior = read_json(journal_path) if journal_path.exists() else None
        result = install_app(manifest, journal_path, prior)
        result.update(
            activation_mode="accepted_candidate",
            main_commit=report["current_main"],
            source_commit=report["candidate"],
            main_advanced=report["current_main"] != report["candidate"],
            version_description="Startup is pinned to the accepted candidate contained in main; later main commits are not claimed to be in this artifact.",
            repository=report["repository"],
            issue=report["issue"],
            request_id=report["request_id"],
        )
        atomic_json(journal_path, result)
    return dict(ok=True, **result)


def after_delivery(repo, report):
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
        return activate(matches[0], report)
    except (ActivationError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Never let a secondary activation error turn a confirmed merge into an unknown merge.
        return {"state": "pending", "error": str(error) if isinstance(error, ActivationError) else "activation_failed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
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
        prs = json.loads(
            command([os.environ.get("GONGGONG_GH", "gh"), "api", f"repos/{repository}/commits/{head}/pulls"])
        )
        accepted = [p for p in prs if p.get("merged_at") and p.get("base", {}).get("ref") == "main"]
        if len(accepted) != 1:
            raise ActivationError("activation_main_receipt_missing")
        result = activate(args.manifest, writer_submit.inspect_pr(root, repository, accepted[0]["number"]))
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
