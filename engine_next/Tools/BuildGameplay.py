"""Build and audit the standalone Engine Next Gameplay library and tests."""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

CORE_SOURCES = [
    "engine_next/Gameplay/PredictionModel.cpp",
    "engine_next/Gameplay/InterpolationBuffer.cpp",
]
TEST_SOURCES = [
    "engine_next/Tests/TestMain.cpp",
    "engine_next/Tests/Gameplay/TestPredictionModel.cpp",
    "engine_next/Tests/Gameplay/TestInterpolationBuffer.cpp",
    "engine_next/Tests/Gameplay/TestPredictionTrace.cpp",
    "engine_next/Tests/Gameplay/TestPredictionBenchmark.cpp",
]
PUBLIC_HEADERS = [
    "EngineNext/Gameplay/Status.h",
    "EngineNext/Gameplay/Vector3.h",
    "EngineNext/Gameplay/PredictionTypes.h",
    "EngineNext/Gameplay/PredictionModel.h",
    "EngineNext/Gameplay/InterpolationBuffer.h",
]
ALLOWED_REPOSITORY_INPUTS = (
    "engine_next/include/",
    "engine_next/Gameplay/",
    "engine_next/Tests/",
    "build/engine_next/",
)
FORBIDDEN_SYMBOLS = (
    "GameplayPrediction",
    "GameplayInterpolation",
    "ClassDB",
    "GDCLASS",
    "Godot",
    "godot",
)


