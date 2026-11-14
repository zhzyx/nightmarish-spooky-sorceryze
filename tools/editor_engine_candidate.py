"""Create or validate one host-owned, Issue-bound engine worktree.

The editor supplies identity, never a model-selected directory or branch. Private
bindings live in the Git common directory and are not delivery evidence.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


class CandidateError(ValueError):
    pass


def git(root, *arguments, check=True, raw=False, env=None):
    try:
        result = subprocess.run(
            [os.environ.get("GONGGONG_GIT", "git"), "-C", str(root), *arguments],
            capture_output=True,
            text=not raw,
            encoding=None if raw else "utf-8",
            timeout=120,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise CandidateError("candidate_git_unavailable") from None
    if check and result.returncode:
        raise CandidateError("candidate_git_failed")
    return result


def registered_worktrees(workspace):
    # -z disables Git's C-style path quoting and keeps embedded newlines in a
    # single field. Let the platform Path implementation handle Git's slash
    # spelling and Windows case-insensitive equality after canonicalization.
    output = git(workspace, "worktree", "list", "--porcelain", "-z", raw=True).stdout
    roots = []
    for field in output.split(b"\0"):
        if not field.startswith(b"worktree "):
            continue
        try:
            path = Path(os.fsdecode(field.removeprefix(b"worktree ")))
            if not path.is_absolute():
                raise ValueError
            roots.append(path.resolve())
        except (OSError, ValueError):
            raise CandidateError("candidate_worktree_registry_invalid") from None
    return roots


def verify_work_order(workspace, issue, request_id):
    """Load the trusted installed gate, not a candidate's mutable gate."""
    directory = Path(__file__).resolve().parents[1] / "customizations/components/issue-workorders"
    spec = importlib.util.spec_from_file_location("engine_candidate_issue_gate", directory / "issue_gate.py")
    if spec is None or spec.loader is None:
        raise CandidateError("candidate_gate_unavailable")
    gate = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(directory))
    try:
        spec.loader.exec_module(gate)
        config = json.loads((workspace / "work-items.json").read_text(encoding="utf-8"))
        gate.intake(workspace, issue, request_id, config["tenant_id"])
    except Exception:
        raise CandidateError("candidate_issue_not_verified") from None
    finally:
        sys.path.remove(str(directory))


