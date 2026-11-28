"""Verify native Terrain3D and automatic Windows templates using an initially empty project."""

import argparse
import hashlib
import subprocess
from pathlib import Path


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def fixture(root):
    # Identical virtual paths in different projects must still carry each project's own bytes.
    project_tag = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    write(
        root,
        "project.godot",
        """
config_version=5
[application]
config/name="Native Terrain Export Test"
run/main_scene="res://main.tscn"
""",
    )
    write(
        root,
        "base.tscn",
        """
[gd_scene format=3]
[node name="Base" type="Node"]
[node name="Terrain" type="Terrain3D" parent="."]
""",
    )
    write(
        root,
        "group.tscn",
        """
[gd_scene format=3]
[ext_resource type="PackedScene" path="res://base.tscn" id="1"]
[node name="Group" type="Node"]
[node name="Landscape" parent="." instance=ExtResource("1")]
""",
    )
    write(
        root,
        "inherited.tscn",
        """
[gd_scene format=3]
[ext_resource type="PackedScene" path="res://group.tscn" id="1"]
[ext_resource type="Terrain3DMaterial" path="res://material.tres" id="2"]
[node name="Derived" instance=ExtResource("1")]
[node name="Terrain" parent="Landscape" index="0"]
data_directory = "res://regions"
height_vt_stream_file = "res://ignored/height.svt"
material = ExtResource("2")
[editable path="Landscape"]
""",
    )
    write(
        root,
        "material.tres",
        """
[gd_resource type="Terrain3DMaterial" format=3]
[resource]
material_rvt_stream_file = "res://near.svt"
material_rvt_far_stream_file = "res://far.svt"
""",
    )
    write(
        root,
        "embedded.tscn",
        """
[gd_scene format=3]
[sub_resource type="Terrain3DMaterial" id="1"]
material_rvt_stream_file = "res://embedded.svt"
material_rvt_far_stream_file = "res://excluded.svt"
[node name="Explicit" type="Terrain3D"]
material = SubResource("1")
""",
    )
    write(
        root,
        "material_set.gd",
        """
extends Resource
@export var entries: Dictionary
""",
    )
    write(
        root,
        "material_set.tres",
        """
[gd_resource type="Resource" format=3]
[ext_resource type="Script" path="res://material_set.gd" id="1"]
[sub_resource type="Terrain3DMaterial" id="material"]
material_rvt_stream_file = "res://resource_nested.svt"
[sub_resource type="Resource" id="inner"]
script = ExtResource("1")
entries = {"preview": [SubResource("material")]}
[resource]
script = ExtResource("1")
entries = {"variants": [SubResource("inner")]}
""",
    )
    write(
        root,
        "unused.tscn",
        """
[gd_scene format=3]
[node name="Unselected" type="Terrain3D"]
height_vt_stream_file = "res://unused.svt"
data_directory = "res://unused_regions"
""",
    )
    write(
        root,
        "main.tscn",
        """
[gd_scene format=3]
[ext_resource type="Script" path="res://main.gd" id="1"]
[ext_resource type="PackedScene" path="res://inherited.tscn" id="2"]
[ext_resource type="PackedScene" path="res://embedded.tscn" id="3"]
[ext_resource type="Script" path="res://material_set.gd" id="4"]
[ext_resource type="Resource" path="res://material_set.tres" id="5"]
[ext_resource type="Resource" path="res://binary_set.res" id="6"]
[sub_resource type="Terrain3DMaterial" id="material"]
material_rvt_stream_file = "res://scene_nested.svt"
[sub_resource type="Resource" id="local_set"]
script = ExtResource("4")
entries = {"variant": [SubResource("material")]}
[node name="Verify" type="Node"]
script = ExtResource("1")
scenes = Array[PackedScene]([ExtResource("2"), ExtResource("3")])
material_sets = [ExtResource("5"), SubResource("local_set"), ExtResource("6")]
""",
    )
    write(
        root,
        "main.gd",
        """
extends Node
@export var scenes: Array[PackedScene]
@export var material_sets: Array

func _ready() -> void:
	var valid := scenes.size() == 2 and material_sets.size() == 3 and ClassDB.can_instantiate(&"Terrain3D")
	for file in ["near.svt", "far.svt", "ignored/height.svt", "embedded.svt", "explicit.svt", "resource_nested.svt", "scene_nested.svt", "embedded_scene_height.svt"]:
		var bytes := FileAccess.get_file_as_bytes("res://" + file)
		if bytes.get_string_from_utf8() != file + "@PROJECT_TAG@":
			printerr("Absent/incorrect SVT page payload: ", file)
			valid = false
	for file in ["excluded.svt", "unused.svt", "unused_regions/terrain3d_00_00.res", "regions/terrain3d_01_00.res"]:
		if FileAccess.file_exists("res://" + file):
			printerr("Unexpected exported dependency: ", file)
			valid = false
	var region := load("res://regions/terrain3d_00_00.res") as Terrain3DRegion
	if region == null or region.resource_name != "region-payload":
		printerr("Native region failed to load")
		valid = false
	if valid:
		print("TERRAIN3D_PACKAGE_OK")
	get_tree().quit(0 if valid else 1)
""".replace("@PROJECT_TAG@", project_tag),
    )
    # Runtime load() above uses a string path. get_file_deps does not include GDScript load() strings.
    write(
        root,
        "create_regions.gd",
        """
extends SceneTree
func _initialize() -> void:
	var terrain := Terrain3D.new()
	terrain.height_vt_stream_file = "res://embedded_scene_height.svt"
	var packed := PackedScene.new()
	var err := packed.pack(terrain)
	terrain.free()
	var holder := Resource.new()
	holder.set_meta("scene", packed)
	if err != OK or ResourceSaver.save(holder, "res://binary_set.res") != OK:
		quit(1)
		return
	var region := Terrain3DRegion.new()
	region.resource_name = "region-payload"
	for file in ["regions/terrain3d_00_00.res", "regions/terrain3d_01_00.res", "unused_regions/terrain3d_00_00.res"]:
		if ResourceSaver.save(region, "res://" + file) != OK:
			quit(1)
			return
	quit()
""",
    )
    for directory in ("regions", "unused_regions", "ignored"):
        (root / directory).mkdir()
    (root / "ignored" / ".gdignore").touch()
    for name in (
        "ignored/height",
        "near",
        "far",
        "embedded",
        "excluded",
        "unused",
        "explicit",
        "resource_nested",
        "scene_nested",
        "embedded_scene_height",
    ):
        file = name + ".svt"
        (root / file).write_bytes((file + project_tag).encode())
    # Unknown file types can be excluded explicitly as well as through a glob.
    selections = {
        "scenes": 'export_files=PackedStringArray("res://main.tscn")\nexclude_filter="excluded.svt,regions/terrain3d_01_00.res"',
        "exclude": 'export_files=PackedStringArray("res://unused.tscn", "res://unused_regions/terrain3d_00_00.res", "res://regions/terrain3d_01_00.res", "res://excluded.svt")\nexclude_filter=""',
        "customized": 'customized_files={"res://unused.tscn":"remove","res://unused_regions/":"remove","res://regions/":"remove","res://regions/terrain3d_00_00.res":"keep","res://excluded.svt":"remove"}\nexclude_filter=""',
    }
    presets = []
    for index, (mode, selection) in enumerate(selections.items()):
        presets.append(f"""
[preset.{index}]
name="Terrain {mode}"
platform="Windows Desktop"
export_filter="{mode}"
{selection}
include_filter="explicit.svt"
[preset.{index}.options]
binary_format/architecture="x86_64"
application/modify_resources=false
debug/export_console_wrapper=0
""")
    write(root, "export_presets.cfg", "\n".join(presets))


