"""Verify editor-baked BC7 terrain with missing channels in a real Windows release template.

Usage: python material_svt_compatibility.py EDITOR RELEASE_TEMPLATE NEW_DIRECTORY
"""

import argparse
import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path


def write_texture(path, rgb):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0)
    scan = bytes([0]) + bytes([*rgb, 150]) * 64
    path.write_bytes(
        bytes.fromhex("89504e470d0a1a0a")
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(scan * 64))
        + chunk(b"IEND", b"")
    )
    path.with_suffix(".png.import").write_text(
        '[remap]\nimporter="texture"\ntype="CompressedTexture2D"\n[params]\ncompress/mode=2\n'
        "compress/high_quality=true\ncompress/normal_map=2\nmipmaps/generate=true\n",
        encoding="utf8",
    )


def prepare(project):
    project.mkdir(parents=True)
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Terrain3D SVT Compatibility"\n'
        'run/main_scene="res://main.tscn"\n[display]\nwindow/size/no_focus=true\n',
        encoding="utf8",
    )
    shutil.copy2(Path(__file__).with_suffix(".gd"), project / "main.gd")
    (project / "main.tscn").write_text(
        '[gd_scene format=3]\n[ext_resource type="Script" path="res://main.gd" id="1"]\n'
        '[node name="Compatibility" type="Node3D"]\nscript=ExtResource("1")\n',
        encoding="utf8",
    )
    (project / "export_presets.cfg").write_text(
        '[preset.0]\nname="Check"\nplatform="Windows Desktop"\nexport_filter="all_resources"\n'
        'include_filter="*.svt"\nexclude_filter=""\n[preset.0.options]\nbinary_format/architecture="x86_64"\n',
        encoding="utf8",
    )
    for name, rgb in [("source", (180, 60, 45)), ("changed", (30, 200, 110)), ("normal", (128, 128, 255))]:
        write_texture(project / (name + ".png"), rgb)
    for name, source in [("assets", "source"), ("changed", "changed")]:
        (project / (name + ".tres")).write_text(
            '[gd_resource type="Terrain3DAssets" format=3]\n'
            f'[ext_resource type="Texture2D" path="res://{source}.png" id="1"]\n'
            '[ext_resource type="Texture2D" path="res://normal.png" id="2"]\n'
            '[sub_resource type="Terrain3DTextureAsset" id="a"]\nalbedo_texture=ExtResource("1")\n'
            '[sub_resource type="Terrain3DTextureAsset" id="b"]\nid=1\nnormal_texture=ExtResource("2")\n'
            '[resource]\ntexture_list=Array[Terrain3DTextureAsset]([SubResource("a"),SubResource("b")])\n',
            encoding="utf8",
        )


def verify(editor, template, work):
    work.mkdir()
    project = work / "project"
    prepare(project)
    game = work / "Compatibility.exe"

    def run(name, args, stage=""):
        env = dict(os.environ, T3D_COMPAT_STAGE=stage)
        log = work / (name + ".log")
        with log.open("wb") as stream:
            result = subprocess.run(args, cwd=work, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=240)
        content = log.read_text("utf8", errors="replace")
        if result.returncode or "ERROR:" in content or (stage and f"T3D_COMPAT {stage} failures=0" not in content):
            raise RuntimeError(f"{name} failed, see {log}")
        print(name, log, flush=True)

    run("import", [editor, "--headless", "--editor", "--path", project, "--import"])
    display = [
        "--rendering-method",
        "forward_plus",
        "--rendering-driver",
        "vulkan",
        "--windowed",
        "--resolution",
        "640x360",
        "--position",
        "-28000,-28000",
        "--fixed-fps",
        "60",
        "--quit-after",
        "1500",
    ]
    run("editor-bake", [editor, "--editor", "--path", project, *display, "res://main.tscn"], "bake")
    run("pack", [editor, "--headless", "--path", project, "--export-pack", "Check", game.with_suffix(".pck")])
    shutil.copy2(template, game)
    for stage in ["unchanged", "changed"]:
        run("release-" + stage, [game, *display], stage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("editor", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("directory", type=Path, help="New scratch directory")
    args = parser.parse_args()
    verify(args.editor.resolve(), args.template.resolve(), args.directory.resolve())
