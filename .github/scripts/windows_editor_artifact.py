"""Restore a verified MSVC editor from a successful default-branch Actions run."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from importlib.metadata import version
from pathlib import Path, PurePosixPath

RECEIPT = "windows-editor-inputs.json"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "customizations/components/issue-workorders"))

# isort: split
import github_runtime  # noqa: E402

WORKFLOWS = {".github/workflows/runner.yml", ".github/workflows/windows_builds.yml"}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def api(path):
    return json.loads(github_runtime.run_gh("api", path))


def source_identity(root, flags, env):
    from editor_native_cache import CacheUnavailable, host_inputs, is_external_data, probe

    options = dict(item.split("=", 1) for item in flags)
    options["cache_path"] = str(root / ".scons_cache")
    try:
        dependencies = probe(root, options, dict(env))["native_sources"]
        if not isinstance(dependencies, list) or not dependencies or not all(isinstance(p, str) for p in dependencies):
            raise ValueError("Invalid SCons dependency inventory")
        dependencies = set(dependencies)
        host_files = host_inputs(root, committed=True)
    except (CacheUnavailable, KeyError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Full-tree identity required: {error}")
        dependencies = None
        host_files = ()
    entries = subprocess.check_output(["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"], cwd=root)
    digest = hashlib.sha256()
    for entry in entries.split(b"\0"):
        if entry:
            name = os.fsdecode(entry.split(b"\t", 1)[1])
            if dependencies is None or not is_external_data(name, dependencies, host_files):
                digest.update(entry + b"\0")
    return digest.hexdigest()


def inputs(root, env):
    # The hosted image pins VS, Windows SDK and system libraries. Downloaded
    # SDKs can vary on the same image and must be checked independently.
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if (
        not env.get("ImageVersion")
        or not env.get("ImageOS")
        or actual != env["CANDIDATE_REVISION"]
        or env.get("GONGGONG_NATIVE_SOURCE_ARCHIVE") != "1"
        or env.get("BUILD_NAME") != "gh"
    ):
        raise ValueError("Unidentified hosted runner or checkout")
    sdk = hashlib.sha256()
    sdk_files = []
    for label, folder in (
        ("workspace", root / "bin/build_deps"),
        ("host", Path(env["LOCALAPPDATA"]) / "Godot/build_deps"),
    ):
        if folder.exists():
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    entry = [label, path.relative_to(folder).as_posix(), digest(path)]
                    sdk.update(json.dumps(entry).encode())
                    sdk_files.append(entry)
    flags = env["EDITOR_BUILD_FLAGS"].split()
    identity = dict(
        schema=2,
        source=source_identity(root, flags, env),
        image=[env["ImageOS"], env["ImageVersion"], env["RUNNER_ARCH"]],
        python=sys.version,
        scons=version("SCons"),
        sdk_sha256=sdk.hexdigest(),
        flags=flags,
        build_name=env["BUILD_NAME"],
        version_metadata="source_archive",
    )
    return identity, sdk_files


def trusted(run, repo, branch):
    return (
        run.get("repository", {}).get("full_name") == repo
        and (run.get("head_repository") or {}).get("full_name") == repo
        and run.get("head_branch") == branch
        and run.get("path") in WORKFLOWS
        and run.get("event") in {"push", "workflow_dispatch"}
        and run.get("conclusion") == "success"
    )


def restore(run_id, repo, branch, expected, destination, scratch):
    if not str(run_id).isdecimal():
        raise ValueError("Numeric build run required")
    run = api(f"repos/{repo}/actions/runs/{run_id}")
    if not trusted(run, repo, branch):
        raise ValueError("Source run is not a compatible successful default-branch build")
    if api(f"repos/{repo}/compare/{run['head_sha']}...{branch}")["status"] not in {"ahead", "identical"}:
        raise ValueError("Source commit is outside the default branch")
    artifacts = api(f"repos/{repo}/actions/runs/{run_id}/artifacts?name=windows-editor")["artifacts"]
    matches = [a for a in artifacts if a["name"] == "windows-editor" and not a["expired"]]
    if len(matches) != 1:
        raise ValueError("Expected one immutable editor artifact")
    item = matches[0]
    archive = scratch / "editor.zip"
    with archive.open("wb") as out:
        subprocess.run(
            [github_runtime.resolve_gh(), "api", f"repos/{repo}/actions/artifacts/{int(item['id'])}/zip"],
            stdout=out,
            check=True,
            timeout=600,
        )
    checksum = "sha256:" + digest(archive)
    if item.get("digest") != checksum:
        raise ValueError("Artifact archive failed SHA-256 verification")
    with zipfile.ZipFile(archive) as packed:
        # bin/* is uploaded with bin as the archive root.
        record = json.loads(packed.read(RECEIPT))
        if (
            not record.get("inputs")
            or (expected is not None and record["inputs"] != expected)
            or record.get("revision") != run["head_sha"]
        ):
            raise ValueError("Editor source, build options, image or SDK changed")
        for entry in packed.infolist():
            path = PurePosixPath(entry.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in entry.filename
                or ":" in entry.filename
                or path.parts[:1] == ("build_deps",)
            ):
                raise ValueError("Unexpected artifact path")
        unpacked = scratch / "unpacked"
        packed.extractall(unpacked)
    exe = unpacked / "godot.windows.editor.x86_64.exe"
    if digest(exe) != record["binary_sha256"]:
        raise ValueError("Editor binary digest mismatch")
    shutil.copytree(unpacked, destination, dirs_exist_ok=True)
    return dict(source_run=run_id, artifact_id=item["id"], archive_sha256=checksum)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("lookup", "record"))
    args = parser.parse_args()
    root = Path.cwd()
    env = os.environ
    saved = Path(env["RUNNER_TEMP"]) / "editor-inputs.json"
    destination = root / "bin"
    if args.operation == "record":
        record = json.loads(saved.read_text(encoding="utf-8"))
        record["binary_sha256"] = digest(destination / "godot.windows.editor.x86_64.exe")
        (destination / RECEIPT).write_text(json.dumps(record, indent=2), encoding="utf-8")
        return
    expected, sdk_files = inputs(root, env)
    key = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    requested = env.get("SOURCE_RUN")
    repo, branch = env["GITHUB_REPOSITORY"], env["DEFAULT_BRANCH"]
    hit = None
    try:
        runs = (
            [requested]
            if requested
            else [
                item["workflow_run"]["id"]
                for item in api(f"repos/{repo}/actions/artifacts?name=windows-editor-key-{key}&per_page=100")[
                    "artifacts"
                ]
                if not item["expired"] and item["workflow_run"]["head_branch"] == branch
            ][:3]
        )
        for run_id in runs:
            try:
                with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"]) as folder:
                    hit = restore(run_id, repo, branch, expected, destination, Path(folder))
                break
            except (KeyError, ValueError, OSError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
                if requested:
                    raise
                print(f"Source run {run_id} unavailable: {error}")
    except (github_runtime.GitHubCommandError, subprocess.SubprocessError):
        if requested:
            raise
        print("Source run lookup unavailable; compiling locally")
    saved.write_text(
        json.dumps(
            dict(
                inputs=expected,
                sdk_files=sdk_files,
                revision=env["CANDIDATE_REVISION"],
                pr_head=env.get("PR_HEAD"),
                pr_base=env.get("PR_BASE"),
                source_tree=subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip(),
                consumer_run=env["GITHUB_RUN_ID"],
                reuse=hit,
            )
        ),
        encoding="utf-8",
    )
    with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
        print("key=" + key, file=handle)
        print("hit=" + ("true" if hit else "false"), file=handle)


if __name__ == "__main__":
    main()