def run(program, args, folder, log, marker=None):
    result = subprocess.run(
        [str(program), *args],
        cwd=folder,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        encoding="utf-8",
        errors="replace",
    )
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode or "ERROR:" in result.stdout or (marker and marker not in result.stdout):
        raise ValueError(f"{program.name} failed, see {log}\n{result.stdout[-3000:]}")


def verify_ordinary_export(editor, work):
    project = work / "ordinary"
    project.mkdir()
    write(
        project,
        "project.godot",
        """
config_version=5
[application]
config/name="Ordinary text scene export"
[editor]
export/convert_text_resources_to_binary=false
""",
    )
    write(
        project,
        "probe.gd",
        """
@tool
extends Resource
func _init() -> void:
	print("ORDINARY_RESOURCE_CONSTRUCTED")
""",
    )
    write(
        project,
        "base.tscn",
        """
[gd_scene format=3]
[ext_resource type="Script" path="res://probe.gd" id="1"]
[sub_resource type="Resource" id="probe"]
script = ExtResource("1")
[node name="Root" type="Node"]
metadata/probe = SubResource("probe")
""",
    )
    write(
        project,
        "main.tscn",
        """
[gd_scene format=3]
[ext_resource type="PackedScene" path="res://base.tscn" id="1"]
[node name="Derived" instance=ExtResource("1")]
""",
    )
    write(
        project,
        "export_presets.cfg",
        """
[preset.0]
name="Pack"
platform="Windows Desktop"
export_filter="scenes"
export_files=PackedStringArray("res://main.tscn")
include_filter=""
exclude_filter=""
[preset.0.options]
binary_format/architecture="x86_64"
""",
    )
    run(editor, ["--headless", "--editor", "--path", str(project), "--import"], project, work / "ordinary-import.log")
    log = work / "ordinary-export.log"
    run(
        editor,
        ["--headless", "--path", str(project), "--export-pack", "Pack", str(work / "ordinary.pck")],
        project,
        log,
    )
    if "ORDINARY_RESOURCE_CONSTRUCTED" in log.read_text("utf-8"):
        raise ValueError(f"Export loaded a resource from an ordinary text scene; see {log}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("editor", type=Path)
    parser.add_argument(
        "workdir", type=Path, help="New directory for the project, Windows packages and individual logs"
    )
    parser.add_argument("--modes", nargs="+", choices=("debug", "release"), default=["debug", "release"])
    args = parser.parse_args()
    editor = args.editor.resolve()
    work = args.workdir.resolve()
    if work.exists():
        parser.error(f"Choose a new directory: {work}")
    project = work / "project"
    project.mkdir(parents=True)
    fixture(project)
    try:
        verify_ordinary_export(editor, work)
        run(
            editor,
            ["--headless", "--path", str(project), "--script", "res://create_regions.gd"],
            project,
            work / "regions.log",
        )
        run(editor, ["--headless", "--editor", "--path", str(project), "--import"], project, work / "import.log")
        for mode in args.modes:
            for selection in ("scenes", "exclude", "customized"):
                case = mode if selection == "scenes" else f"{mode}-{selection}"
                output = work / case
                output.mkdir()
                executable = output / "TerrainProbe.exe"
                run(
                    editor,
                    ["--headless", "--path", str(project), "--export-" + mode, "Terrain " + selection, str(executable)],
                    project,
                    work / f"export-{case}.log",
                )
                run(
                    executable,
                    ["--headless", "--quit-after", "120"],
                    output,
                    work / f"run-{case}.log",
                    "TERRAIN3D_PACKAGE_OK",
                )
                print(
                    f"{mode} {selection}: exported via default template and loaded all expected files from PCK",
                    flush=True,
                )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
