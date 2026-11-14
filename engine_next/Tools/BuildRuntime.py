"""Build and audit Engine Next server, client and runtime tests without Godot."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import BuildGameplay as BuildSupport
import PackageRuntime

ENET_SOURCES = [
    "engine_next/thirdparty/enet/callbacks.c",
    "engine_next/thirdparty/enet/compress.c",
    "engine_next/thirdparty/enet/host.c",
    "engine_next/thirdparty/enet/list.c",
    "engine_next/thirdparty/enet/packet.c",
    "engine_next/thirdparty/enet/peer.c",
    "engine_next/thirdparty/enet/protocol.c",
    "engine_next/thirdparty/enet/unix.c",
    "engine_next/thirdparty/enet/win32.c",
]
LIBRARY_SOURCES = [
    *ENET_SOURCES,
    "engine_next/Gameplay/PredictionModel.cpp",
    "engine_next/Gameplay/InterpolationBuffer.cpp",
    "engine_next/Gameplay/PredictionReconciler.cpp",
    "engine_next/Runtime/Clock.cpp",
    "engine_next/Runtime/FixedStepLoop.cpp",
    "engine_next/Runtime/World.cpp",
    "engine_next/Runtime/Trace.cpp",
    "engine_next/Runtime/RuntimeConfig.cpp",
    "engine_next/Runtime/RuntimeHost.cpp",
    "engine_next/Network/Protocol.cpp",
    "engine_next/Network/EnetTransport.cpp",
    "engine_next/Network/ImpairmentTransport.cpp",
    "engine_next/Network/SessionManager.cpp",
    "engine_next/Server/ServerRuntime.cpp",
    "engine_next/Client/ClientRuntime.cpp",
]
TEST_SOURCES = [
    "engine_next/Tests/RuntimeTestMain.cpp",
    "engine_next/Tests/Runtime/TestClockAndFixedStep.cpp",
    "engine_next/Tests/Runtime/TestWorld.cpp",
    "engine_next/Tests/Runtime/TestRuntimeConfig.cpp",
    "engine_next/Tests/Runtime/TestRuntimeHost.cpp",
    "engine_next/Tests/Network/TestProtocol.cpp",
    "engine_next/Tests/Network/TestImpairmentTransport.cpp",
    "engine_next/Tests/Gameplay/TestPredictionReconciler.cpp",
]
APP_SOURCES = {
    "next_server": ["engine_next/Apps/NextServerMain.cpp"],
    "next_client": ["engine_next/Apps/NextClientMain.cpp"],
    "EngineNextRuntimeTests": TEST_SOURCES,
}
PUBLIC_HEADERS = [
    "EngineNext/Gameplay/Status.h",
    "EngineNext/Gameplay/Vector3.h",
    "EngineNext/Gameplay/PredictionTypes.h",
    "EngineNext/Gameplay/PredictionModel.h",
    "EngineNext/Gameplay/InterpolationBuffer.h",
    "EngineNext/Gameplay/PredictionReconciler.h",
    "EngineNext/Runtime/Types.h",
    "EngineNext/Runtime/Clock.h",
    "EngineNext/Runtime/FixedStepLoop.h",
    "EngineNext/Runtime/World.h",
    "EngineNext/Runtime/Trace.h",
    "EngineNext/Runtime/RuntimeConfig.h",
    "EngineNext/Runtime/RuntimeHost.h",
    "EngineNext/Network/ITransport.h",
    "EngineNext/Network/Protocol.h",
    "EngineNext/Network/ImpairmentTransport.h",
]
BUILD_SUPPORT_SOURCES = [
    "engine_next/Tools/BuildGameplay.py",
    "engine_next/Tools/BuildRuntime.py",
    "engine_next/Tools/RunM2Handshake.py",
    "engine_next/Tools/RunM2DrainFaults.py",
    "engine_next/Tools/RunM2Soak.py",
    "engine_next/Tools/PackageRuntime.py",
]
BuildSupport.ALLOWED_REPOSITORY_INPUTS = (
    "engine_next/",
    "build/engine_next/",
)


def runtime_object_name(source, suffix):
    path_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    return Path(source).stem + "-" + path_digest + suffix


def audit_archive(args, sources):
    if args.compiler == "clang":
        output = BuildSupport.run([args.ar, "-t", args.library], cwd=args.repo)
        members = [
            line.strip()
            for line in output.decode("utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("__.SYMDEF")
        ]
    else:
        output = BuildSupport.run([args.lib, "/NOLOGO", "/LIST", args.library], cwd=args.repo)
        members = [
            line.strip()
            for line in output.decode("utf-8", errors="replace").splitlines()
            if line.strip().endswith(".obj")
        ]
    expected = sorted(runtime_object_name(source, ".o" if args.compiler == "clang" else ".obj") for source in sources)
    if sorted(Path(member).name for member in members) != expected:
        raise ValueError("Unexpected archive members: " + repr(members))
    return members


def audit_symbols(args, executable):
    if args.compiler == "clang":
        command = [args.nm, executable]
    else:
        command = [args.dumpbin, "/NOLOGO", "/SYMBOLS", executable]
    output = BuildSupport.run(command, cwd=args.repo)
    text = output.decode("utf-8", errors="replace")
    violations = [token for token in BuildSupport.FORBIDDEN_SYMBOLS if token in text]
    if violations:
        raise ValueError("Godot symbols found: " + ", ".join(violations))
    return {
        "command": [str(value) for value in command],
        "forbidden": [],
    }


def audit_linux_dependencies(args, executable):
    output = BuildSupport.run([args.ldd, executable], cwd=args.repo)
    dependencies = []
    for line in output.decode("utf-8", errors="replace").splitlines():
        value = line.strip()
        if not value:
            continue
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
    if unexpected:
        raise ValueError("Unexpected dynamic dependencies: " + ", ".join(unexpected))
    return dependencies


def audit_dynamic_dependencies(args, executable):
    if args.compiler == "msvc" or sys.platform == "darwin":
        args.executable = executable
        return BuildSupport.audit_dynamic_dependencies(args)
    return audit_linux_dependencies(args, executable)


def configure_toolchain(args):
    args.tool_environment = os.environ.copy()
    args.tool_environment["VSLANG"] = "1033"
    if args.compiler == "clang":
        args.clangxx = shutil.which("clang++")
        args.clang = shutil.which("clang")
        args.ar = shutil.which("ar")
        args.nm = shutil.which("nm")
        args.otool = shutil.which("otool") if sys.platform == "darwin" else None
        args.ldd = shutil.which("ldd") if sys.platform != "darwin" else None
        missing = [
            name
            for name, value in (("clang++", args.clangxx), ("clang", args.clang), ("ar", args.ar), ("nm", args.nm))
            if not value
        ]
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


def compiler_command_with_enet(args, source, object_path, dependency_path):
    command = BuildSupport.compiler_command(args, source, object_path, dependency_path)
    include = args.repo / "engine_next/thirdparty/enet/include"
    if args.compiler == "clang":
        index = command.index("-c")
        command[index:index] = ["-I", include]
    else:
        index = command.index("/c")
        command[index:index] = ["/I", include]
    return command


def compile_c_source(args, source, object_path, dependency_path, include_audit, commands):
    source_path = args.repo / source
    include = args.repo / "engine_next/thirdparty/enet/include"
    if args.compiler == "clang":
        command = [
            args.clang,
            "-std=c99",
            "-O1" if args.sanitize else "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-pedantic",
            "-ffp-contract=off",
            "-DHAS_INET_PTON=1",
            "-DHAS_INET_NTOP=1",
            "-I",
            args.repo,
            "-I",
            include,
            "-MMD",
            "-MF",
            dependency_path,
            "-c",
            source_path,
            "-o",
            object_path,
        ]
        if args.sanitize:
            command.extend(["-fsanitize=address,undefined", "-fno-omit-frame-pointer"])
    else:
        command = [
            args.cl,
            "/nologo",
            "/TC",
            "/D_WINSOCK_DEPRECATED_NO_WARNINGS",
            "/std:c17",
            "/O2",
            "/W4",
            "/WX",
            "/wd4100",
            "/wd4245",
            "/wd5287",
            "/fp:strict",
            "/showIncludes",
            "/I",
            args.repo,
            "/I",
            include,
            "/c",
            source_path,
            "/F" + "o" + str(object_path),
        ]
    output = BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in command])
    if args.compiler == "clang":
        includes = BuildSupport.parse_depfile(args.repo, dependency_path)
    else:
        includes = BuildSupport.parse_msvc_includes(args.repo, output)
    include_audit[source] = includes


def compile_sources(args, sources, object_dir, suffix, include_audit, commands):
    objects = []
    for source in sources:
        object_path = object_dir / runtime_object_name(source, suffix)
        dependency_path = object_dir / runtime_object_name(source, ".d")
        if source.endswith(".c"):
            compile_c_source(args, source, object_path, dependency_path, include_audit, commands)
        else:
            command = compiler_command_with_enet(args, source, object_path, dependency_path)
            output = BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
            commands.append([str(value) for value in command])
            if args.compiler == "clang":
                includes = BuildSupport.parse_depfile(args.repo, dependency_path)
            else:
                includes = BuildSupport.parse_msvc_includes(args.repo, output)
            include_audit[source] = includes
        objects.append(object_path)
    return objects


def link_target(args, name, sources, library, library_objects, object_dir, suffix, include_audit, commands):
    target_objects = compile_sources(args, sources, object_dir, suffix, include_audit, commands)
    executable = args.build_dir / (name + ".exe" if args.compiler == "msvc" or os.name == "nt" else name)
    response = args.build_dir / (name + "Link.rsp")
    response_values = [*target_objects, library]
    if args.compiler == "clang":
        response_values.extend(["-o", executable])
        if args.sanitize:
            response_values.append("-fsanitize=address,undefined")
    else:
        response_values.extend(["ws2_32.lib", "winmm.lib", "/OUT:" + str(executable), "/INCREMENTAL:NO"])
    response.write_text(
        BuildSupport.quoted_response(response_values, windows=args.compiler == "msvc"),
        encoding="utf-8",
    )
    link_command = [args.clangxx if args.compiler == "clang" else args.link]
    if args.compiler == "msvc":
        link_command.append("/NOLOGO")
    link_command.append("@" + str(response))
    BuildSupport.run(link_command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in link_command])

    system_libraries = ["c++"] if args.compiler == "msvc" or sys.platform == "darwin" else ["stdc++", "gcc_s", "c", "m"]
    if args.compiler == "msvc":
        system_libraries.extend(["ws2_32", "winmm"])
    manifest = {
        "schema_version": 1,
        "target": "next_runtime",
        "producer": {"kind": "linker_response", **BuildSupport.artifact(args.repo, response)},
        "objects": [BuildSupport.artifact(args.repo, path) for path in [*library_objects, *target_objects]],
        "libraries": [BuildSupport.artifact(args.repo, library)],
        "runtime_files": [],
        "system_libraries": system_libraries,
    }
    manifest_path = args.build_dir / (name + "LinkManifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "name": name,
        "executable": executable,
        "response": response,
        "manifest": manifest_path,
        "link_inputs": [str(value) for value in response_values],
        "symbol_audit": audit_symbols(args, executable),
        "dynamic_dependencies": audit_dynamic_dependencies(args, executable),
        "artifact": BuildSupport.artifact(args.repo, executable),
    }


def run_target(args, target, directory, trace_directory):
    executable = directory / target["executable"].name
    if target["name"] == "EngineNextRuntimeTests":
        return BuildSupport.run([executable], cwd=directory, env=args.tool_environment).decode("utf-8").strip()
    trace_path = trace_directory / (target["name"] + ".jsonl")
    return (
        BuildSupport
        .run(
            [executable, "--manual-ticks", "4", "--trace-output", trace_path],
            cwd=directory,
            env=args.tool_environment,
        )
        .decode("utf-8")
        .strip()
    )


def run_handshake(args, targets, directory):
    executables = {target["name"]: directory / target["executable"].name for target in targets}
    return (
        BuildSupport
        .run(
            [
                sys.executable,
                args.repo / "engine_next/Tools/RunM2Handshake.py",
                "--server",
                executables["next_server"],
                "--client",
                executables["next_client"],
                "--report",
                directory / "HandshakeReport.json",
            ],
            cwd=args.repo,
            env=args.tool_environment,
        )
        .decode("utf-8")
        .strip()
    )


def run_soak(args, targets):
    executables = {target["name"]: target["executable"] for target in targets}
    return (
        BuildSupport
        .run(
            [
                sys.executable,
                args.repo / "engine_next/Tools/RunM2Soak.py",
                "--server",
                executables["next_server"],
                "--client",
                executables["next_client"],
                "--report",
                args.build_dir / "SoakReport.json",
            ],
            cwd=args.repo,
            env=args.tool_environment,
        )
        .decode("utf-8")
        .strip()
    )


def run_drain_faults(args, targets, directory):
    executables = {target["name"]: directory / target["executable"].name for target in targets}
    return (
        BuildSupport
        .run(
            [
                sys.executable,
                args.repo / "engine_next/Tools/RunM2DrainFaults.py",
                "--server",
                executables["next_server"],
                "--client",
                executables["next_client"],
                "--report",
                directory / "DrainFaultsReport.json",
            ],
            cwd=args.repo,
            env=args.tool_environment,
        )
        .decode("utf-8")
        .strip()
    )


def run_acceptance(args, targets):
    summaries = {}
    clean_summaries = {}
    traces = {}
    clean_dir = args.build_dir / "CleanRun"
    clean_dir.mkdir(exist_ok=True)
    for target in targets:
        summaries[target["name"]] = run_target(args, target, args.build_dir, args.build_dir)
        clean_executable = clean_dir / target["executable"].name
        shutil.copy2(target["executable"], clean_executable)
        clean_summaries[target["name"]] = run_target(args, target, clean_dir, clean_dir)
        if target["name"] != "EngineNextRuntimeTests":
            trace_path = args.build_dir / (target["name"] + ".jsonl")
            clean_trace_path = clean_dir / (target["name"] + ".jsonl")
            if trace_path.read_bytes() != clean_trace_path.read_bytes():
                raise ValueError("Clean-environment trace differs: " + target["name"])
            traces[target["name"]] = BuildSupport.digest(trace_path)
    return {
        "summaries": summaries,
        "clean_summaries": clean_summaries,
        "trace_sha256": traces,
        "handshake": run_handshake(args, targets, args.build_dir),
        "clean_handshake": run_handshake(args, targets, clean_dir),
        "drain_faults": run_drain_faults(args, targets, args.build_dir),
        "clean_drain_faults": run_drain_faults(args, targets, clean_dir),
    }


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
    configure_toolchain(args)

    suffix = ".o" if args.compiler == "clang" else ".obj"
    commands = []
    include_audit = {}
    library_sources = [
        source
        for source in LIBRARY_SOURCES
        if not (args.compiler == "msvc" and source.endswith("/unix.c"))
        and not (args.compiler == "clang" and source.endswith("/win32.c"))
    ]
    library_objects = compile_sources(args, library_sources, object_dir, suffix, include_audit, commands)

    header_objects = []
    for index, header in enumerate(PUBLIC_HEADERS):
        source = object_dir / ("PublicHeader" + str(index) + ".cpp")
        source.write_text('#include "' + header + '"\n', encoding="utf-8")
        BuildSupport.compile_source(
            args,
            source,
            object_dir / ("PublicHeader" + str(index) + suffix),
            object_dir / ("PublicHeader" + str(index) + ".d"),
            include_audit,
            commands,
        )
        header_objects.append(object_dir / ("PublicHeader" + str(index) + suffix))

    args.library = args.build_dir / ("libEngineNextRuntime.a" if args.compiler == "clang" else "EngineNextRuntime.lib")
    args.library.unlink(missing_ok=True)
    if args.compiler == "clang":
        archive_command = [args.ar, "-rcs", args.library, *library_objects]
    else:
        archive_command = [args.lib, "/NOLOGO", "/OUT:" + str(args.library), *library_objects]
    BuildSupport.run(archive_command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in archive_command])

    targets = []
    for name, sources in APP_SOURCES.items():
        targets.append(
            link_target(
                args,
                name,
                sources,
                args.library,
                library_objects,
                object_dir,
                suffix,
                include_audit,
                commands,
            )
        )
    acceptance = (
        run_acceptance(args, targets)
        if args.run_tests
        else {
            "summaries": {},
            "clean_summaries": {},
            "trace_sha256": {},
        }
    )

    third_party_inputs = sorted(
        path.relative_to(args.repo).as_posix()
        for path in (args.repo / "engine_next/thirdparty/enet").rglob("*")
        if path.is_file()
    )
    native_inputs = sorted([
        *library_sources,
        *third_party_inputs,
        *TEST_SOURCES,
        *APP_SOURCES["next_server"],
        *APP_SOURCES["next_client"],
        *["engine_next/include/" + header for header in PUBLIC_HEADERS],
        "engine_next/Tests/TestFramework.h",
        *BUILD_SUPPORT_SOURCES,
    ])
    native_identity = {
        "compiler": args.compiler,
        "sanitize": args.sanitize,
        "inputs": {name: BuildSupport.digest(args.repo / name) for name in native_inputs},
    }
    native_key = hashlib.sha256(json.dumps(native_identity, sort_keys=True).encode("utf-8")).hexdigest()
    target_reports = []
    for target in targets:
        target_reports.append({
            "name": target["name"],
            "manifest": BuildSupport.repository_name(args.repo, target["manifest"]),
            "producer": BuildSupport.repository_name(args.repo, target["response"]),
            "link_inputs": target["link_inputs"],
            "symbol_audit": target["symbol_audit"],
            "dynamic_dependencies": target["dynamic_dependencies"],
            "artifact": target["artifact"],
            "summary": acceptance["summaries"].get(target["name"], "not_run"),
            "clean_summary": acceptance["clean_summaries"].get(target["name"], "not_run"),
            "trace_sha256": acceptance["trace_sha256"].get(target["name"]),
        })
    report = {
        "schema_version": 1,
        "target": "EngineNextRuntime",
        "native_key": native_key,
        "native_inputs": native_identity["inputs"],
        "compiler": args.compiler,
        "platform": sys.platform,
        "sanitize": args.sanitize,
        "commands": commands,
        "public_headers": PUBLIC_HEADERS,
        "public_header_objects": [str(path) for path in header_objects],
        "include_audit": include_audit,
        "archive_members": audit_archive(args, library_sources),
        "library": BuildSupport.artifact(args.repo, args.library),
        "targets": target_reports,
        "handshake": acceptance.get("handshake", "not_run"),
        "clean_handshake": acceptance.get("clean_handshake", "not_run"),
        "drain_faults": acceptance.get("drain_faults", "not_run"),
        "clean_drain_faults": acceptance.get("clean_drain_faults", "not_run"),
    }
    report_path = args.build_dir / "RuntimeBuildReport.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package = PackageRuntime.create_package(args.repo, args.build_dir)
    package_handshake = "not_run"
    if args.run_tests:
        package_handshake = (
            BuildSupport
            .run(
                [
                    sys.executable,
                    args.repo / "engine_next/Tools/RunM2Handshake.py",
                    "--server",
                    package["directory"] / targets[0]["executable"].name,
                    "--client",
                    package["directory"] / targets[1]["executable"].name,
                    "--report",
                    args.build_dir / "PackageHandshakeReport.json",
                ],
                cwd=args.repo,
                env=args.tool_environment,
            )
            .decode("utf-8")
            .strip()
        )
    report["package"] = {
        "manifest": BuildSupport.repository_name(args.repo, package["manifest"]),
        "files": package["files"],
        "godot_free_package": package["godot_free_package"],
    }
    report["package_handshake"] = package_handshake
    report["soak"] = run_soak(args, targets) if args.soak else "not_run"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": True,
                "report": BuildSupport.repository_name(args.repo, report_path),
                "manifests": [BuildSupport.repository_name(args.repo, target["manifest"]) for target in targets],
                "summaries": acceptance["summaries"],
                "clean_summaries": acceptance["clean_summaries"],
                "trace_sha256": acceptance["trace_sha256"],
                "handshake": acceptance.get("handshake", "not_run"),
                "clean_handshake": acceptance.get("clean_handshake", "not_run"),
                "package": report["package"],
                "package_handshake": package_handshake,
                "soak": report["soak"],
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
    parser.add_argument("--soak", action="store_true")
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
    import subprocess

    sys.exit(main())
