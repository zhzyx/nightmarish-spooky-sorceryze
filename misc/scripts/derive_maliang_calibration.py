#!/usr/bin/env python3
"""Render a fixed operator calibration sheet; no model, network or user images.

Run with the host Python and explicit --blender/--builder/--output/--module.
The host needs Pillow for the contact sheet; Blender renders the three rows.
The generated Python module contains one data literal, never executable hooks.
"""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def source_hashes(builder):
    if builder.name != "sculpt_builder.py":
        raise ValueError("The fixed builder must be named sculpt_builder.py")
    return {
        "builder_sha256": sha(builder),
        "anatomy_base_sha256": sha(builder.with_name("anatomy_base.py")),
        "anatomy_body_sha256": sha(builder.with_name("anatomy_body.py")),
        "character_detail_sha256": sha(builder.with_name("character_detail.py")),
        "organic_detail_sha256": sha(builder.with_name("organic_detail.py")),
    }


def render_row(builder_path, plan_path, output):
    import bpy  # type: ignore[import-not-found]
    from mathutils import Vector  # type: ignore[import-not-found]

    expected = source_hashes(builder_path)
    sys.path.insert(0, str(builder_path.parent))
    import sculpt_builder

    if Path(sculpt_builder.__file__).resolve() != builder_path or source_hashes(builder_path) != expected:
        raise ValueError("Calibration imported a different or changed builder")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    receipt = sculpt_builder.build(plan, output / "baseline.glb")
    # build() leaves the exact constructed objects in this scene. The override
    # changes only rendering, not the saved GLB or its measured geometry.
    scene = bpy.context.scene
    clay = bpy.data.materials.new("FixedCalibrationClay")
    clay.use_nodes = True
    shader = clay.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.48, 0.48, 0.48, 1)
    shader.inputs["Roughness"].default_value = 0.8
    scene.view_layers[0].material_override = clay
    for obj in list(scene.objects):
        if obj.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.seed = 0
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 384
    scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.12, 0.12, 0.12)
    for index, (position, power, size) in enumerate([
        ((-3, -4, 5), 450, 4),
        ((3, -2, 3), 220, 3),
        ((0, 3, 4), 300, 3),
    ]):
        light = bpy.data.lights.new("CalibrationLight" + str(index), "AREA")
        light.energy, light.size = power, size
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0, 0, 1)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    camera = bpy.data.cameras.new("CalibrationCamera")
    obj = bpy.data.objects.new(camera.name, camera)
    scene.collection.objects.link(obj)
    scene.camera = obj
    camera.type = "ORTHO"
    views = [
        ("front_body", (0, -4, 0.9), (0, 0, 0.9), 2.05),
        ("front_face", (0, -4, 1.61), (0, 0, 1.61), 0.46),
        ("right_profile", (4, 0, 1.61), (0, 0, 1.61), 0.46),
    ]
    for name, position, target, scale in views:
        obj.location = position
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
        camera.ortho_scale = scale
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
    save_json(output / "render-receipt.json", receipt)
    if source_hashes(builder_path) != expected:
        raise ValueError("Calibration runtime changed during rendering")


