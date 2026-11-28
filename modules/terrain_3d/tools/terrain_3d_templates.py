"""Assemble a portable Windows editor with its matching built-in Terrain3D export templates."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[3]

PROBE = """extends Node

func _ready() -> void:
	var version := Engine.get_version_info()
	var result := {
		"version": version, "editor": OS.has_feature("editor"),
		"debug": OS.has_feature("debug"), "arch": Engine.get_architecture_name(),
		"terrain": ClassDB.class_exists(&"Terrain3D") and ClassDB.class_exists(&"Terrain3DRegion")
			and ClassDB.class_has_method(&"Terrain3DMaterial", &"set_material_rvt_far_stream_file")
			and RenderingServer.has_method(&"gpu_driven_terrain_create")
			and RenderingServer.has_method(&"runtime_virtual_texture_set_height_region")
			and RenderingServer.has_method(&"runtime_virtual_texture_set_material_height_source"),
	}
	if OS.has_feature("editor"):
		var image := Image.create(8, 8, false, Image.FORMAT_RGBA8)
		image.fill(Color(0.3, 0.6, 0.8, 0.5))
		result["bptc"] = image.compress(Image.COMPRESS_BPTC, Image.COMPRESS_SOURCE_GENERIC) == OK and image.get_format() == Image.FORMAT_BPTC_RGBA
	var output := FileAccess.open(OS.get_cmdline_user_args()[0], FileAccess.WRITE)
	output.store_string(JSON.stringify(result))
	output.close()
	get_tree().quit()
"""


def run(binary, arguments, project):
    result = subprocess.run(
        [str(binary), *arguments],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if result.returncode:
        raise ValueError(f"{binary.name} failed with exit code {result.returncode}\n{result.stdout}")
    return result.stdout.strip()


def probe(binary, role, project, packed):
    output = project.parent / f"probe-{role}.json"
    version_string = run(binary, ["--version"], project).splitlines()[-1]
    if role == "editor":
        arguments = ["--headless", "--path", str(project)]
    else:
        # Release templates may disable --path, --main-pack and arbitrary scripts. Start a regular game.
        shutil.copy2(packed, binary.with_suffix(".pck"))
        arguments = ["--headless"]
    run(binary, [*arguments, "--quit-after", "120", "--", str(output)], binary.parent)
    if not output.is_file():
        raise ValueError(f"{binary.name} did not run the built-in capability probe")
    info = json.loads(output.read_text(encoding="utf-8"))
    if not info["terrain"] or info["arch"] != "x86_64":
        raise ValueError(f"{binary.name} lacks the built-in x86_64 Terrain3D runtime")
    if role == "editor" and not info.get("bptc", False):
        raise ValueError(f"{binary.name} cannot encode BPTC textures for Terrain3D imports")
    if info["editor"] != (role == "editor") or (role != "editor" and info["debug"] != (role == "debug")):
        raise ValueError(f"{binary.name} is not the requested {role} build")
    build = "." + info["version"]["build"]
    build_start = version_string.rfind(build)
    if build_start < 1:
        raise ValueError(f"Unexpected Godot version: {version_string}")
    return version_string, version_string[:build_start], info["version"]["hash"]


def package(bin_dir, destination):
    if destination.exists():
        raise ValueError(f"Choose a new destination directory: {destination}")
    files = {
        "editor": bin_dir / "godot.windows.editor.x86_64.exe",
        "debug": bin_dir / "godot.windows.template_debug.x86_64.exe",
        "release": bin_dir / "godot.windows.template_release.x86_64.exe",
    }
    for binary in files.values():
        if not binary.is_file():
            raise ValueError(f"Missing build product: {binary}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".terrain3d-stage-", dir=destination.parent) as temporary:
        workspace = Path(temporary)
        inputs = workspace / "inputs"
        inputs.mkdir()
        (inputs / "_sc_").touch()
        # Probe the exact staged bytes that will be shipped, even if SCons updates bin during packaging.
        for role, binary in files.copy().items():
            staged = inputs / binary.name
            shutil.copy2(binary, staged)
            wrapper = binary.with_suffix(".console.exe")
            if wrapper.is_file():
                shutil.copy2(wrapper, inputs)
            files[role] = staged
        companions = list(bin_dir.glob("*.dll"))
        for name in ("WebView2-LICENSE.txt", "WebView2-NOTICE.txt", "tianshu-board.json", "tianshu-ui.json"):
            if (bin_dir / name).is_file():
                companions.append(bin_dir / name)
        for source in companions:
            shutil.copy2(source, inputs)

        project = workspace / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Terrain3D probe"\nrun/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (project / "probe.gd").write_text(PROBE, encoding="utf-8")
        (project / "main.tscn").write_text(
            '[gd_scene format=3]\n[ext_resource type="Script" path="res://probe.gd" id="1"]\n[node name="Probe" type="Node"]\nscript = ExtResource("1")\n',
            encoding="utf-8",
        )
        (project / "export_presets.cfg").write_text(
            '[preset.0]\nname="Probe"\nplatform="Windows Desktop"\nexport_filter="all_resources"\n', encoding="utf-8"
        )
        packed = workspace / "Probe.pck"
        versions = {"editor": probe(files["editor"], "editor", project, packed)}
        run(files["editor"], ["--headless", "--editor", "--path", str(project), "--import"], project)
        run(files["editor"], ["--headless", "--path", str(project), "--export-pack", "Probe", str(packed)], project)
        for role in ("debug", "release"):
            versions[role] = probe(files[role], role, project, packed)
        if len(set(versions.values())) != 1:
            raise ValueError(f"Editor and template build versions differ: {versions}")
        version, config, _revision = versions["editor"]
        stage = workspace / "portable"
        templates = stage / "editor_data" / "export_templates" / config
        templates.mkdir(parents=True)
        (stage / "_sc_").touch()
        for role, binary in files.items():
            target = stage / binary.name if role == "editor" else templates / f"windows_{role}_x86_64.exe"
            binary.rename(target)
            wrapper = binary.with_suffix(".console.exe")
            if wrapper.is_file():
                wrapper.rename(target.with_suffix(".console.exe"))
        for source in companions:
            staged = inputs / source.name
            # The Windows exporter looks up architecture-suffixed redistributables next to the templates.
            if source.name.lower().endswith(".x86_64.dll"):
                shutil.copy2(staged, templates)
            staged.rename(stage / source.name)
        shutil.copy2(ENGINE_ROOT / "LICENSE.txt", stage / "LICENSE.txt")
        shutil.copy2(ENGINE_ROOT / "modules/terrain_3d/LICENSE.txt", stage / "Terrain3D-LICENSE.txt")
        stage.rename(destination)
    print(f"{version} portable editor: {destination / files['editor'].name}")
    print(f"Debug and release templates: {destination / 'editor_data' / 'export_templates' / config}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination", type=Path, help="New portable editor directory that may be copied to another machine"
    )
    parser.add_argument(
        "--bin",
        type=Path,
        default=ENGINE_ROOT / "bin",
        help="SCons output containing matching editor, template_debug and template_release builds",
    )
    args = parser.parse_args()
    try:
        package(args.bin.resolve(), args.destination.resolve())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
