"""Share checked native editor bytes between worktrees of one local Git repository."""

import ast
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class CacheUnavailable(Exception):
    """SCons should run normally when this build cannot be identified."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", root, *args], timeout=120)


UI_OUTPUTS = {"bin/tianshu-ui.json", "bin/tianshu-ui.self_update_a.json", "bin/tianshu-ui.self_update_b.json"}
EXTERNAL_SCRIPTS = {"editor/docks/daqian/graph_layout.gd", "editor/docks/daqian/issue_graph.gd"}
REPRODUCIBLE = "GONGGONG_NATIVE_SOURCE_ARCHIVE"
REQUEST_CONTEXT = {"PWD", "OLDPWD", "GONGGONG_WORKSPACE", "WT_SESSION", "TERM_SESSION_ID", "CODEX_TOOL_CALL_ID"}
RESTORE_MARKERS = "bin/.gonggong-native-restores"
PROGRESS = {"GODOT_BUILD_COUNT_ONLY", "GODOT_BUILD_PROGRESS_TOTAL", "GODOT_BUILD_PROGRESS_FILE"}


def host_inputs(root, *, committed=False):
    """Read an exact, reviewed inventory; the policy itself stays a native input.

    This never makes a placement declaration or a directory wildcard sufficient
    for reuse. The configured SCons consumers always override these candidates.
    """
    path = root / "tools/native_host_inputs.json"
    if committed:
        entry = git(root, "ls-tree", "-z", "HEAD", "--", "tools/native_host_inputs.json")
        if not entry:
            return frozenset()
        mode, kind, oid = entry.split(b"\t", 1)[0].split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise CacheUnavailable("non-file host input inventory")
        raw = git(root, "cat-file", "blob", oid.decode("ascii"))
    else:
        if not path.exists():
            return frozenset()
        if path.is_symlink():
            raise CacheUnavailable("linked host input inventory")
        raw = path.read_bytes()
    try:
        policy = json.loads(raw)
        if (
            not isinstance(policy, dict)
            or set(policy) != {"schema_version", "inputs"}
            or type(policy["schema_version"]) is not int
            or policy["schema_version"] != 1
        ):
            raise ValueError("inventory schema")
        names = policy["inputs"]
        if (
            not isinstance(names, list)
            or any(
                not isinstance(name, str)
                or "\\" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or not name.startswith((
                    "customizations/components/tianxuan/",
                    "customizations/platforms/development/git/heqi/",
                ))
                or Path(name).suffix not in {".py", ".md"}
                for name in names
            )
            or len(set(names)) != len(names)
        ):
            raise ValueError("exact host input paths required")
        return frozenset(names)
    except (ValueError, TypeError, KeyError) as error:
        raise CacheUnavailable("invalid host input inventory") from error


def is_external_data(name, native_sources, host_files=()):
    """Classified host records/fixtures remain native when a generator consumes them."""
    if name in native_sources:
        return False
    p = Path(name)
    if name in host_files or name in EXTERNAL_SCRIPTS or name == "work-items.json":
        return True
    if p.parent.as_posix() == "tests/editor":
        return p.suffix == ".gd" or (p.name.startswith("run_") and p.suffix == ".py")
    if p.parts[0] == "design-docs":
        return p.suffix == ".md"
    if p.parts[0] in {"data-collection", "gonggong-diting-data"}:
        return p.suffix in {".json", ".jsonl", ".md"}
    return p.parent.as_posix() == "bin/gonggong-build-receipts" and p.suffix == ".json"


def write_probe(env, path, git_info):
    """Called in SCons after platform selection and all SCsubs were evaluated."""
    from SCons.Environment import CleanTargets
    from SCons.Node.FS import Dir
    from SCons.Node.Python import Value

    root = Path.cwd()
    stack = [env.Dir("#")]
    sources, generated = set(), set()
    while stack:
        directory = stack.pop()
        for name, node in directory.entries.items():
            if name in (".", ".."):
                continue
            if isinstance(node, Dir):
                stack.append(node)
            else:
                relative = Path(node.abspath).relative_to(root).as_posix()
                if node.has_builder():
                    generated.add(relative)
                else:
                    sources.add(relative)
    for nodes in CleanTargets.values():
        for node in nodes:
            output = Path(node.abspath)
            if output.is_relative_to(root):
                generated.add(output.relative_to(root).as_posix())
    sources.difference_update(generated)
    # Requires() orders the independently generated UI package before the build.
    # SCons deliberately excludes these order-only edges from content signatures.
    native_sources = set()
    # Static library dependencies are often discovered later by tool scanners.
    # Include all configured generators too, even when not reachable by walking
    # explicit edges from the final linker node.
    pending = [env.Entry("#" + n) for n in generated if n not in UI_OUTPUTS]
    seen = set()
    generated_values = {}
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        absolute = getattr(node, "abspath", None)
        if absolute and Path(absolute).is_relative_to(root):
            native_sources.add(Path(absolute).relative_to(root).as_posix())
        for field in ("sources", "depends", "implicit"):
            children = getattr(node, field, None) or ()
            pending.extend(children)
            values = [
                hashlib.sha256(child.get_contents()).hexdigest() for child in children if isinstance(child, Value)
            ]
            if values and absolute and Path(absolute).is_relative_to(root):
                generated_values[Path(absolute).relative_to(root).as_posix() + "/" + field] = values
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).is_absolute() and Path(filename).is_relative_to(root):
            native_sources.add(Path(filename).relative_to(root).as_posix())
    tool_paths = {}
    for name in ("CC", "CXX", "LINK", "AR", "RC"):
        command = env.subst("$" + name)
        tool_paths[name] = env.WhereIs(command) if command else None
    search = env["ENV"]
    roots = []
    for key in ("INCLUDE", "LIB", "LIBPATH"):
        roots.extend(str(search.get(key, "")).split(os.pathsep))
    for key in ("CPPPATH", "LIBPATH"):
        for entry in env.get(key, []):
            directory = Path(env.Dir(entry).abspath)
            if not directory.is_relative_to(root):
                roots.append(str(directory))
    for key in ("accesskit_sdk_path", "angle_libs", "agility_sdk_path", "pix_path", "dxc_path", "mesa_libs"):
        if env.get(key):
            roots.append(str(env[key]))
    result = {
        "msvc": bool(env.msvc),
        "git_info": git_info,
        "roots": sorted(set(filter(None, roots))),
        "tools": tool_paths,
        "sources": sorted(sources),
        "generated": sorted(generated),
        "native_sources": sorted(native_sources),
        "generated_values": hashlib.sha256(canonical(generated_values)).hexdigest(),
        "sdk": [str(env.get(key, "")) for key in ("MSVC_VERSION", "MSVC_SDK_VERSION", "TARGET_ARCH")],
        "unsupported": any(
            env.get(k) for k in ("module_mono_enabled", "vsproj", "compiledb", "use_llvm", "ninja", "debug_symbols")
        )
        or env.get("library_type") != "executable",
    }
    Path(path).write_bytes(canonical(result))


def probe(root, options, env):
    with tempfile.TemporaryDirectory(prefix="godot_native_probe_") as tmp:
        path = Path(tmp) / "selection.json"
        command = [sys.executable, "-m", "SCons", "-n", "-Q", f"gonggong_native_probe={path}"]
        command.extend(f"{k}={v}" for k, v in sorted(options.items()))
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=180)
        if result.returncode or not path.is_file():
            raise CacheUnavailable("SCons could not identify native inputs")
        return json.loads(path.read_bytes())


def file_value(path):
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise CacheUnavailable("linked input")
    if path.is_file():
        return [path.stat().st_mode & 0o111, digest(path)]
    if path.exists():
        raise CacheUnavailable("non-file input")
    return None


def hash_files(pool, root, names, cancelled):
    def read(name):
        check_cancel(cancelled)
        return file_value(root / name)

    return dict(zip(names, pool.map(read, names)))


def tree_value(path, pool, cancelled):
    if not path.exists():
        return None
    if not path.is_dir():
        return file_value(path)
    files_to_hash = []
    for directory, dirs, files in os.walk(path, onerror=raise_oserror):
        check_cancel(cancelled)
        for name in dirs:
            item = Path(directory) / name
            if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                raise CacheUnavailable("linked toolchain or SDK")
        base = Path(directory).relative_to(path)
        files_to_hash.extend((base / name).as_posix() for name in files)
    return hashlib.sha256(canonical(hash_files(pool, path, files_to_hash, cancelled))).hexdigest()


def raise_oserror(error):
    raise error


def path_list(data):
    return {os.fsdecode(item) for item in data.split(b"\0") if item}


def identify(root, options, artifact, env, cancelled=None):
    # Restrict reuse to option shapes whose external inputs and native outputs
    # the probe can enumerate. Other target/toolchain configurations still build.
    supported = {
        "platform",
        "target",
        "arch",
        "dev_build",
        "precision",
        "module_mono_enabled",
        "ninja",
        "extra_suffix",
        "tests",
        "accesskit",
        "d3d12",
        "angle",
        "vulkan",
        "opengl3",
        "use_volk",
        "debug_symbols",
        "optimize",
        "msvc_version",
        "mssdk_version",
        "windows_subsystem",
        "production",
    }
    resources = {"cache_path", "cache_limit"}
    if options.get("cache_path"):
        object_cache = (root / options["cache_path"]).resolve()
        if object_cache.is_relative_to(root):
            raise CacheUnavailable("object cache inside source worktree")
    if (
        options.get("platform") != "windows"
        or options.get("target") != "editor"
        or set(options) - supported - resources
    ):
        raise CacheUnavailable("unidentified configuration")
    if not (root / "SConstruct").is_file():
        raise CacheUnavailable("SCons root unavailable")
    custom = root / "custom.py"
    if custom.exists():
        for statement in ast.parse(custom.read_bytes()).body:
            if not (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id in supported
                and isinstance(statement.value, ast.Constant)
            ):
                raise CacheUnavailable("dynamic SCons custom configuration")
    if any(env.get(k) for k in ("SCONSFLAGS", "SCONS_LIB_DIR", "PYTHONPATH", "CL", "_CL_", "LINK", "_LINK_")):
        raise CacheUnavailable("external build configuration")
    import SCons

    effective_env = {k: v for k, v in env.items() if k not in REQUEST_CONTEXT}
    selected = probe(root, options, {**effective_env, REPRODUCIBLE: "1"})
    if not selected["msvc"] or selected["unsupported"] or not all(selected["tools"].values()):
        raise CacheUnavailable("unidentified native toolchain")
    if selected["git_info"] != {"git_hash": "", "git_timestamp": 0}:
        raise CacheUnavailable("native Git metadata is request-specific")
    generated = set(selected["generated"])
    sources = set(selected["sources"])
    native_sources = set(selected["native_sources"])
    host_files = host_inputs(root)
    tracked = path_list(git(root, "ls-files", "-z"))
    added = path_list(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    ignored = path_list(git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    names = []
    output = artifact.relative_to(root).as_posix()
    sidecars = {"bin/editor_self_build.lock", output + ".build.json", output + ".candidate.json"}
    for name in sorted(tracked | added | ignored):
        if is_external_data(name, native_sources, host_files):
            continue
        local_state = (
            name in {".scons_node_count", ".scons_env.json"}
            or (name.startswith(".sconsign") and "/" not in name and name.endswith(".dblite"))
            or name.startswith((".ruff_cache/", ".gonggong-outbox/", "bin/.vs/"))
            or (name.startswith("bin/") and name.count("/") == 1 and name.endswith((".log", "-report.json")))
        )
        if local_state and name in ignored and name not in native_sources:
            continue
        if name in ignored and name not in sources:
            p = Path(name)
            if name in generated or name in sidecars or name.startswith(RESTORE_MARKERS + "/"):
                continue
            if p.suffix == ".pyc" and "__pycache__" in p.parts:
                continue
        names.append(name)
    roots = {Path(p).resolve() for p in selected["roots"]}
    for tool in selected["tools"].values():
        directory = Path(tool).resolve().parent
        roots.add(directory)
    roots.add(Path(SCons.__file__).resolve().parent)
    external = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        inputs = hash_files(pool, root, names, cancelled)
        for directory in sorted(roots):
            label = directory.relative_to(root).as_posix() if directory.is_relative_to(root) else str(directory)
            external[label] = tree_value(directory, pool, cancelled)
    if output not in generated:
        raise CacheUnavailable("artifact not in configured graph")
    outputs = [output]
    if options.get("windows_subsystem", "gui") == "gui":
        console = artifact.with_suffix(".console.exe").relative_to(root).as_posix()
        if console not in generated:
            raise CacheUnavailable("console artifact not in configured graph")
        outputs.append(console)
    outputs.extend(sorted(n for n in generated if n.startswith("bin/") and n.lower().endswith(".dll")))
    identity = {
        "version": 1,
        "options": {k: v for k, v in options.items() if k not in resources},
        "outputs": outputs,
        "inputs": inputs,
        "generated_values": selected["generated_values"],
        "external": external,
        "python": [sys.version, digest(Path(sys.executable))],
        "scons": SCons.__version__,
        "sdk": selected["sdk"],
        "tools": selected["tools"],
        "environment": {k: v for k, v in effective_env.items() if k not in PROGRESS | {REPRODUCIBLE}},
    }
    check_cancel(cancelled)
    return hashlib.sha256(canonical(identity)).hexdigest(), outputs


def native_key(root, options, artifact, env=None):
    try:
        return identify(Path(root).resolve(), options, Path(artifact).resolve(), os.environ if env is None else env)[0]
    except (OSError, ImportError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        raise CacheUnavailable(str(error)) from error


def check_cancel(cancelled):
    if cancelled and cancelled():
        raise InterruptedError("Native build cancelled")


@contextlib.contextmanager
def single_flight(path, cancelled):
    # A kernel lock is released on process exit. Never unlink its inode.
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
        while True:
            check_cancel(cancelled)
            try:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except PermissionError:
                time.sleep(0.2)
            except BlockingIOError:
                time.sleep(0.2)
        yield


def verified_copy(source, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
        stage = Path(temp.name)
    try:
        shutil.copy2(source, stage)
        if digest(stage) != expected:
            raise ValueError("native cache artifact digest mismatch")
        stage.replace(target)
    finally:
        stage.unlink(missing_ok=True)


def restored_target_dependencies(env):
    """Invalidate only targets replaced outside SCons since their last local build."""
    markers = Path(env.Dir("#").abspath) / RESTORE_MARKERS
    for marker in markers.rglob("*.generation"):
        output = marker.relative_to(markers).with_suffix("").as_posix()
        target = env.File("#bin/" + output)
        if target.has_builder():
            env.Depends(target, env.Value(marker.read_bytes()))


def record_restore(root, name):
    relative = Path(name).relative_to("bin")
    marker = root / RESTORE_MARKERS / (relative.as_posix() + ".generation")
    marker.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=marker.parent, delete=False) as temp:
        stage = Path(temp.name)
        temp.write(os.urandom(32))
    try:
        stage.replace(marker)
    finally:
        stage.unlink(missing_ok=True)


def build_or_reuse(root, options, artifact, produce, *, env=None, cancelled=None, store=None):
    root, artifact = Path(root).resolve(), Path(artifact).resolve()
    check_cancel(cancelled)
    try:
        if env is None:
            raise CacheUnavailable("producer environment not bound")
        key, outputs = identify(root, options, artifact, env, cancelled)
        if store is None:
            store = (
                Path(os.fsdecode(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).strip())
                / "gonggong-native-cache"
            )
        store = Path(store)
        store.mkdir(parents=True, exist_ok=True)
        lock = contextlib.ExitStack()
        lock.enter_context(single_flight(store / (key + ".lock"), cancelled))
    except InterruptedError:
        raise
    except (CacheUnavailable, OSError, ValueError, ImportError, SyntaxError, subprocess.SubprocessError) as error:
        check_cancel(cancelled)
        produce()
        check_cancel(cancelled)
        return {"status": "uncached", "reason": str(error), "key": None, "artifact_sha256": digest(artifact)}

    with lock:
        check_cancel(cancelled)
        head = git(root, "rev-parse", "HEAD").decode().strip()
        entry = store / key
        hit = entry.is_dir()
        if hit:
            try:
                metadata = json.loads((entry / "manifest.json").read_bytes())
                if (
                    metadata["key"] != key
                    or set(metadata["outputs"]) != set(outputs)
                    or not isinstance(metadata.get("producer_head"), str)
                ):
                    raise ValueError("invalid native cache manifest")
                for name in outputs:
                    if digest(entry / name) != metadata["outputs"][name]:
                        raise ValueError("corrupt native cache artifact")
            except (KeyError, TypeError, OSError, ValueError):
                # Quarantine preserves evidence and permits atomic replacement.
                entry.rename(store / (key + ".corrupt-" + os.urandom(8).hex()))
                hit = False
        if not hit:
            request_context = {k: env.pop(k) for k in REQUEST_CONTEXT if k in env}
            previous = env.get(REPRODUCIBLE)
            env[REPRODUCIBLE] = "1"
            try:
                produce()
            finally:
                env.update(request_context)
                if previous is None:
                    del env[REPRODUCIBLE]
                else:
                    env[REPRODUCIBLE] = previous
        check_cancel(cancelled)
        if (
            identify(root, options, artifact, env, cancelled) != (key, outputs)
            or git(root, "rev-parse", "HEAD").decode().strip() != head
        ):
            raise ValueError("native_build_inputs_changed")
        if hit:
            for name in outputs:
                record_restore(root, name)
                verified_copy(entry / name, root / name, metadata["outputs"][name])
        else:
            with tempfile.TemporaryDirectory(dir=store) as tmp:
                stage = Path(tmp) / "entry"
                hashes = {}
                for name in outputs:
                    hashes[name] = digest(root / name)
                    verified_copy(root / name, stage / name, hashes[name])
                metadata = {"key": key, "producer_head": head, "outputs": hashes}
                (stage / "manifest.json").write_bytes(canonical(metadata))
                check_cancel(cancelled)
                stage.rename(entry)
        check_cancel(cancelled)
        return {
            "status": "hit" if hit else "built",
            "key": key,
            "reason": "",
            "artifact_sha256": metadata["outputs"][outputs[0]],
            "producer_head": metadata["producer_head"],
            "consumer_head": head,
            "outputs": metadata["outputs"],
        }
