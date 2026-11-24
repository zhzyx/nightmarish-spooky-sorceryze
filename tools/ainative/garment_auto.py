"""Automatic, evidence-bound garment recognition for the Workbench node.

The model is inspected locally, a bounded set of connected components is rendered
with exact IDs, and one vision request may select only those attached components.
No triangle IDs, hidden geometry, human confirmation or visual acceptance are
invented. The source GLB is never overwritten and no request is retried here.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from extensions import canonical, require
from garment_inventory import request_inventory
from garment_split import GarmentSource, spec_from_inventory, write_component_preview

DEFAULT_COMPONENT_LIMIT = 4
MAX_COMPONENT_LIMIT = 24
RENDER_VIEWS = ("front", "right", "back", "left", "top")
COMPONENT_VIEWS = ("front", "back")


def _render(source, candidates, directory, godot_path, render_script, triangle_id_model=None, triangle_id_model_high=None, camera_bounds=None):
    godot_path = Path(godot_path).expanduser().resolve()
    render_script = Path(render_script).expanduser().resolve()
    require(godot_path.is_file() and render_script.is_file(), "review_render_failed")
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        '[application]\nconfig/name="Private garment recognition"\n', encoding="utf-8"
    )
    output = directory / "renders"
    request = directory / "render-request.json"
    script_sha256 = hashlib.sha256(render_script.read_bytes()).hexdigest()
    request.write_text(
        canonical(
            dict(
                model=str(source),
                output=str(output),
                yaw_degrees=0.0,
                viewport_size=768,
                camera_bounds=camera_bounds,
                render_views=[dict(view=view, region="full_subject", direction=view) for view in RENDER_VIEWS],
                components=[dict(component_id=item["component_id"], model=item["path"]) for item in candidates],
                triangle_id_model=str(triangle_id_model or ""),
                triangle_id_model_high=str(triangle_id_model_high or ""),
                script_sha256=script_sha256,
            )
        ),
        encoding="utf-8",
    )
    arguments = [
        str(godot_path),
        "--path",
        str(project),
        "--script",
        str(render_script),
        "--rendering-method",
        "gl_compatibility",
        "--audio-driver",
        "Dummy",
        "--",
        str(request),
    ]
    try:
        with (directory / "render.log").open("xb") as log:
            completed = subprocess.run(
                arguments,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
    except subprocess.TimeoutExpired:
        require(False, "review_render_failed")
    require(completed.returncode == 0, "review_render_failed")
    report_path = output / "views.json"
    require(report_path.is_file(), "review_render_failed")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    require(
        report.get("model_sha256") == hashlib.sha256(source.read_bytes()).hexdigest()
        and report.get("script_sha256") == script_sha256,
        "review_render_failed",
    )

    def image(entry, expected_view):
        require(entry.get("view") == expected_view, "review_render_failed")
        path = Path(entry.get("path", "")).resolve()
        require(path.is_relative_to(output.resolve()) and path.is_file(), "review_render_failed")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == entry.get("sha256"), "review_render_failed")
        return path

    views = report.get("views")
    require(isinstance(views, list) and len(views) == len(RENDER_VIEWS), "review_render_failed")
    images = [dict(path=image(entry, view), label=view, component_id=None) for entry, view in zip(views, RENDER_VIEWS)]
    rendered_components = report.get("components")
    require(isinstance(rendered_components, list) and len(rendered_components) == len(candidates), "review_render_failed")
    for candidate, rendered in zip(candidates, rendered_components):
        require(
            rendered.get("component_id") == candidate["component_id"]
            and rendered.get("model_sha256") == candidate["sha256"],
            "review_render_failed",
        )
        entries = rendered.get("views")
        require(isinstance(entries, list) and len(entries) == len(COMPONENT_VIEWS), "review_render_failed")
        for entry, view in zip(entries, COMPONENT_VIEWS):
            images.append(
                dict(
                    path=image(entry, view),
                    label=view,
                    component_id=candidate["component_id"],
                )
            )
    return images


def recognize(source, directory, godot_path, render_script, planner=None, candidate_limit=DEFAULT_COMPONENT_LIMIT):
    source = Path(source).expanduser().resolve()
    directory = Path(directory).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() == ".glb", "source_missing")
    require(not directory.exists(), "garment_auto_output_exists")
    require(
        type(candidate_limit) is int and 1 <= candidate_limit <= MAX_COMPONENT_LIMIT,
        "garment_auto_candidate_limit_invalid",
    )
    directory.mkdir(parents=True)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    geometry = GarmentSource(source)
    inspection = geometry.inspection()
    (directory / "inspection.json").write_text(canonical(inspection), encoding="utf-8")
    ordered = sorted(
        inspection["components"],
        key=lambda component: (-component["triangle_count"], component["component_index"]),
    )
    require(bool(ordered), "garment_inventory_no_geometry")
    selected = ordered[:candidate_limit]
    candidates = []
    for index, component in enumerate(selected):
        candidate = write_component_preview(
            source,
            component["component_id"],
            directory / "component-models" / (str(index).zfill(3) + ".glb"),
        )
        candidates.append(dict(component_id=component["component_id"], **candidate))
    images = _render(source, candidates, directory, godot_path, render_script)
    if planner is None:
        from kimi_provider import DEFAULT_ENDPOINT, DEFAULT_MODEL

        planner = dict(endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, key_env="KIMI_API_KEY")
    inventory = request_inventory(planner, inspection, images, directory / "inventory")
    spec = spec_from_inventory(source, directory / "extracted", inventory, inspection)
    (directory / "selection.json").write_text(canonical(spec), encoding="utf-8")
    require(bool(spec["items"]), "garment_inventory_no_geometry")
    require(hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256, "garment_split_source_changed")
    receipt = dict(
        schema_version=1,
        mode="ai_visual_component_selection",
        source_sha256=source_sha256,
        candidate_count=len(candidates),
        candidate_limit=candidate_limit,
        candidate_policy="largest_triangle_components_for_visual_evidence",
        recognized_item_count=len(inventory["items"]),
        selected_item_count=len(spec["items"]),
        unresolved_items=spec["unresolved_items"],
        inventory_sha256=spec["inventory_sha256"],
        source_not_overwritten=True,
        visual_review_passed=False,
        human_confirmed=False,
        cloth_ready=False,
    )
    (directory / "selection.json").write_text(canonical(spec), encoding="utf-8")
    (directory / "auto-receipt.json").write_text(canonical(receipt), encoding="utf-8")
    return dict(
        items=spec["items"],
        unresolved_items=spec["unresolved_items"],
        inventory_sha256=spec["inventory_sha256"],
        receipt=receipt,
    )