def identity(workspace):
    if workspace.is_symlink() or workspace.resolve() != workspace:
        raise CandidateError("candidate_workspace_invalid")
    if Path(git(workspace, "rev-parse", "--show-toplevel").stdout.strip()).resolve() != workspace:
        raise CandidateError("candidate_workspace_invalid")
    raw_common = git(workspace, "rev-parse", "--git-common-dir").stdout.strip()
    common = (workspace / raw_common).resolve()
    try:
        settings = json.loads((workspace / "work-items.json").read_text(encoding="utf-8"))
        repository = settings["repository"]
    except (OSError, ValueError, KeyError):
        raise CandidateError("candidate_repository_invalid") from None
    if not isinstance(repository, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise CandidateError("candidate_repository_invalid")
    origin = git(workspace, "config", "--get", "remote.origin.url").stdout.strip()
    allowed = {
        f"https://github.com/{repository}",
        f"https://github.com/{repository}.git",
        f"git@github.com:{repository}",
        f"git@github.com:{repository}.git",
        f"ssh://git@github.com/{repository}",
        f"ssh://git@github.com/{repository}.git",
    }
    if origin.lower() not in {value.lower() for value in allowed}:
        raise CandidateError("candidate_origin_mismatch")
    return common, repository, origin


def atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix=".candidate-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def binding_lock(path, *, timeout=0.0):
    if path.is_symlink():
        raise CandidateError("candidate_binding_invalid")
    deadline = time.monotonic() + max(0.0, float(timeout))
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise CandidateError("candidate_binding_busy") from None
                    time.sleep(0.025)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise CandidateError("candidate_binding_busy") from None
                    time.sleep(0.025)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def validate_source(workspace, binding, expected, require_clean=False):
    for name, value in expected.items():
        if binding.get(name) != value:
            raise CandidateError("candidate_binding_mismatch")
    target = Path(expected["source_root"])
    if not target.is_dir() or target.is_symlink() or target.resolve() != target:
        raise CandidateError("candidate_source_missing")
    common, repository, origin = identity(target)
    if str(common) != expected["common_dir"] or repository != expected["repository"] or origin != expected["origin"]:
        raise CandidateError("candidate_repository_mismatch")
    branch = git(target, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode or branch.stdout.strip() != expected["branch"]:
        raise CandidateError("candidate_branch_mismatch")
    base = binding.get("base_sha")
    if not isinstance(base, str) or not re.fullmatch(r"[a-f0-9]{40,64}", base):
        raise CandidateError("candidate_base_invalid")
    if git(target, "merge-base", "--is-ancestor", base, "HEAD", check=False).returncode:
        raise CandidateError("candidate_base_changed")
    if not (target / "SConstruct").is_file() or not (target / "tools/editor_self_build.py").is_file():
        raise CandidateError("candidate_engine_source_missing")
    if require_clean and git(target, "status", "--porcelain", "--untracked-files=all").stdout:
        raise CandidateError("candidate_initial_tree_dirty")
    # A repository can keep stale .git metadata after worktree removal; require registration.
    if target not in registered_worktrees(workspace):
        raise CandidateError("candidate_worktree_unregistered")


def file_digest(path):
    if path.is_symlink():
        raise CandidateError("candidate_provenance_linked")
    if not path.exists():
        return None
    if not path.is_file():
        raise CandidateError("candidate_provenance_conflict")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_destination(target, name):
    destination = target / name
    for parent in (destination, *destination.parents):
        if parent == target:
            break
        if parent.is_symlink():
            raise CandidateError("candidate_provenance_linked")
    return destination


def requirement_migration_plan(workspace, target, request_id):
    """Freeze private source bytes before the first candidate file is changed."""
    settings = json.loads((workspace / "work-items.json").read_text(encoding="utf-8"))
    tenant = settings.get("tenant_id", "")
    if not isinstance(tenant, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", tenant):
        raise CandidateError("candidate_provenance_identity_mismatch")
    relative = [Path("design-docs") / (request_id + ".md")]
    event_root = workspace / "gonggong-diting-data/events" / tenant / request_id
    if event_root.is_symlink():
        raise CandidateError("candidate_provenance_linked")
    if event_root.is_dir():
        relative += sorted(p.relative_to(workspace) for p in event_root.glob("*.json") if p.is_file())
    files = []
    for name in relative:
        source = checked_destination(workspace, name)
        if not source.exists():
            continue
        data = source.read_bytes()
        if name.suffix == ".json":
            value = json.loads(data)
            if not isinstance(value, dict) or value.get("request_id") != request_id or value.get("tenant_id") != tenant:
                raise CandidateError("candidate_provenance_identity_mismatch")
        destination = checked_destination(target, name)
        files.append({
            "path": name.as_posix(),
            "initial_sha256": file_digest(destination),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_base64": base64.b64encode(data).decode("ascii"),
        })
    return {"version": 1, "tenant_id": tenant, "request_id": request_id, "files": files}


def checked_migration_plan(binding):
    plan = binding.get("migration_plan")
    if not isinstance(plan, dict) or plan.get("version") != 1 or plan.get("request_id") != binding["request_id"]:
        raise CandidateError("candidate_migration_plan_invalid")
    tenant = plan.get("tenant_id")
    if not isinstance(tenant, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", tenant):
        raise CandidateError("candidate_migration_plan_invalid")
    files = plan.get("files")
    if not isinstance(files, list):
        raise CandidateError("candidate_migration_plan_invalid")
    result = {}
    doc = "design-docs/" + binding["request_id"] + ".md"
    events = Path("gonggong-diting-data/events") / tenant / binding["request_id"]
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise CandidateError("candidate_migration_plan_invalid")
        name = Path(item["path"])
        if name.is_absolute() or ".." in name.parts or name.as_posix() != item["path"] or item["path"] in result:
            raise CandidateError("candidate_migration_plan_invalid")
        if item["path"] != doc and not (name.parent == events and name.suffix == ".json"):
            raise CandidateError("candidate_migration_plan_invalid")
        initial = item.get("initial_sha256")
        if initial is not None and (not isinstance(initial, str) or not re.fullmatch(r"[a-f0-9]{64}", initial)):
            raise CandidateError("candidate_migration_plan_invalid")
        try:
            content = base64.b64decode(item["content_base64"], validate=True)
        except (KeyError, TypeError, ValueError):
            raise CandidateError("candidate_migration_plan_invalid") from None
        if hashlib.sha256(content).hexdigest() != item.get("sha256"):
            raise CandidateError("candidate_migration_plan_invalid")
        if name.suffix == ".json":
            try:
                value = json.loads(content)
            except (ValueError, UnicodeError):
                raise CandidateError("candidate_migration_plan_invalid") from None
            if (
                not isinstance(value, dict)
                or value.get("request_id") != binding["request_id"]
                or value.get("tenant_id") != tenant
            ):
                raise CandidateError("candidate_provenance_identity_mismatch")
        result[item["path"]] = (item, content)
    return result


def validate_migration_tree(target, binding, plan):
    # The migrator never stages or commits. These changes cannot be its partial work.
    if git(target, "rev-parse", "HEAD").stdout.strip() != binding["base_sha"]:
        raise CandidateError("candidate_initial_tree_dirty")
    if git(target, "diff", "--cached", "--quiet", check=False).returncode:
        raise CandidateError("candidate_initial_tree_dirty")
    dirty = set()
    for arguments in (
        ("diff", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
        ("ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
    ):
        dirty.update(name for name in git(target, *arguments).stdout.split("\0") if name)
    if dirty - plan.keys():
        raise CandidateError("candidate_initial_tree_dirty")
    for name, (item, _) in plan.items():
        current = file_digest(checked_destination(target, Path(name)))
        if current not in (item["initial_sha256"], item["sha256"]):
            raise CandidateError("candidate_initial_tree_dirty")


def atomic_migration_file(target, destination, content):
    # A sibling temporary file stays outside the worktree even if the process is
    # killed before rename. Its filesystem matches the candidate's directory.
    descriptor, temporary = tempfile.mkstemp(prefix=".gonggong-provenance-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def migrate_requirement(target, binding):
    """Resume the exact persisted plan; prepared candidates never call this."""
    plan = checked_migration_plan(binding)
    validate_migration_tree(target, binding, plan)
    for name, (item, content) in plan.items():
        destination = checked_destination(target, Path(name))
        current = file_digest(destination)
        if current == item["sha256"]:
            continue
        if current != item["initial_sha256"]:
            raise CandidateError("candidate_initial_tree_dirty")
        atomic_migration_file(target, destination, content)
    validate_migration_tree(target, binding, plan)
    return {name: item["sha256"] for name, (item, _) in plan.items()}


def protected_roots(workspace, target):
    return [str(root) for root in registered_worktrees(workspace) if root != target]


def finish_preparation(workspace, target, binding, binding_path):
    if "migration_plan" not in binding:
        # A pre-plan interruption is resumable only while the fresh tree is clean.
        if git(target, "status", "--porcelain", "--untracked-files=all").stdout:
            raise CandidateError("candidate_initial_tree_dirty")
        source = Path(binding.get("migration_source", str(workspace)))
        if source == target and "migration_source" not in binding:
            raise CandidateError("candidate_migration_source_missing")
        binding["migration_plan"] = requirement_migration_plan(source, target, binding["request_id"])
        binding["protected_roots"] = protected_roots(workspace, target)
        atomic_json(binding_path, binding)
    binding["provenance"] = migrate_requirement(target, binding)
    binding["protected_roots"] = sorted(
        set(binding.get("protected_roots", [])) | set(protected_roots(workspace, target))
    )
    binding["state"] = "prepared"
    atomic_json(binding_path, binding)


def candidate_digest(common, repository, issue, request_id, owner, actor_login=None):
    parts = [str(common), repository, issue, request_id, owner]
    if actor_login:
        parts.append(str(actor_login).lower())
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()[:24]


def inherited_launch(workspace, common, repository, origin, folder, actual_launch):
    """Follow only a private binding tied to this source or this exact artifact."""
    import editor_managed_native_entry as managed
    from editor_native_app import (
        app_for_executable,
        native_output_dir,
        read_locator,
        validate_native_app,
        verify_bundle,
    )

    actual_locator = None
    if app_for_executable(actual_launch):
        try:
            actual_locator = read_locator(actual_launch)
        except FileNotFoundError:
            pass  # Existing managed Apps predate the native resource locator.
        except (OSError, ValueError, TypeError):
            raise CandidateError("candidate_inherited_artifact_invalid") from None
    located_manifest = actual_locator.get("candidate_manifest") if actual_locator else None
    proven = {}
    for path in sorted(folder.glob("*.json")):
        if path.is_symlink() or not re.fullmatch(r"[a-f0-9]{24}\.json", path.name):
            continue
        if hasattr(os, "geteuid") and path.stat().st_uid != os.geteuid():
            continue
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            manifest_path = Path(previous["artifact_manifest"])
            source = Path(previous["source_root"])
        except (OSError, ValueError, TypeError, KeyError):
            # An unrelated unfinished candidate is not evidence of a launch lineage.
            continue
        associated = (
            manifest_path == Path(str(actual_launch) + ".candidate.json") or str(manifest_path) == located_manifest
        )
        if source != workspace and not associated:
            continue
        if (
            not source.is_absolute()
            or not source.is_dir()
            or source.resolve() != source
            or (
                manifest_path.parent != source / "bin"
                and (sys.platform != "darwin" or manifest_path.parent != native_output_dir(source))
            )
            or manifest_path.is_symlink()
            or manifest_path.resolve() != manifest_path
        ):
            raise CandidateError("candidate_inherited_artifact_invalid")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            executable = Path(manifest["executable"])
        except (OSError, ValueError, TypeError, KeyError):
            if source == workspace or associated:
                raise CandidateError("candidate_inherited_artifact_invalid") from None
            continue
        native = "native_app" in manifest
        if not native and manifest_path.parent != source / "bin":
            raise CandidateError("candidate_inherited_artifact_invalid")
        installed_native = (
            native
            and str(manifest_path) == located_manifest
            and actual_launch == Path(previous.get("initial_launch_executable", ""))
        )
        managed_record = None
        if native and str(manifest_path) == located_manifest:
            initial = Path(previous.get("initial_launch_executable", ""))
            initial_app = app_for_executable(initial)
            if (initial_app and initial_app.is_symlink()) or managed.in_snapshot_store(actual_launch, source):
                try:
                    managed_record = managed.registered_entry(initial, common, expected_manifest=manifest_path)
                    payload_executable = Path(managed_record["payload_executable"])
                    if actual_launch != payload_executable:
                        raise ValueError("candidate_managed_executable_changed")
                except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
                    raise CandidateError("candidate_inherited_artifact_invalid") from None
                installed_native = True
        if source != workspace and executable != actual_launch and not installed_native:
            continue
        if (
            previous.get("state") != "prepared"
            or previous.get("common_dir") != str(common)
            or previous.get("repository") != repository
            or previous.get("origin") != origin
        ):
            raise CandidateError("candidate_inherited_binding_invalid")
        old_issue, old_request, old_owner = previous.get("issue"), previous.get("request_id"), previous.get("owner")
        old_actor = previous.get("actor_login")
        if (
            type(old_issue) is not int
            or old_issue < 1
            or not isinstance(old_request, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", old_request)
            or not isinstance(old_owner, str)
            or not old_owner
            or (
                old_actor is not None
                and (not isinstance(old_actor, str) or not re.fullmatch(r"[A-Za-z0-9-]+", old_actor))
            )
        ):
            raise CandidateError("candidate_inherited_binding_invalid")
        digest = candidate_digest(common, repository, old_issue, old_request, old_owner, old_actor)
        if path.name != digest + ".json" or source.name != "godot-candidate-" + digest:
            raise CandidateError("candidate_inherited_binding_invalid")
        expected = {
            "version": 1,
            "owner": old_owner,
            "issue": old_issue,
            "request_id": old_request,
            "common_dir": str(common),
            "repository": repository,
            "origin": origin,
            "source_root": str(source),
            "branch": "codex/engine-candidate/" + old_request + "-" + digest,
        }
        if old_actor:
            expected["actor_login"] = old_actor.lower()
        validate_source(workspace, previous, expected)
        if (
            manifest_path.is_symlink()
            or manifest_path.resolve() != manifest_path
            or not executable.is_file()
            or executable.is_symlink()
            or executable.resolve() != executable
            or (not native and executable.parent != source / "bin")
            or (not native and manifest_path != Path(str(executable) + ".candidate.json"))
        ):
            raise CandidateError("candidate_inherited_artifact_invalid")
        built_binding = manifest.get("binding")
        if not isinstance(built_binding, dict) or manifest.get("schema_version") != 1:
            raise CandidateError("candidate_inherited_artifact_invalid")
        for name in (
            "owner",
            "issue",
            "request_id",
            "common_dir",
            "repository",
            "source_root",
            "branch",
            "base_sha",
            "initial_launch_executable",
        ):
            if built_binding.get(name) != previous.get(name):
                raise CandidateError("candidate_inherited_binding_invalid")
        if built_binding.get("binding_path") != str(path) or hashlib.sha256(
            executable.read_bytes()
        ).hexdigest() != manifest.get("artifact_sha256"):
            raise CandidateError("candidate_inherited_artifact_invalid")
        from package_tianshu_ui import verify_candidate_package

        try:
            verify_candidate_package(manifest)
        except ValueError as error:
            raise CandidateError(str(error)) from None
        if native:
            try:
                validate_native_app(source, manifest, manifest_path)
                if installed_native and managed_record is None:
                    # An installed entry may inherit only this exact accepted,
                    # sealed artifact. No arbitrary nested executable is allowed.
                    verify_bundle(
                        app_for_executable(actual_launch), read_locator(executable), manifest["artifact_sha256"]
                    )
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                raise CandidateError("candidate_inherited_artifact_invalid") from None
        initial = previous.get("initial_launch_executable")
        if (
            not isinstance(initial, str)
            or not Path(initial).is_absolute()
            or not Path(initial).is_file()
            or Path(initial).is_symlink()
            or (Path(initial).resolve() != Path(initial) and managed_record is None)
        ):
            raise CandidateError("candidate_inherited_launch_invalid")
        proven[str(Path(initial))] = str(path)
    if len(proven) > 1:
        raise CandidateError("candidate_inherited_launch_ambiguous")
    if not proven and managed.in_snapshot_store(actual_launch, workspace):
        raise CandidateError("candidate_managed_entry_unregistered")
    return next(iter(proven.items())) if proven else (str(actual_launch), "")


def prepare(
    workspace,
    issue,
    request_id,
    owner,
    validate_only=False,
    launch_executable=None,
    actor_login=None,
):
    workspace = Path(workspace).absolute()
    if (
        type(issue) is not int
        or issue < 1
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id)
        or len(request_id) > 96
    ):
        raise CandidateError("candidate_identity_invalid")
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 128 or any(ord(c) < 32 for c in owner):
        raise CandidateError("candidate_identity_invalid")
    normalized_actor = None
    if actor_login is not None and actor_login != "":
        if not isinstance(actor_login, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", actor_login):
            raise CandidateError("candidate_identity_invalid")
        normalized_actor = actor_login.lower()
    # Every read/recovery checks the current remote Issue; a private journal is not authority.
    verify_work_order(workspace, issue, request_id)
    common, repository, origin = identity(workspace)
    digest = candidate_digest(common, repository, issue, request_id, owner, normalized_actor)
    target = workspace.parent / ("godot-candidate-" + digest)
    branch = "codex/engine-candidate/" + request_id + "-" + digest
    folder = common / "gonggong-engine-candidates"
    if folder.is_symlink():
        raise CandidateError("candidate_binding_invalid")
    folder.mkdir(mode=0o700, exist_ok=True)
    binding_path = folder / (digest + ".json")
    expected = {
        "version": 1,
        "owner": owner,
        "issue": issue,
        "request_id": request_id,
        "common_dir": str(common),
        "repository": repository,
        "origin": origin,
        "source_root": str(target),
        "branch": branch,
    }
    if normalized_actor:
        expected["actor_login"] = normalized_actor
    with binding_lock(folder / (digest + ".lock"), timeout=5.0):
        if binding_path.exists():
            if binding_path.is_symlink():
                raise CandidateError("candidate_binding_invalid")
            try:
                binding = json.loads(binding_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise CandidateError("candidate_binding_invalid") from None
            if not isinstance(binding, dict):
                raise CandidateError("candidate_binding_invalid")
            reserved = binding.get("state") == "reserved"
            if reserved and validate_only:
                raise CandidateError("candidate_preparation_incomplete")
            if binding.get("state") not in ("reserved", "prepared"):
                raise CandidateError("candidate_binding_invalid")
            validate_source(workspace, binding, expected)
            if reserved:
                finish_preparation(workspace, target, binding, binding_path)
            state = "validated" if validate_only else "reused"
        else:
            if validate_only:
                raise CandidateError("candidate_binding_missing")
            # Never adopt an existing path or branch, including a previous user's checkout.
            if (
                target.exists()
                or target.is_symlink()
                or git(workspace, "show-ref", "--verify", "--quiet", "refs/heads/" + branch, check=False).returncode
                == 0
            ):
                raise CandidateError("candidate_target_occupied")
            initial_launch = ""
            inherited_binding = ""
            if launch_executable is not None:
                launch = Path(launch_executable)
                if not launch.is_absolute() or not launch.is_file():
                    raise CandidateError("candidate_launch_executable_invalid")
                from editor_native_app import app_for_executable

                launch_app = app_for_executable(launch)
                if launch_app and launch_app.is_symlink():
                    import editor_managed_native_entry as managed

                    try:
                        managed.registered_entry(launch, common)
                    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
                        raise CandidateError("candidate_managed_entry_unregistered") from None
                initial_launch, inherited_binding = inherited_launch(
                    workspace, common, repository, origin, folder, launch.resolve()
                )
            fetch_environment = None
            if sys.platform == "win32" and origin.lower().startswith("https://github.com/"):
                from editor_network_proxy import windows_https_proxy_environment

                proxy = windows_https_proxy_environment(["github.com"], os.environ)
                if proxy:
                    fetch_environment = {**os.environ, **proxy}
            git(
                workspace,
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                "origin",
                "refs/heads/main:refs/remotes/origin/main",
                env=fetch_environment,
            )
            base = git(workspace, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}").stdout.strip()
            binding = dict(
                expected,
                base_sha=base,
                state="reserved",
                created_at=int(time.time()),
                initial_launch_executable=initial_launch,
                migration_source=str(workspace),
                initial_launch_inherited_from=inherited_binding,
            )
            atomic_json(binding_path, binding)
            git(workspace, "worktree", "add", "-b", branch, str(target), base)
            validate_source(workspace, binding, expected, require_clean=True)
            finish_preparation(workspace, target, binding, binding_path)
            state = "created"
        result = {
            "ok": True,
            "state": state,
            "source_root": str(target),
            "branch": branch,
            "base_sha": binding["base_sha"],
            "issue": issue,
            "request_id": request_id,
            "owner": owner,
            "binding_path": str(binding_path),
            "common_dir": str(common),
            "repository": repository,
            "initial_launch_executable": binding.get("initial_launch_executable", ""),
            "protected_roots": binding.get("protected_roots", []),
        }
        if normalized_actor:
            result["actor_login"] = normalized_actor
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--actor-login", default=None, help="Optional GitHub account login for multi-account isolation")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--launch-executable", type=Path, help="Host launch path, recorded only for a new binding")
    args = parser.parse_args()
    try:
        result = prepare(
            args.workspace,
            args.issue,
            args.request_id,
            args.owner,
            args.validate_only,
            args.launch_executable,
            args.actor_login,
        )
    except CandidateError as error:
        result = {"ok": False, "error": str(error)}
    except Exception:
        result = {"ok": False, "error": "candidate_preparation_failed"}
    atomic_json(args.out, result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