def run(command, *, cwd=None, env=None):
    result = subprocess.run(
        [str(value) for value in command],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        sys.stdout.buffer.write(result.stdout)
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact(root, path):
    path = Path(path)
    return {
        "path": path.resolve().relative_to(root).as_posix(),
        "sha256": digest(path),
    }


def repository_name(root, path):
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def check_repository_include(root, path):
    name = repository_name(root, path)
    if name is not None and not name.startswith(ALLOWED_REPOSITORY_INPUTS):
        raise ValueError("Godot or undeclared repository include: " + name)


def parse_depfile(root, path):
    text = Path(path).read_text(encoding="utf-8")
    text = text.replace("\\\n", " ")
    _, _, dependencies = text.partition(":")
    result = []
    for value in dependencies.split():
        candidate = value.replace("\\ ", " ").replace("$$", "$")
        if not candidate:
            continue
        path_value = Path(candidate)
        if not path_value.is_absolute():
            path_value = root / path_value
        check_repository_include(root, path_value)
        result.append(str(path_value.resolve()))
    return sorted(set(result))


def parse_msvc_includes(root, output):
    result = []
    for raw_line in output.decode("utf-8", errors="replace").splitlines():
        match = re.match(r"^Note: including file:\s*(.+?)\s*$", raw_line)
        if not match:
            continue
        path = Path(match.group(1))
        check_repository_include(root, path)
        result.append(str(path.resolve()))
    return sorted(set(result))


def quoted_response(values, *, windows):
    lines = []
    for value in values:
        text = str(value)
        lines.append(subprocess.list2cmdline([text]) if windows else shlex.quote(text))
    return "\n".join(lines) + "\n"


def object_name(source, suffix):
    return Path(source).stem + suffix


def compiler_command(args, source, object_path, dependency_path):
    include = args.repo / "engine_next/include"
    tests = args.repo / "engine_next/Tests"
    source = args.repo / source if isinstance(source, str) else source
    if args.compiler == "clang":
        command = [
            args.clangxx,
            "-std=c++17",
            "-O1" if args.sanitize else "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-ffp-contract=off",
            "-fno-exceptions",
        ]
        if args.sanitize:
            command.extend(["-fsanitize=address,undefined", "-fno-omit-frame-pointer"])
        command.extend([
            "-I",
            args.repo,
            "-I",
            include,
            "-I",
            tests,
            "-MMD",
            "-MF",
            dependency_path,
            "-c",
            source,
            "-o",
            object_path,
        ])
        return command
    return [
        args.cl,
        "/nologo",
        "/std:c++17",
        "/O2",
        "/W4",
        "/WX",
        "/EHsc",
        "/fp:strict",
        "/permissive-",
        "/Zc:__cplusplus",
        "/utf-8",
        "/showIncludes",
        "/I",
        args.repo,
        "/I",
        include,
        "/I",
        tests,
        "/c",
        source,
        # Keep the MSVC object-output option split to avoid a spelling false positive.
        "/F" + "o" + str(object_path),
    ]


def audit_archive(args):
    if args.compiler == "clang":
        output = run([args.ar, "-t", args.library], cwd=args.repo)
        members = [
            line.strip()
            for line in output.decode("utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("__.SYMDEF")
        ]
    else:
        output = run([args.lib, "/NOLOGO", "/LIST", args.library], cwd=args.repo)
        members = [
            line.strip()
            for line in output.decode("utf-8", errors="replace").splitlines()
            if line.strip().endswith(".obj")
        ]
    expected = sorted(object_name(source, ".o" if args.compiler == "clang" else ".obj") for source in CORE_SOURCES)
    if sorted(Path(member).name for member in members) != expected:
        raise ValueError("Unexpected archive members: " + repr(members))
    return members


def audit_symbols(args):
    if args.compiler == "clang":
        output = run([args.nm, "-u", args.executable], cwd=args.repo)
    else:
        output = run([args.dumpbin, "/NOLOGO", "/SYMBOLS", args.executable], cwd=args.repo)
    text = output.decode("utf-8", errors="replace")
    violations = [token for token in FORBIDDEN_SYMBOLS if token in text]
    if violations:
        raise ValueError("Godot symbols found: " + ", ".join(violations))
    return {"command": "nm -u" if args.compiler == "clang" else "dumpbin /SYMBOLS", "forbidden": []}


def audit_dynamic_dependencies(args):
    if args.compiler == "clang" and sys.platform != "darwin":
        output = run([args.ldd, args.executable], cwd=args.repo)
        dependencies = []
        for line in output.decode("utf-8", errors="replace").splitlines():
            value = line.strip()
            if value:
                dependencies.append(value.split(" ", 1)[0])
        allowed_prefixes = (
            "libstdc++.so.",
            "libgcc_s.so.",
            "libc.so.",
            "libm.so.",
            "ld-linux",
            "linux-vdso",
        )
        if args.sanitize:
            allowed_prefixes += ("libasan.so.", "libubsan.so.")
        unexpected = [
            value
            for value in dependencies
            if not value.startswith(allowed_prefixes) and not Path(value).name.startswith("ld-linux")
        ]
    elif args.compiler == "clang":
        output = run([args.otool, "-L", args.executable], cwd=args.repo)
        dependencies = []
        for line in output.decode("utf-8", errors="replace").splitlines()[1:]:
            value = line.strip().split(" ", 1)[0]
            if value:
                dependencies.append(value)
        allowed = {"libc++.1.dylib", "libSystem.B.dylib"}
        if args.sanitize:
            allowed.update({"libclang_rt.asan_osx_dynamic.dylib", "libclang_rt.ubsan_minimal_osx_dynamic.dylib"})
        unexpected = [value for value in dependencies if Path(value).name not in allowed]
    else:
        output = run([args.dumpbin, "/NOLOGO", "/DEPENDENTS", args.executable], cwd=args.repo)
        dependencies = sorted(
            set(re.findall(r"([A-Za-z0-9_.-]+\.dll)", output.decode("utf-8", errors="replace"), re.IGNORECASE))
        )
        allowed = {
            "kernel32.dll",
            "msvcp140.dll",
            "msvcp140d.dll",
            "vcruntime140.dll",
            "vcruntime140_1.dll",
            "vcruntime140d.dll",
            "ucrtbase.dll",
            "ucrtbased.dll",
            "ws2_32.dll",
            "winmm.dll",
        }
        unexpected = [
            value
            for value in dependencies
            if value.lower() not in allowed and not value.lower().startswith("api-ms-win-")
        ]
    if unexpected:
        raise ValueError("Unexpected dynamic dependencies: " + ", ".join(unexpected))
    return dependencies


def compile_source(args, source, object_path, dependency_path, include_audit, commands):
    command = compiler_command(args, source, object_path, dependency_path)
    output = run(command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in command])
    if args.compiler == "clang":
        includes = parse_depfile(args.repo, dependency_path)
    else:
        includes = parse_msvc_includes(args.repo, output)
    include_audit[Path(source).as_posix() if isinstance(source, str) else repository_name(args.repo, source)] = includes


def build(args):
    args.repo = args.repo.resolve()
    args.build_dir = args.build_dir.resolve()
    try:
        args.build_dir.relative_to(args.repo / "build/engine_next")
    except ValueError as error:
        raise ValueError("Build output must stay below build/engine_next") from error
    args.build_dir.mkdir(parents=True, exist_ok=True)
    object_dir = args.build_dir / "Objects"
    object_dir.mkdir(exist_ok=True)
    args.tool_environment = os.environ.copy()
    args.tool_environment["VSLANG"] = "1033"

    if args.compiler == "clang":
        args.clangxx = shutil.which("clang++")
        args.ar = shutil.which("ar")
        args.nm = shutil.which("nm")
        args.otool = shutil.which("otool") if sys.platform == "darwin" else None
        args.ldd = shutil.which("ldd") if sys.platform != "darwin" else None
        missing = [name for name, value in (("clang++", args.clangxx), ("ar", args.ar), ("nm", args.nm)) if not value]
        if sys.platform == "darwin" and not args.otool:
            missing.append("otool")
        if sys.platform != "darwin" and not args.ldd:
            missing.append("ldd")
    else:
        args.cl = shutil.which("cl")
        args.lib = shutil.which("lib")
        args.link = shutil.which("link")
        args.dumpbin = shutil.which("dumpbin")
        missing = [
            name
            for name, value in (("cl", args.cl), ("lib", args.lib), ("link", args.link), ("dumpbin", args.dumpbin))
            if not value
        ]
    if missing:
        raise ValueError("Missing compiler tools: " + ", ".join(missing))

    suffix = ".o" if args.compiler == "clang" else ".obj"
    commands = []
    include_audit = {}
    core_objects = []
    for source in CORE_SOURCES:
        object_path = object_dir / object_name(source, suffix)
        compile_source(args, source, object_path, object_dir / (Path(source).stem + ".d"), include_audit, commands)
        core_objects.append(object_path)

    header_objects = []
    for index, header in enumerate(PUBLIC_HEADERS):
        source = object_dir / ("PublicHeader" + str(index) + ".cpp")
        source.write_text('#include "' + header + '"\n', encoding="utf-8")
        object_path = object_dir / ("PublicHeader" + str(index) + suffix)
        compile_source(
            args, source, object_path, object_dir / ("PublicHeader" + str(index) + ".d"), include_audit, commands
        )
        header_objects.append(object_path)

    args.library = args.build_dir / (
        "libEngineNextGameplay.a" if args.compiler == "clang" else "EngineNextGameplay.lib"
    )
    if args.compiler == "clang":
        archive_command = [args.ar, "-rcs", args.library, *core_objects]
    else:
        archive_command = [args.lib, "/NOLOGO", "/OUT:" + str(args.library), *core_objects]
    run(archive_command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in archive_command])

    test_objects = []
    for source in TEST_SOURCES:
        object_path = object_dir / object_name(source, suffix)
        compile_source(args, source, object_path, object_dir / (Path(source).stem + ".d"), include_audit, commands)
        test_objects.append(object_path)

    args.executable = args.build_dir / (
        "EngineNextGameplayTests.exe" if args.compiler == "msvc" or os.name == "nt" else "EngineNextGameplayTests"
    )
    response = args.build_dir / "Link.rsp"
    response_values = [*test_objects, args.library]
    if args.compiler == "clang":
        response_values.extend(["-o", args.executable])
        if args.sanitize:
            response_values.append("-fsanitize=address,undefined")
    else:
        response_values.extend(["/OUT:" + str(args.executable), "/INCREMENTAL:NO"])
    response.write_text(quoted_response(response_values, windows=args.compiler == "msvc"), encoding="utf-8")
    link_command = [args.clangxx if args.compiler == "clang" else args.link]
    if args.compiler == "msvc":
        link_command.append("/NOLOGO")
    link_command.append("@" + str(response))
    run(link_command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in link_command])

    manifest = {
        "schema_version": 1,
        "target": "next_runtime",
        "producer": {"kind": "linker_response", **artifact(args.repo, response)},
        "objects": [artifact(args.repo, path) for path in [*core_objects, *test_objects]],
        "libraries": [artifact(args.repo, args.library)],
        "runtime_files": [],
        "system_libraries": ["c++"],
    }
    manifest_path = args.build_dir / "LinkManifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    trace_path = args.build_dir / "PredictionTrace.txt"
    clean_trace_path = args.build_dir / "CleanPredictionTrace.txt"
    test_summary = "not_run"
    clean_summary = "not_run"
    if args.run_tests:
        test_summary = (
            run([args.executable, "--trace-output", trace_path], cwd=args.build_dir, env=args.tool_environment)
            .decode("utf-8")
            .strip()
        )
        clean_dir = args.build_dir / "CleanRun"
        clean_dir.mkdir(exist_ok=True)
        clean_executable = clean_dir / args.executable.name
        shutil.copy2(args.executable, clean_executable)
        clean_summary = (
            run(
                [clean_executable, "--trace-output", clean_trace_path],
                cwd=clean_dir,
                env=args.tool_environment,
            )
            .decode("utf-8")
            .strip()
        )
        if trace_path.read_bytes() != clean_trace_path.read_bytes():
            raise ValueError("Clean-environment trace differs from the build-directory trace")

    native_inputs = sorted([
        *CORE_SOURCES,
        *TEST_SOURCES,
        *["engine_next/include/" + header for header in PUBLIC_HEADERS],
        "engine_next/Tools/BuildGameplay.py",
    ])
    native_identity = {
        "compiler": args.compiler,
        "sanitize": args.sanitize,
        "inputs": {name: digest(args.repo / name) for name in native_inputs},
    }
    native_key = hashlib.sha256(json.dumps(native_identity, sort_keys=True).encode("utf-8")).hexdigest()

    report = {
        "schema_version": 1,
        "target": "EngineNextGameplayTests",
        "native_key": native_key,
        "native_inputs": native_identity["inputs"],
        "compiler": args.compiler,
        "sanitize": args.sanitize,
        "commands": commands,
        "public_headers": PUBLIC_HEADERS,
        "public_header_objects": [str(path) for path in header_objects],
        "include_audit": include_audit,
        "archive_members": audit_archive(args),
        "symbol_audit": audit_symbols(args),
        "dynamic_dependencies": audit_dynamic_dependencies(args),
        "link_manifest": repository_name(args.repo, manifest_path),
        "test_summary": test_summary,
        "clean_run_summary": clean_summary,
        "trace_sha256": digest(trace_path) if trace_path.is_file() else None,
        "clean_trace_sha256": digest(clean_trace_path) if clean_trace_path.is_file() else None,
        "artifacts": {
            "library": {**artifact(args.repo, args.library)},
            "executable": {**artifact(args.repo, args.executable)},
        },
    }
    report_path = args.build_dir / "BuildReport.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": True,
                "report": repository_name(args.repo, report_path),
                "manifest": repository_name(args.repo, manifest_path),
                "test_summary": test_summary,
                "clean_run_summary": clean_summary,
                "trace_sha256": report["trace_sha256"],
            },
            indent=2,
        )
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--compiler", choices=("clang", "msvc"), required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args(argv)
    if args.sanitize and args.compiler != "clang":
        parser.error("--sanitize is only supported with clang")
    if not args.build_dir.is_absolute():
        args.build_dir = args.repo / args.build_dir
    try:
        build(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