def derive(args):
    generator_path = Path(__file__).resolve()
    generator_sha = sha(generator_path)
    from PIL import Image, ImageDraw, __version__

    builder = args.builder.resolve(strict=True)
    expected = source_hashes(builder)
    module_path = args.module.resolve()
    if module_path.exists() and not args.replace_module:
        raise ValueError("Calibration module exists; use --replace-module for an explicit revision")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(builder.parent))
    import sculpt_builder

    if Path(sculpt_builder.__file__).resolve() != builder or source_hashes(builder) != expected:
        raise ValueError("Calibration imported a different or changed builder")
    runtime = {key: value for key, value in expected.items() if key != "builder_sha256"}
    builder_sha = expected["builder_sha256"]
    rows = [
        dict(age="adult", blend=0.0, label="ADULT: age_blend=0.0", style="realistic"),
        dict(age="elder", blend=0.65, label="ELDER DEFAULT: age_blend=0.65", style="realistic"),
        dict(age="elder", blend=1.0, label="OLDER DELTA: age_blend=1.0", style="realistic"),
        dict(
            age="adult",
            blend=0.0,
            label="STYLIZED EXAMPLE: head_ratio=6, eye_size=1.5, smile=0.6, brow=0.25",
            style="stylized",
        ),
    ]
    panels = []
    blender_versions = set()
    sheet = Image.new("RGB", (1152, len(rows) * 454 + 100), (30, 30, 30))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), "FIXED OPERATOR BASELINE - NOT A USER TARGET OR RECONSTRUCTION", fill=(255, 213, 128))
    draw.text(
        (12, 32),
        "Rows 1-3: face factors=1, head_ratio=7.5, height=1.8m, bald A-pose. Row 4 is an explicit style example.",
        fill="white",
    )
    draw.text(
        (12, 54),
        "Compare target SHAPE to these baselines; retain target identity, hair, outfit and requested style.",
        fill="white",
    )
    draw.text(
        (12, 76),
        "Each row: FRONT BODY | FRONT FACE | RIGHT PROFILE. Neutral clay, fixed orthographic cameras.",
        fill="white",
    )
    for row, specification in enumerate(rows):
        age, blend, label = specification["age"], specification["blend"], specification["label"]
        directory = output / ("row-" + str(row + 1))
        directory.mkdir()
        character = sculpt_builder.character_defaults(specification["style"])
        character.update(age=age, age_blend=blend, hair="bald")
        if specification["style"] == "stylized":
            character.update(hair="short_wavy", clothing="coverall", head_ratio=6.0)
            character["face"]["eye_size"] = 1.5
            character["detail"] = dict(
                cloth_ease=0.4,
                fold_amplitude=0.35,
                hair_volume=0.6,
                hair_sweep=0.35,
                smile=0.6,
                brow_raise=0.25,
                forehead_height=-0.15,
                pocket_size=0.0,
            )
        plan = dict(
            version=2,
            name="Fixed operator calibration " + str(row + 1),
            character=character,
            materials=[],
            regions=[],
            finish=dict(voxel_size=0.005, smooth_iterations=2, subdivision=1),
            completion=dict(mode="plausible", inferred_regions=["character"]),
        )
        sculpt_builder.validate_plan(plan)
        plan_path = directory / "plan.json"
        plan_path.write_bytes(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        )
        command = [
            str(args.blender.resolve(strict=True)),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(Path(__file__).resolve()),
            "--",
            "--render-row",
            "--builder",
            str(builder),
            "--plan",
            str(plan_path),
            "--output",
            str(directory),
        ]
        with (directory / "render.log").open("wb") as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=300)
        native_receipt = json.loads((directory / "render-receipt.json").read_text(encoding="utf-8"))
        blender_versions.add(native_receipt["blender_version"])
        require = sculpt_builder.require
        require(sha(generator_path) == generator_sha, "calibration_generator_changed")
        require(sha(builder) == builder_sha, "calibration_builder_changed")
        require(
            all(sha(builder.with_name(key.removesuffix("_sha256") + ".py")) == value for key, value in runtime.items()),
            "calibration_runtime_changed",
        )
        y = 100 + row * 454
        description = (
            " | wavy hair, coverall, explicit controls above"
            if specification["style"] == "stylized"
            else " | relative face/head factors at baseline"
        )
        draw.text((12, y + 6), label + description, fill=(255, 213, 128))
        for column, name in enumerate(("front_body", "front_face", "right_profile")):
            with Image.open(directory / (name + ".png")) as rendered:
                sheet.paste(rendered.convert("RGB"), (column * 384, y + 36))
        panels.append(
            dict(
                row=row + 1,
                label=label,
                age=age,
                age_blend=blend,
                plan_sha256=sha(plan_path),
                baseline_controls=character,
            )
        )
        print(json.dumps(dict(row=row + 1, state="rendered", plan_sha256=sha(plan_path))), flush=True)
    png = output / "operator-calibration.png"
    sheet.save(png)
    data = dict(
        schema_version=1,
        png_base64=base64.b64encode(png.read_bytes()).decode("ascii"),
        png_sha256=sha(png),
        width=sheet.width,
        height=sheet.height,
        baseline_builder_sha256=builder_sha,
        baseline_runtime_sha256=runtime,
        panels=panels,
        scope="fixed operator baseline calibration, NOT user target or reconstructed result",
    )
    # JSON is not used as Python: Python's literal spellings must be retained.
    # repr() encodes one literal only; the runtime parses its AST without exec.
    module = (
        "# SPDX-License-Identifier: CC0-1.0\n"
        "# Rendered from the pinned ordinary CC0 anatomy data using the fixed local operator.\n"
        "# Generated by misc/scripts/derive_maliang_calibration.py; no neural weights or user reference.\n"
        "# fmt: off\nCALIBRATION = " + repr(data) + "\n# fmt: on\n"
    )
    if sha(generator_path) != generator_sha:
        raise ValueError("Calibration generator changed during generation")
    with module_path.open("wb" if args.replace_module else "xb") as stream:
        stream.write(module.encode("utf-8"))
    summary = {key: value for key, value in data.items() if key != "png_base64"}
    summary.update(
        module_sha256=sha(module_path),
        generator_sha256=generator_sha,
        blender_versions=sorted(blender_versions),
        pillow_version=__version__,
        render_settings=dict(engine="CYCLES", device="CPU", samples=16, seed=0, denoising=True),
        reproducibility="Pinned source/controls/cameras; byte-identical PNG across renderer or denoiser versions is not asserted",
    )
    save_json(output / "calibration-origin.json", summary)
    print(json.dumps(dict(state="derived", module=str(args.module.resolve()), png_sha256=data["png_sha256"])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--module", type=Path)
    parser.add_argument("--replace-module", action="store_true", help="Explicitly revise an existing generated module")
    parser.add_argument("--render-row", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--plan", type=Path, help=argparse.SUPPRESS)
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(arguments)
    if args.render_row:
        if args.plan is None:
            parser.error("--plan is required for a render row")
        render_row(args.builder.resolve(strict=True), args.plan.resolve(strict=True), args.output.resolve(strict=True))
    else:
        if args.blender is None or args.module is None:
            parser.error("--blender and --module are required")
        derive(args)


if __name__ == "__main__":
    main()
