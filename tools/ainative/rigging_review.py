"""AI-only visual gate for local GLBs entering the humanoid rigging node.

No reference image, manual approval, model mutation or hidden retry is involved.
The editor host owns the subprocess; rendering and one AI request happen here.
"""

import base64
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path

import api_planner
from extensions import canonical, require
from mesh_vision import REVIEW_FRONT_YAW, load_review_views, review_schema, validate_review

MAX_GLB_BYTES = 64 * 1024 * 1024
REQUIRED_HEAD_VIEWS = ("head_front", "head_three_quarter", "head_side")


def _prompt():
    return """Review ONLY the attached rendered views of one existing GLB for automatic standard-humanoid rigging. There are no external reference images and no human approval step. Inspect every image independently, then decide whether this is one complete, upright, approximately symmetric humanoid in a T-like reference pose with separated arms and legs. Subject_match=true means the visible subject satisfies that humanoid task, not similarity to an unavailable reference. Set subject_match=false for a non-human, bust, duplicate subject, missing limbs, or unclear evidence. proportions_pass and details_pass require visibly usable body proportions and complete geometry. Every views entry must use each required rendered view ID exactly once; set similar=true only when that view is usable and consistent with the same model. The head gate is applicable to this task: set applicable=true, then independently check complete mouth/chin/lower face, a joined neck, recognizable human facial structure with normal proportions, and geometry without visible animation blockers from head_front, head_three_quarter and head_side. If the subject is not humanoid or evidence is inadequate, set the relevant booleans=false and passed=false. Set rendered_front_view to the full-body view label (front, right, back or left) that actually shows the anatomical front. Use schema_version=2 and the exact acceptance constants. This is visual geometry review only: never claim a skeleton, skin weights or played animation exists. passed=true only when the standard-humanoid task, all required views, proportions, details and the full head gate pass; issues must then be empty. Otherwise list concrete issues and provide retry_guidance. Do not request manual approval and do not infer missing views.
Required view IDs:
["front", "right", "back", "left", "top", "detail_upper_front", "detail_lower_front", "head_front", "head_three_quarter", "head_side"]
"""


def _render(source, directory, godot_path, render_script, yaw_degrees=0.0):
    source = source.resolve()
    data = source.read_bytes()
    require(28 <= len(data) <= MAX_GLB_BYTES and data[:4] == b"glTF", "review_render_failed")
    require(Path(godot_path).is_file() and Path(render_script).is_file(), "review_render_failed")
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        '[application]\nconfig/name="Private humanoid AI review"\n', encoding="utf-8"
    )
    output = directory / "renders"
    script = Path(render_script).resolve()
    request = directory / "render-request.json"
    request.write_text(
        canonical(
            dict(
                model=str(source),
                output=str(output),
                yaw_degrees=float(yaw_degrees),
                script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
            )
        ),
        encoding="utf-8",
    )
    arguments = [
        str(Path(godot_path).resolve()),
        "--path",
        str(project),
        "--script",
        str(script),
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
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
    except subprocess.TimeoutExpired:
        require(False, "review_render_failed")
    require(completed.returncode == 0, "review_render_failed")
    return load_review_views(source, output)


def _request_ai(entries, directory):
    from kimi_provider import DEFAULT_ENDPOINT, DEFAULT_MODEL

    config = dict(endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, key_env="KIMI_API_KEY")
    api_planner.validate_config(config)
    directory.mkdir()
    prompt = _prompt()
    content = [dict(type="text", text=prompt)]
    for entry in entries:
        path = Path(entry["path"])
        content.append(dict(type="text", text="IMAGE " + entry["image_id"] + "; role/view: " + entry["label"]))
        content.append(
            dict(
                type="image_url",
                image_url=dict(url="data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()),
            )
        )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(
            type="json_schema", json_schema=dict(name="humanoid_rigging_review", strict=True, schema=review_schema())
        ),
        reasoning_effort="low",
        max_tokens=16384,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= api_planner.MAX_REQUEST, "vision_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(review_schema()), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    api_planner.perform(config, directory)
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    require(
        receipt.get("request_sha256") == hashlib.sha256(raw).hexdigest()
        and receipt.get("instructions_sha256") == hashlib.sha256(canonical(document).encode()).hexdigest(),
        "vision_output_invalid",
    )
    return document, receipt


def _head_review(source_sha, document, source):
    views = {item["view"]: bool(item["similar"]) for item in document["views"] if item["view"] in REQUIRED_HEAD_VIEWS}
    require(set(views) == set(REQUIRED_HEAD_VIEWS) and all(views.values()), "vision_output_invalid")
    data = source.read_bytes()
    size = struct.unpack_from("<I", data, 12)[0]
    extras = json.loads(data[20 : 20 + size]).get("asset", {}).get("extras", {})
    landmarks = extras.get("maliang_head_landmarks", {})
    merged = isinstance(landmarks, dict) and landmarks.get("confirmed") is True
    return dict(
        schema_version=2,
        mode="automatic",
        ai_reviewed=True,
        geometry_sha256=source_sha,
        source_sha256=source_sha,
        geometry_binding="whole_source_file_sha256",
        head_geometry_mode="merged" if merged else "integrated",
        passed=True,
        acceptance=document["acceptance"],
        head_gate=document["head_gate"],
        head_views=views,
        animation_geometry_ready=True,
        rigging_verified=False,
        animation_verified=False,
    )


def review_local_model(request):
    source = Path(request.get("source", "")).expanduser().resolve()
    directory = Path(request.get("directory", "")).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() == ".glb", "source_missing")
    require(not directory.exists(), "review_output_exists")
    directory.mkdir(parents=True)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    entries = _render(source, directory, request.get("godot_path", ""), request.get("render_script", ""))
    document, api_receipt = _request_ai(entries, directory / "request")
    document = validate_review(document, entries)
    api_receipts = [api_receipt]
    initial_front = document.get("rendered_front_view")
    if initial_front != "front" and document.get("subject_match") and document.get("proportions_pass"):
        correction = REVIEW_FRONT_YAW[initial_front]
        orientation = directory / "orientation"
        orientation.mkdir()
        entries = _render(
            source,
            orientation,
            request.get("godot_path", ""),
            request.get("render_script", ""),
            yaw_degrees=correction,
        )
        document, corrected_receipt = _request_ai(entries, directory / "request-front-recovery")
        document = validate_review(document, entries)
        api_receipts.append(corrected_receipt)
        document["orientation_recovery"] = dict(
            model_sha256=source_sha,
            previous_yaw_degrees=0.0,
            correction_degrees=float(correction),
            yaw_degrees=float(correction),
            previous_rendered_front_view=initial_front,
            geometry_changed=False,
        )
    if document.get("rendered_front_view") != "front":
        document["passed"] = False
        document["issues"] = list(document.get("issues", [])) + [
            "The full-body front render does not show the anatomical front"
        ]
    if not document.get("head_gate", {}).get("applicable"):
        document["passed"] = False
        document["issues"] = list(document.get("issues", [])) + ["The required humanoid head gate was not applicable"]
    passed = document.get("passed") is True
    result = dict(
        passed=passed,
        source_sha256=source_sha,
        rendered_front_view=document.get("rendered_front_view", ""),
        issues=list(document.get("issues", [])),
        review_document=document,
        api_receipt=api_receipts[-1],
        api_receipts=api_receipts,
    )
    if passed:
        result["head_review"] = _head_review(source_sha, document, source)
    (directory / "review-receipt.json").write_text(canonical(result), encoding="utf-8")
    return result
