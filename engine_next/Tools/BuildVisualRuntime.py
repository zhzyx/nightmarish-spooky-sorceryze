"""Build the independent Windows visual runtime and portable FrameGraph tests."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import BuildGameplay as BuildSupport
import BuildRuntime as RuntimeSupport
import PackageVisualRuntime

CORE_SOURCES = [
    "engine_next/Rendering/PagedGeometry.cpp",
    "engine_next/Rendering/PageResidency.cpp",
    "engine_next/Rendering/Cook/GpuPagedPackage.cpp",
    "engine_next/Rendering/LodSelection.cpp",
    "engine_next/Rendering/Cook/GeometryLod.cpp",
    "engine_next/thirdparty/meshoptimizer/simplifier.cpp",
    "engine_next/thirdparty/meshoptimizer/allocator.cpp",
    "engine_next/Rendering/FrameGraph.cpp",
    "engine_next/Rendering/RenderPipeline.cpp",
    "engine_next/Rendering/RenderConfiguration.cpp",
    "engine_next/Rendering/CameraMatrices.cpp",
    "engine_next/Rendering/ShadowData.cpp",
    "engine_next/Rendering/LocalShadowData.cpp",
    "engine_next/Rendering/TemporalState.cpp",
    "engine_next/Rendering/PostProcessSettings.cpp",
    "engine_next/Rendering/ColorLut.cpp",
    "engine_next/Rendering/LightTimeline.cpp",
    "engine_next/Rendering/ReflectionSettings.cpp",
    "engine_next/Rendering/AmbientOcclusionSettings.cpp",
    "engine_next/Rendering/RayReflectionSettings.cpp",
    "engine_next/Rendering/GeometrySettings.cpp",
    "engine_next/Rendering/GeometryCulling.cpp",
    "engine_next/Rendering/GeometryScene.cpp",
    "engine_next/Rendering/VolumeSettings.cpp",
    "engine_next/Rendering/VolumeGrid.cpp",
    "engine_next/Rendering/ParticleSettings.cpp",
    "engine_next/Rendering/ParticleState.cpp",
    "engine_next/Rendering/MaterialSettings.cpp",
    "engine_next/Rendering/GlobalIlluminationSettings.cpp",
    "engine_next/Rendering/ProbeGrid.cpp",
    "engine_next/Rendering/ProbePlacement.cpp",
    "engine_next/Rendering/ShadowBounds.cpp",
    "engine_next/Rendering/Cook/GltfDecoder.cpp",
    "engine_next/Rendering/Animation.cpp",
    "engine_next/Rendering/DeformationFrame.cpp",
    "engine_next/Rendering/DeformationChanges.cpp",
    "engine_next/Rendering/MeshBasis.cpp",
    "engine_next/Rendering/Cook/ImageDecoder.cpp",
    "engine_next/Rendering/Cook/EnvironmentLighting.cpp",
    "engine_next/Rendering/Cook/EnvironmentImportance.cpp",
    "engine_next/Rendering/Cook/GpuPackage.cpp",
    "engine_next/Rendering/Cook/MeshCluster.cpp",
    "engine_next/Rendering/Cook/TextureCook.cpp",
    "engine_next/Rendering/RenderScene.cpp",
    "engine_next/Serialization/Json.cpp",
    "engine_next/Serialization/Sha256.cpp",
    "engine_next/Assets/Types.cpp",
    "engine_next/Assets/AssetManifest.cpp",
    "engine_next/Assets/SceneDocument.cpp",
    "engine_next/Assets/BlobValidator.cpp",
    "engine_next/Assets/AssetPackage.cpp",
]
ZLIB_SOURCES = [
    "engine_next/thirdparty/zlib/" + name
    for name in ("adler32.c", "crc32.c", "inflate.c", "inffast.c", "inftrees.c", "zutil.c")
]
JPEG_SOURCES = [
    "engine_next/thirdparty/libjpeg-turbo/" + name
    for name in json.loads(
        (Path(__file__).resolve().parents[1] / "thirdparty/libjpeg-turbo/UPSTREAM.json").read_text(encoding="utf-8")
    )["sources"]
]
CLIENT_SOURCES = [
    source for source in RuntimeSupport.LIBRARY_SOURCES if source not in CORE_SOURCES and not source.endswith(".c")
]
VISUAL_SOURCES = [
    "engine_next/Apps/NextVisualClientMain.cpp",
    "engine_next/Rendering/VisualRuntime.cpp",
    "engine_next/Platform/Windows/Window.cpp",
    "engine_next/Platform/Windows/RayTracingScene.cpp",
    "engine_next/Platform/Windows/GpuProbeGrid.cpp",
    "engine_next/Platform/Windows/GpuDeformation.cpp",
    "engine_next/Platform/Windows/GpuRayReflections.cpp",
    "engine_next/Platform/Windows/GpuGeometry.cpp",
    "engine_next/Platform/Windows/GpuPagedGeometry.cpp",
]
TEST_SOURCES = [
    "engine_next/Tests/Rendering/TestPagedGeometry.cpp",
    "engine_next/Tests/Rendering/TestPageResidency.cpp",
    "engine_next/Tests/Rendering/TestGpuPagedPackage.cpp",
    "engine_next/Tests/Rendering/TestLodSelection.cpp",
    "engine_next/Tests/Rendering/TestGeometryLod.cpp",
    "engine_next/Tests/RenderingTestMain.cpp",
    "engine_next/Tests/Rendering/TestFrameGraph.cpp",
    "engine_next/Tests/Rendering/TestRenderPipeline.cpp",
    "engine_next/Tests/Rendering/TestRenderConfiguration.cpp",
    "engine_next/Tests/Rendering/TestCameraMatrices.cpp",
    "engine_next/Tests/Rendering/TestShadowData.cpp",
    "engine_next/Tests/Rendering/TestLocalShadowData.cpp",
    "engine_next/Tests/Rendering/TestShadowSampling.cpp",
    "engine_next/Tests/Rendering/TestTemporalSampling.cpp",
    "engine_next/Tests/Rendering/TestTemporalState.cpp",
    "engine_next/Tests/Rendering/TestPostProcessSettings.cpp",
    "engine_next/Tests/Rendering/TestColorLut.cpp",
    "engine_next/Tests/Rendering/TestLightTimeline.cpp",
    "engine_next/Tests/Rendering/TestReflectionSettings.cpp",
    "engine_next/Tests/Rendering/TestAmbientOcclusionSettings.cpp",
    "engine_next/Tests/Rendering/TestRayReflections.cpp",
    "engine_next/Tests/Rendering/TestGeometrySettings.cpp",
    "engine_next/Tests/Rendering/TestGeometryCulling.cpp",
    "engine_next/Tests/Rendering/TestGeometryScene.cpp",
    "engine_next/Tests/Rendering/TestVolumeSettings.cpp",
    "engine_next/Tests/Rendering/TestVolumeParse.cpp",
    "engine_next/Tests/Rendering/TestVolumeMath.cpp",
    "engine_next/Tests/Rendering/TestVolumeColor.cpp",
    "engine_next/Tests/Rendering/TestVolumeTemporalMath.cpp",
    "engine_next/Tests/Rendering/TestParticles.cpp",
    "engine_next/Tests/Rendering/TestMaterialSettings.cpp",
    "engine_next/Tests/Rendering/TestMaterialLobes.cpp",
    "engine_next/Tests/Rendering/TestMaterialEnvironment.cpp",
    "engine_next/Tests/Rendering/TestGlobalIlluminationSettings.cpp",
    "engine_next/Tests/Rendering/TestProbeGrid.cpp",
    "engine_next/Tests/Rendering/TestProbePlacement.cpp",
    "engine_next/Tests/Rendering/TestProbeMath.cpp",
    "engine_next/Tests/Rendering/TestGISampling.cpp",
    "engine_next/Tests/Rendering/TestGiMaterialSampling.cpp",
    "engine_next/Tests/Rendering/TestTransparentMath.cpp",
    "engine_next/Tests/Rendering/TestSceneEntityTransforms.cpp",
    "engine_next/Tests/Rendering/TestReflectionTrace.cpp",
    "engine_next/Tests/Rendering/TestReflectionSampling.cpp",
    "engine_next/Tests/Rendering/TestExposureSampling.cpp",
    "engine_next/Tests/Rendering/TestBloomSampling.cpp",
    "engine_next/Tests/Rendering/TestShadowBounds.cpp",
    "engine_next/Tests/Rendering/TestGltfDecoder.cpp",
    "engine_next/Tests/Rendering/TestAnimation.cpp",
    "engine_next/Tests/Rendering/TestImageDecoder.cpp",
    "engine_next/Tests/Rendering/TestEnvironmentLighting.cpp",
    "engine_next/Tests/Rendering/TestEnvironmentImportance.cpp",
    "engine_next/Tests/Rendering/TestGpuPackage.cpp",
    "engine_next/Tests/Rendering/TestMeshCluster.cpp",
    "engine_next/Tests/Rendering/TestTextureCook.cpp",
]
PUBLIC_HEADERS = [
    "EngineNext/Rendering/DeformationFrame.h",
    "EngineNext/Rendering/AnimationData.h",
    "EngineNext/Rendering/PagedGeometry.h",
    "EngineNext/Rendering/PageResidency.h",
    "EngineNext/Rendering/GeometryLod.h",
    "EngineNext/Rendering/FrameGraph.h",
    "EngineNext/Rendering/MeshData.h",
    "EngineNext/Rendering/ImageData.h",
    "EngineNext/Rendering/TextureData.h",
    "EngineNext/Rendering/RenderConfiguration.h",
    "EngineNext/Rendering/CameraMatrices.h",
    "EngineNext/Rendering/ShadowData.h",
    "EngineNext/Rendering/LocalShadowData.h",
    "EngineNext/Rendering/TemporalState.h",
    "EngineNext/Rendering/PostProcessSettings.h",
    "EngineNext/Rendering/ColorLut.h",
    "EngineNext/Rendering/LightTimeline.h",
    "EngineNext/Rendering/ReflectionSettings.h",
    "EngineNext/Rendering/AmbientOcclusionSettings.h",
    "EngineNext/Rendering/RayReflectionSettings.h",
    "EngineNext/Rendering/GeometrySettings.h",
    "EngineNext/Rendering/GeometryCulling.h",
    "EngineNext/Rendering/GeometryScene.h",
    "EngineNext/Rendering/VolumeSettings.h",
    "EngineNext/Rendering/VolumeGrid.h",
    "EngineNext/Rendering/ParticleSettings.h",
    "EngineNext/Rendering/ParticleState.h",
    "EngineNext/Rendering/MaterialSettings.h",
    "EngineNext/Rendering/GlobalIlluminationSettings.h",
    "EngineNext/Rendering/ProbeGrid.h",
    "EngineNext/Rendering/ProbePlacement.h",
    "EngineNext/Rendering/RenderScene.h",
    "EngineNext/Rendering/VisualRuntime.h",
]
SYSTEM_LIBRARIES = ["d3d12", "dxgi", "dxguid", "user32", "ole32", "windowscodecs", "ws2_32", "winmm"]
SHADERS = [
    ("VSMain", "vs_6_0", "FixedMesh.vs.cso", []),
    ("PSMain", "ps_6_0", "FixedMesh.ps.cso", []),
    ("CSMain", "cs_6_0", "FixedMesh.cs.cso", ["-D", "COMPUTE_STAGE=1"]),
    ("VSMain", "vs_6_0", "Deferred.vs.cso", ["-D", "GEOMETRY_STAGE=1"]),
    ("VSMain", "vs_6_0", "AnimatedDeferred.vs.cso", ["-D", "GEOMETRY_STAGE=1", "-D", "ANIMATION_STAGE=1"]),
    ("PSMain", "ps_6_0", "Deferred.ps.cso", ["-D", "GEOMETRY_STAGE=1"]),
    ("PSMain", "ps_6_0", "MaterialDeferred.ps.cso", ["-D", "GEOMETRY_STAGE=1", "-D", "MATERIAL_EXTENSION_STAGE=1"]),
    ("FullscreenVS", "vs_6_0", "Lighting.vs.cso", []),
    ("LightingPS", "ps_6_0", "Lighting.ps.cso", []),
    (
        "LightingPS",
        "ps_6_0",
        "MaterialLighting.ps.cso",
        ["-D", "MATERIAL_EXTENSION_STAGE=1", "-D", "ENVIRONMENT_IMPORTANCE_STAGE=1"],
    ),
    ("ToneMapPS", "ps_6_0", "ToneMap.ps.cso", ["-D", "TONEMAP_STAGE=1"]),
    ("ToneMapPS", "ps_6_0", "ScreenEffects.ps.cso", ["-D", "TONEMAP_STAGE=1", "-D", "SCREEN_EFFECTS_STAGE=1"]),
    ("ShadowVS", "vs_6_0", "Shadow.vs.cso", []),
    ("ShadowPS", "ps_6_0", "Shadow.ps.cso", []),
    ("CSMain", "cs_6_0", "Temporal.cs.cso", []),
    ("HistogramBuildCS", "cs_6_0", "Histogram.cs.cso", ["-D", "HISTOGRAM_STAGE=1"]),
    ("ExposureAdaptCS", "cs_6_0", "Exposure.cs.cso", []),
    ("DownsampleCS", "cs_6_0", "BloomDown.cs.cso", []),
    ("UpsampleCS", "cs_6_0", "BloomUp.cs.cso", []),
    ("LightingPS", "ps_6_0", "ReflectionLighting.ps.cso", ["-D", "REFLECTION_STAGE=1"]),
    (
        "LightingPS",
        "ps_6_0",
        "MaterialReflectionLighting.ps.cso",
        ["-D", "REFLECTION_STAGE=1", "-D", "MATERIAL_EXTENSION_STAGE=1", "-D", "ENVIRONMENT_IMPORTANCE_STAGE=1"],
    ),
    ("ColorMipCS", "cs_6_0", "ReflectionColor.cs.cso", ["-D", "COLOR_MIP_STAGE=1"]),
    ("TraceCS", "cs_6_0", "ReflectionTrace.cs.cso", ["-D", "REFLECTION_TRACE_STAGE=1"]),
    (
        "TraceCS",
        "cs_6_0",
        "MaterialReflectionTrace.cs.cso",
        ["-D", "REFLECTION_TRACE_STAGE=1", "-D", "MATERIAL_EXTENSION_STAGE=1", "-D", "ENVIRONMENT_IMPORTANCE_STAGE=1"],
    ),
    ("CompositeCS", "cs_6_0", "ReflectionComposite.cs.cso", ["-D", "COMPOSITE_STAGE=1"]),
    ("RadianceCS", "cs_6_0", "ReflectionRadiance.cs.cso", ["-D", "RADIANCE_STAGE=1"]),
    ("TraceCS", "cs_6_5", "RayReflectionTrace.cs.cso", ["-D", "RAY_REFLECTION_TRACE=1"]),
    ("TemporalCS", "cs_6_5", "RayReflectionTemporal.cs.cso", ["-D", "RAY_REFLECTION_TEMPORAL=1"]),
    ("SpatialCS", "cs_6_5", "RayReflectionSpatial.cs.cso", ["-D", "RAY_REFLECTION_SPATIAL=1"]),
    ("CompositeCS", "cs_6_5", "RayReflectionComposite.cs.cso", ["-D", "RAY_REFLECTION_COMPOSITE=1"]),
    ("InjectCS", "cs_6_0", "VolumeInject.cs.cso", ["-D", "VOLUME_INJECT_STAGE=1"]),
    ("LightCS", "cs_6_0", "VolumeLight.cs.cso", ["-D", "VOLUME_LIGHT_STAGE=1"]),
    ("TemporalCS", "cs_6_0", "VolumeTemporal.cs.cso", []),
    ("IntegrateCS", "cs_6_0", "VolumeIntegrate.cs.cso", ["-D", "VOLUME_INTEGRATE_STAGE=1"]),
    ("CompositeCS", "cs_6_0", "VolumeComposite.cs.cso", []),
    ("VSMain", "vs_6_0", "Transparent.vs.cso", []),
    ("PSMain", "ps_6_0", "Transparent.ps.cso", []),
    (
        "PSMain",
        "ps_6_0",
        "MaterialTransparent.ps.cso",
        ["-D", "MATERIAL_EXTENSION_STAGE=1", "-D", "ENVIRONMENT_IMPORTANCE_STAGE=1"],
    ),
    ("LightingPS", "ps_6_0", "GiLighting.ps.cso", ["-D", "ENGINE_NEXT_GI=1"]),
    (
        "LightingPS",
        "ps_6_0",
        "GiMaterialLighting.ps.cso",
        ["-D", "ENGINE_NEXT_GI=1", "-D", "MATERIAL_EXTENSION_STAGE=1", "-D", "ENVIRONMENT_IMPORTANCE_STAGE=1"],
    ),
    ("LightingPS", "ps_6_0", "GiReflectionLighting.ps.cso", ["-D", "ENGINE_NEXT_GI=1", "-D", "REFLECTION_STAGE=1"]),
    (
        "LightingPS",
        "ps_6_0",
        "GiMaterialReflectionLighting.ps.cso",
        [
            "-D",
            "ENGINE_NEXT_GI=1",
            "-D",
            "REFLECTION_STAGE=1",
            "-D",
            "MATERIAL_EXTENSION_STAGE=1",
            "-D",
            "ENVIRONMENT_IMPORTANCE_STAGE=1",
        ],
    ),
    ("PSMain", "ps_6_0", "GiTransparent.ps.cso", ["-D", "ENGINE_NEXT_GI=1"]),
    (
        "PSMain",
        "ps_6_0",
        "GiMaterialTransparent.ps.cso",
        ["-D", "ENGINE_NEXT_GI=1", "-D", "MATERIAL_EXTENSION_STAGE=1", "-D", "ENVIRONMENT_IMPORTANCE_STAGE=1"],
    ),
    ("PrepareCS", "cs_6_5", "GiPrepare.cs.cso", []),
    ("RelocateCS", "cs_6_5", "GiRelocate.cs.cso", []),
    ("TraceCS", "cs_6_5", "GiTrace.cs.cso", []),
    ("UpdateCS", "cs_6_5", "GiIntegrate.cs.cso", []),
    ("CullCS", "cs_6_0", "GeometryCull.cs.cso", []),
    ("CullCS", "cs_6_0", "GeometryPagedCull.cs.cso", ["-D", "PAGED_GEOMETRY_STAGE=1"]),
    ("CopyDepthCS", "cs_6_0", "GeometryHiZCopy.cs.cso", []),
    ("ReduceDepthCS", "cs_6_0", "GeometryHiZReduce.cs.cso", []),
    ("DepthVS", "vs_6_0", "GeometryDepth.vs.cso", []),
    ("DepthPS", "ps_6_0", "GeometryDepth.ps.cso", []),
    ("AmbientOcclusionCS", "cs_6_0", "AmbientOcclusion.cs.cso", []),
    ("AmbientBlurCS", "cs_6_0", "AmbientOcclusionBlur.cs.cso", []),
]
SHADERS += [
    (entry, profile, "Ao" + name, [*definitions, "-D", "AMBIENT_OCCLUSION_STAGE=1"])
    for entry, profile, name, definitions in SHADERS
    if name.endswith("Lighting.ps.cso")
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def object_name(source, suffix):
    suffix_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    return Path(source).stem + "-" + suffix_hash + suffix


def developer_environment(environment):
    """Import the installed x64 toolchain into this child process only."""
    if all(shutil.which(tool, path=environment.get("PATH")) for tool in ("cl", "link", "lib", "dumpbin")):
        return environment
    base = Path(environment.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    vswhere = base / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.is_file():
        raise ValueError("MSVC tools unavailable and vswhere.exe was not found")
    installation = (
        BuildSupport
        .run(
            [
                vswhere,
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            env=environment,
        )
        .decode("utf-8")
        .strip()
    )
    script = Path(installation) / "Common7/Tools/VsDevCmd.bat"
    if not installation or not script.is_file() or '"' in str(script):
        raise ValueError("No installed x64 MSVC developer environment")
    command = f'call "{script}" -no_logo -arch=x64 -host_arch=x64 >nul && set'
    # cmd parses the /c tail itself; list2cmdline escaping that tail adds literal backslashes.
    command_line = subprocess.list2cmdline([environment.get("COMSPEC", "cmd.exe")]) + ' /d /s /c "' + command + '"'
    process = subprocess.run(
        command_line, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True
    )
    output = process.stdout
    result = {name.upper(): value for name, value in environment.items()}
    for line in output.decode("utf-8", errors="replace").splitlines():
        name, separator, value = line.partition("=")
        if separator and name and not name.startswith("="):
            result[name.upper()] = value
    result["VSLANG"] = "1033"
    return result


def find_dxc(environment, explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise ValueError("Explicit DXC executable was not found")
        return path
    candidate = shutil.which("dxc", path=environment.get("PATH"))
    if candidate:
        return Path(candidate)
    sdk = Path(
        environment.get("WindowsSdkDir") or environment.get("WINDOWSSDKDIR") or "C:/Program Files (x86)/Windows Kits/10"
    )
    for directory in sorted((sdk / "bin").glob("10.*"), reverse=True):
        candidate = directory / "x64/dxc.exe"
        if candidate.is_file():
            return candidate
    raise ValueError("DXC was not found in the Windows SDK; supply --dxc")


def configure_tools(args):
    args.tool_environment = os.environ.copy()
    args.tool_environment["VSLANG"] = "1033"
    if args.compiler == "msvc":
        args.tool_environment = developer_environment(args.tool_environment)
        tools = {name: name for name in ("cl", "link", "lib", "dumpbin")}
    else:
        tools = {"clangxx": "clang++", "ar": "ar", "nm": "nm"}
        tools["otool" if sys.platform == "darwin" else "ldd"] = "otool" if sys.platform == "darwin" else "ldd"
    for attribute, name in tools.items():
        value = shutil.which(name, path=args.tool_environment.get("PATH"))
        if not value:
            raise ValueError("Missing compiler tool: " + name)
        setattr(args, attribute, value)


def parse_includes(args, output, dependency):
    root = args.repo.resolve()
    if args.compiler == "clang":
        text = dependency.read_text(encoding="utf-8").replace("\\\n", " ")
        separator = re.search(r":\s", text)
        if separator is None:
            raise ValueError("Clang dependency file has no target separator")
        body = text[separator.end() :]
        words = re.findall(r"(?:\\.|[^\s\\])+", body)
        paths = [Path(re.sub(r"\\([ #\\])", r"\1", value).replace("$$", "$")) for value in words]
        paths = [path if path.is_absolute() else root / path for path in paths]
    else:
        if dependency is None or not dependency.is_file():
            raise ValueError("MSVC source-dependency output is missing")
        data = json.loads(dependency.read_text(encoding="utf-8-sig"))
        data = data.get("Data", {})
        source = data.get("Source")
        includes = data.get("Includes")
        if (
            not isinstance(source, str)
            or not source
            or not isinstance(includes, list)
            or (not includes and not source.endswith(".c"))
        ):
            raise ValueError("MSVC source-dependency output is incomplete")
        if any(not isinstance(path, str) or not path for path in includes):
            raise ValueError("MSVC source-dependency output contains invalid includes")
        paths = [Path(source), *[Path(path) for path in includes]]
    includes = []
    for path in paths:
        name = BuildSupport.repository_name(root, path)
        if name is not None and not name.startswith(("ai_core/", "engine_next/", "build/engine_next/")):
            raise ValueError("Undeclared repository include: " + name)
        includes.append(str(path.resolve()))
    return sorted(set(includes))


def compile_sources(args, sources, commands, include_audit):
    objects = []
    suffix = ".obj" if args.compiler == "msvc" else ".o"
    for source in sources:
        source_path = args.repo / source if isinstance(source, str) else source
        name = BuildSupport.repository_name(args.repo, source_path)
        output = args.build_dir / "Objects" / object_name(name, suffix)
        dependency = output.with_suffix(".json" if args.compiler == "msvc" else ".d")
        if dependency.exists():
            dependency.unlink()
        command = RuntimeSupport.compiler_command_with_enet(args, source_path, output, dependency)
        if args.compiler == "msvc":
            command[command.index("/EHsc")] = "/EHs-c-"
            command.remove("/showIncludes")
            command[command.index("/c") : command.index("/c")] = [
                "/D_HAS_EXCEPTIONS=0",
                "/sourceDependencies",
                str(dependency),
                "/DNOMINMAX",
                "/DWIN32_LEAN_AND_MEAN",
                "/Zi",
                "/F" + "d" + str(output.with_suffix(".pdb")),
            ]
        raw = BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
        include_audit[name] = parse_includes(args, raw, dependency)
        commands.append([str(value) for value in command])
        objects.append(output)
    return objects


def compile_c_source(args, source, output, commands, include_audit):
    dependency = output.with_suffix(".json" if args.compiler == "msvc" else ".d")
    if args.compiler == "msvc":
        command = [
            args.cl,
            "/nologo",
            "/TC",
            "/std:c17",
            "/O2",
            "/W4",
            "/WX",
            "/wd4100",
            "/wd4245",
            "/wd5287",
            "/fp:strict",
            "/D_WINSOCK_DEPRECATED_NO_WARNINGS",
            "/sourceDependencies",
            str(dependency),
            "/I",
            args.repo,
            "/I",
            args.repo / "engine_next/thirdparty/enet/include",
            "/I",
            args.repo / "engine_next/thirdparty/libjpeg-turbo/src",
            "/DNO_GETENV",
            "/c",
            args.repo / source,
            "/F" + "o" + str(output),
        ]
    else:
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
            args.repo / "engine_next/thirdparty/enet/include",
            "-I",
            args.repo / "engine_next/thirdparty/libjpeg-turbo/src",
            "-DNO_GETENV",
            "-D_POSIX_C_SOURCE=200809L",
            "-MMD",
            "-MF",
            dependency,
            "-c",
            args.repo / source,
            "-o",
            output,
        ]
        if args.sanitize:
            command.extend(["-fsanitize=address,undefined", "-fno-omit-frame-pointer"])
    raw = BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
    include_audit[source] = parse_includes(args, raw, dependency)
    commands.append([str(value) for value in command])


def create_archive(args, objects, commands):
    library = args.build_dir / ("EngineNextRendering.lib" if args.compiler == "msvc" else "libEngineNextRendering.a")
    if library.exists():
        library.unlink()
    command = (
        [args.lib, "/NOLOGO", "/OUT:" + str(library), *objects]
        if args.compiler == "msvc"
        else [args.ar, "-rcs", library, *objects]
    )
    BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in command])
    listing = [args.lib, "/NOLOGO", "/LIST", library] if args.compiler == "msvc" else [args.ar, "-t", library]
    raw = BuildSupport.run(listing, cwd=args.repo, env=args.tool_environment).decode("utf-8", errors="replace")
    suffix = ".obj" if args.compiler == "msvc" else ".o"
    members = [Path(line.strip()).name for line in raw.splitlines() if line.strip().endswith(suffix)]
    if sorted(members) != sorted(path.name for path in objects):
        raise ValueError("Rendering archive contains unexpected members")
    return library, members


def audit_dependencies(args, executable, visual):
    if args.compiler != "msvc":
        args.executable = executable
        return BuildSupport.audit_dynamic_dependencies(args)
    output = BuildSupport.run([args.dumpbin, "/NOLOGO", "/DEPENDENTS", executable], env=args.tool_environment)
    dependencies = sorted(set(re.findall(r"([A-Za-z0-9_.-]+\.dll)", output.decode("utf-8", errors="replace"), re.I)))
    allowed = {
        "kernel32.dll",
        "msvcp140.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "ucrtbase.dll",
        "ole32.dll",
        "windowscodecs.dll",
        "ws2_32.dll",
        "winmm.dll",
    }
    if visual:
        allowed.update({"d3d12.dll", "dxgi.dll", "user32.dll"})
    unexpected = [
        name for name in dependencies if name.lower() not in allowed and not name.lower().startswith("api-ms-win-")
    ]
    if unexpected:
        raise ValueError("Unexpected dynamic dependencies: " + ", ".join(unexpected))
    return dependencies


def audit_symbols(args, inputs):
    for path in inputs:
        command = [args.dumpbin, "/NOLOGO", "/SYMBOLS", path] if args.compiler == "msvc" else [args.nm, path]
        output = BuildSupport.run(command, env=args.tool_environment).decode("utf-8", errors="replace")
        if args.compiler == "msvc":
            output = "\n".join(line for line in output.splitlines() if "| ??_C@" not in line)
        if any(token in output for token in BuildSupport.FORBIDDEN_SYMBOLS):
            raise ValueError("Forbidden symbol in " + path.name)
    return {"forbidden": [], "audited_inputs": [path.name for path in inputs]}


def link_target(args, name, objects, library, core_objects, commands, visual=False):
    executable = args.build_dir / (name + ".exe" if args.compiler == "msvc" else name)
    response = args.build_dir / (name + "Link.rsp")
    libraries = SYSTEM_LIBRARIES if visual else (["ole32", "windowscodecs"] if args.compiler == "msvc" else [])
    values = [*objects, library]
    if args.compiler == "msvc":
        values.extend([name + ".lib" for name in libraries])
        values.extend([
            "/OUT:" + str(executable),
            "/INCREMENTAL:NO",
            "/DEBUG",
            "/PDB:" + str(executable.with_suffix(".pdb")),
        ])
        command = [args.link, "/NOLOGO", "@" + str(response)]
    else:
        values.extend(["-o", executable])
        if args.sanitize:
            values.append("-fsanitize=address,undefined")
        command = [args.clangxx, "@" + str(response)]
    response.write_text(
        BuildSupport.quoted_response(values, windows=args.compiler == "msvc"), encoding="utf-8", newline="\n"
    )
    BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
    commands.append([str(value) for value in command])
    manifest = {
        "schema_version": 1,
        "target": "next_visual_client" if visual else "next_rendering_tests",
        "producer": {"kind": "linker_response", **BuildSupport.artifact(args.repo, response)},
        "objects": [BuildSupport.artifact(args.repo, path) for path in [*core_objects, *objects]],
        "libraries": [BuildSupport.artifact(args.repo, library)],
        "runtime_files": [BuildSupport.artifact(args.repo, executable)],
        "system_libraries": ["c++", *libraries],
    }
    manifest_path = args.build_dir / (name + "LinkManifest.json")
    write_json(manifest_path, manifest)
    result = {
        "name": name,
        "artifact": BuildSupport.artifact(args.repo, executable),
        "manifest": BuildSupport.repository_name(args.repo, manifest_path),
        "manifest_sha256": BuildSupport.digest(manifest_path),
        "symbol_audit": audit_symbols(args, [*core_objects, *objects, executable]),
        "dynamic_dependencies": audit_dependencies(args, executable, visual),
    }
    checker = args.repo / "tools/check_engine_next_contract.py"
    command = [sys.executable, checker, "--repo", args.repo, "--require-sources", "--link-manifest", manifest_path]
    result["contract"] = json.loads(BuildSupport.run(command, cwd=args.repo))
    return result


def compile_shaders(args, commands):
    compiler = find_dxc(args.tool_environment, args.dxc)
    results = []
    for entry, profile, name, definitions in SHADERS:
        source = (
            args.repo
            / "engine_next/Rendering/Shaders"
            / (
                "FixedMesh.hlsl"
                if name.startswith("FixedMesh")
                else "AmbientOcclusion.hlsl"
                if name.startswith("AmbientOcclusion")
                else "GeometryCull.hlsl"
                if name in ("GeometryCull.cs.cso", "GeometryPagedCull.cs.cso")
                else "GeometryHiZ.hlsl"
                if name.startswith("GeometryHiZ")
                else "GeometryDepth.hlsl"
                if name.startswith("GeometryDepth")
                else "Transparent.hlsl"
                if name.startswith(("Transparent", "MaterialTransparent", "GiTransparent", "GiMaterialTransparent"))
                else "GI.hlsl"
                if name in ("GiPrepare.cs.cso", "GiRelocate.cs.cso", "GiTrace.cs.cso", "GiIntegrate.cs.cso")
                else "VolumeTemporal.hlsl"
                if name == "VolumeTemporal.cs.cso"
                else "VolumeComposite.hlsl"
                if name == "VolumeComposite.cs.cso"
                else "Volume.hlsl"
                if name.startswith("Volume")
                else "Reflection.hlsl"
                if (name.startswith("Reflection") and name != "ReflectionLighting.ps.cso")
                or name == "MaterialReflectionTrace.cs.cso"
                else "RayReflections.hlsl"
                if name.startswith("RayReflection")
                else "Shadow.hlsl"
                if name.startswith("Shadow")
                else "Exposure.hlsl"
                if name.startswith(("Histogram", "Exposure"))
                else "Bloom.hlsl"
                if name.startswith("Bloom")
                else "TemporalAA.hlsl"
                if name.startswith("Temporal")
                else "Deferred.hlsl"
            )
        )
        output = args.build_dir / name
        command = [compiler, "-E", entry, "-T", profile, "-Ges", "-WX", "-O3", "-Fo", output, *definitions, source]
        BuildSupport.run(command, cwd=args.repo, env=args.tool_environment)
        commands.append([str(value) for value in command])
        if not output.is_file() or output.stat().st_size == 0:
            raise ValueError("DXC produced no shader: " + name)
        results.append({"entry": entry, "profile": profile, **BuildSupport.artifact(args.repo, output)})
    return results, {
        "sha256": BuildSupport.digest(compiler),
        "version": BuildSupport.run([compiler, "--version"]).decode("utf-8", errors="replace").strip(),
    }


def build(args):
    args.repo = args.repo.resolve()
    args.build_dir = args.build_dir.resolve()
    args.build_dir.relative_to(args.repo / "build/engine_next")
    if args.compiler != "msvc" and not args.tests_only:
        raise ValueError("The D3D12 visual client requires MSVC on Windows; use --tests-only for portable tests")
    args.build_dir.mkdir(parents=True, exist_ok=True)
    (args.build_dir / "Objects").mkdir(exist_ok=True)
    configure_tools(args)
    if args.compiler == "clang":
        args.clang = shutil.which("clang", path=args.tool_environment.get("PATH"))
    commands = []
    include_audit = {}
    core_objects = compile_sources(args, CORE_SOURCES, commands, include_audit)
    for source in [*ZLIB_SOURCES, *JPEG_SOURCES, "engine_next/Rendering/Cook/JpegValidation.c"]:
        output = args.build_dir / "Objects" / object_name(source, ".obj" if args.compiler == "msvc" else ".o")
        compile_c_source(args, source, output, commands, include_audit)
        core_objects.append(output)
    library, members = create_archive(args, core_objects, commands)
    header_sources = []
    headers = PUBLIC_HEADERS[:-1] if args.tests_only else PUBLIC_HEADERS
    for index, header in enumerate(headers):
        source = args.build_dir / "Objects" / ("PublicHeader" + str(index) + ".cpp")
        source.write_text('#include "' + header + '"\n', encoding="utf-8", newline="\n")
        header_sources.append(source)
    compile_sources(args, header_sources, commands, include_audit)
    test_objects = compile_sources(args, TEST_SOURCES, commands, include_audit)
    tests = link_target(args, "next_rendering_tests", test_objects, library, core_objects, commands)
    summary = "not_run"
    if args.run_tests:
        summary = (
            BuildSupport
            .run([args.repo / tests["artifact"]["path"]], cwd=args.build_dir, env=args.tool_environment)
            .decode("utf-8")
            .strip()
        )
    targets = [tests]
    shaders = []
    dxc = None
    if not args.tests_only:
        shaders, dxc = compile_shaders(args, commands)
        visual_objects = compile_sources(args, [*CLIENT_SOURCES, *VISUAL_SOURCES], commands, include_audit)
        for source in RuntimeSupport.ENET_SOURCES:
            if source.endswith("/unix.c"):
                continue
            output = args.build_dir / "Objects" / object_name(source, ".obj")
            compile_c_source(args, source, output, commands, include_audit)
            visual_objects.append(output)
        targets.append(
            link_target(args, "next_visual_client", visual_objects, library, core_objects, commands, visual=True)
        )
    native_files = sorted({
        *CORE_SOURCES,
        *ZLIB_SOURCES,
        *JPEG_SOURCES,
        "engine_next/Rendering/Cook/JpegValidation.c",
        *TEST_SOURCES,
        *([] if args.tests_only else CLIENT_SOURCES + RuntimeSupport.ENET_SOURCES),
        *([] if args.tests_only else VISUAL_SOURCES),
        *["engine_next/include/" + name for name in headers],
        "engine_next/Tests/TestFramework.h",
        "engine_next/Tools/BuildGameplay.py",
        "engine_next/Tools/BuildRuntime.py",
        *[
            path.relative_to(args.repo).as_posix()
            for name in ("enet", "zlib", "libjpeg-turbo", "meshoptimizer")
            for path in (args.repo / "engine_next/thirdparty" / name).rglob("*")
            if path.is_file()
        ],
        "engine_next/Tools/BuildVisualRuntime.py",
        "engine_next/Tools/PackageVisualRuntime.py",
        "tools/check_engine_next_contract.py",
        "tools/engine_next_contract.json",
        *(
            []
            if args.tests_only
            else [
                "engine_next/Rendering/Shaders/FixedMesh.hlsl",
                "engine_next/Rendering/Shaders/Deferred.hlsl",
                "engine_next/Rendering/Shaders/AmbientOcclusion.hlsl",
                "engine_next/Rendering/Shaders/AmbientOcclusionMath.hlsli",
                "engine_next/Rendering/Shaders/ScreenEffects.hlsli",
                "engine_next/Rendering/Shaders/Shadow.hlsl",
                "engine_next/Rendering/Shaders/ShadowSampling.hlsli",
                "engine_next/Rendering/Shaders/ShadowReceiverPlane.hlsli",
                "engine_next/Rendering/Shaders/TemporalAA.hlsl",
                "engine_next/Rendering/Shaders/TemporalSampling.hlsli",
                "engine_next/Rendering/Shaders/Exposure.hlsl",
                "engine_next/Rendering/Shaders/ExposureMath.hlsli",
                "engine_next/Rendering/Shaders/Bloom.hlsl",
                "engine_next/Rendering/Shaders/BloomSampling.hlsli",
                "engine_next/Rendering/Shaders/Reflection.hlsl",
                "engine_next/Rendering/Shaders/RayReflections.hlsl",
                "engine_next/Rendering/Shaders/RayReflectionSampling.hlsli",
                "engine_next/Rendering/Shaders/GeometryVisibility.hlsli",
                "engine_next/Rendering/Shaders/GeometryCull.hlsl",
                "engine_next/Rendering/Shaders/GeometryHiZ.hlsl",
                "engine_next/Rendering/Shaders/GeometryDepth.hlsl",
                "engine_next/Rendering/Shaders/ReflectionTrace.hlsli",
                "engine_next/Rendering/Shaders/ReflectionSampling.hlsli",
                "engine_next/Rendering/Shaders/Volume.hlsl",
                "engine_next/Rendering/Shaders/VolumeCommon.hlsli",
                "engine_next/Rendering/Shaders/VolumeMath.hlsli",
                "engine_next/Rendering/Shaders/VolumeColor.hlsli",
                "engine_next/Rendering/Shaders/VolumeTemporal.hlsl",
                "engine_next/Rendering/Shaders/VolumeTemporalMath.hlsli",
                "engine_next/Rendering/Shaders/VolumeComposite.hlsl",
                "engine_next/Rendering/Shaders/VolumeSampling.hlsli",
                "engine_next/Rendering/Shaders/TransparentMath.hlsli",
                "engine_next/Rendering/Shaders/MaterialLobes.hlsli",
                "engine_next/Rendering/Shaders/MaterialEnvironment.hlsli",
                "engine_next/Rendering/Shaders/MaterialEnvironmentLighting.hlsli",
                "engine_next/Rendering/Shaders/EnvironmentImportance.hlsli",
                "engine_next/Rendering/Shaders/ProbeMath.hlsli",
                "engine_next/Rendering/Shaders/Transparent.hlsl",
                "engine_next/Rendering/Shaders/GI.hlsl",
                "engine_next/Rendering/Shaders/ProbePlacementMath.hlsli",
                "engine_next/Rendering/Shaders/GILighting.hlsli",
                "engine_next/Rendering/Shaders/GISampling.hlsli",
                "engine_next/Rendering/Shaders/GISamplingMath.hlsli",
                "engine_next/Rendering/Shaders/GiMaterialSampling.hlsli",
                "engine_next/Rendering/Shaders/GiReceiver.hlsli",
                "engine_next/Rendering/Shaders/RayTracingScene.hlsli",
                "engine_next/Rendering/Shaders/ProbeMath.hlsli",
            ]
        ),
        *[
            name
            for values in include_audit.values()
            for path in values
            if (name := BuildSupport.repository_name(args.repo, path)) and name.startswith(("engine_next/", "ai_core/"))
        ],
    })
    native_identity = {
        "inputs": {path: BuildSupport.digest(args.repo / path) for path in native_files},
        "compiler": args.compiler,
        "sanitize": args.sanitize,
        "compiler_sha256": BuildSupport.digest(args.cl if args.compiler == "msvc" else args.clangxx),
        "dxc": dxc,
    }
    report = {
        "schema_version": 1,
        "target": "EngineNextVisualRuntime",
        "platform": sys.platform,
        "compiler": args.compiler,
        "sanitize": args.sanitize,
        "native_key": hashlib.sha256(json.dumps(native_identity, sort_keys=True).encode()).hexdigest(),
        "native_identity": native_identity,
        "commands": commands,
        "include_audit": include_audit,
        "archive_members": members,
        "targets": targets,
        "shaders": shaders,
        "test_summary": summary,
    }
    report_path = args.build_dir / "VisualBuildReport.json"
    write_json(report_path, report)
    if not args.tests_only:
        package = PackageVisualRuntime.create_package(args.repo, args.build_dir)
        report["package"] = {
            "manifest": BuildSupport.repository_name(args.repo, package["manifest"]),
            "files": package["files"],
        }
        if args.run_tests:
            executable = package["directory"] / "next_visual_client.exe"
            report["clean_help"] = (
                BuildSupport
                .run([executable, "--help"], cwd=package["directory"], env=args.tool_environment)
                .decode("utf-8")
                .strip()
            )
    write_json(report_path, report)
    print(
        json.dumps(
            {"passed": True, "report": BuildSupport.repository_name(args.repo, report_path), "test_summary": summary},
            indent=2,
        )
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--compiler", choices=("msvc", "clang"), default="msvc" if os.name == "nt" else "clang")
    parser.add_argument("--tests-only", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--dxc")
    args = parser.parse_args(argv)
    if args.sanitize and args.compiler != "clang":
        parser.error("--sanitize requires clang")
    if not args.build_dir.is_absolute():
        args.build_dir = args.repo / args.build_dir
    try:
        build(args)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
