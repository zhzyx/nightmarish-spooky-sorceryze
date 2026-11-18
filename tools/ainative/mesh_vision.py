"""Vision-guided reference understanding and generated-mesh acceptance.

All references participate in subject understanding and final review. Tripo's
per-call view limit only selects the current generation inputs; it never defines
the meaning, order, or accepted size of the user's image collection.
"""

import base64
import copy
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from extensions import canonical, require
from provider_common import validate_png

ANALYSIS_VIEWS = ("front", "three_quarter", "left", "right", "back", "top", "bottom", "detail", "unknown")
GENERATION_VIEWS = {"front", "left", "right", "back"}
VIEW_WEIGHTS = {
    "front": 100,
    "three_quarter": 90,
    "left": 80,
    "right": 80,
    "back": 70,
    "top": 40,
    "bottom": 30,
    "unknown": 10,
}


def analysis_schema():
    image = dict(
        type="object",
        properties=dict(
            image_id=dict(type="string"),
            view=dict(type="string", enum=list(ANALYSIS_VIEWS)),
            content_kind=dict(
                type="string", enum=["full_subject", "partial_subject", "detail", "contact_sheet", "other"]
            ),
            detail_region=dict(type="string"),
            same_subject=dict(type="boolean"),
            observation=dict(type="string"),
        ),
        required=["image_id", "view", "content_kind", "detail_region", "same_subject", "observation"],
        additionalProperties=False,
    )
    subject = dict(
        type="object",
        properties=dict(
            category=dict(type="string"),
            description=dict(type="string"),
            structure=dict(type="string"),
            expected_details=dict(type="string"),
        ),
        required=["category", "description", "structure", "expected_details"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            subject=subject,
            images=dict(type="array", items=image),
            coherent=dict(type="boolean"),
            synthesis=dict(type="string"),
        ),
        required=["subject", "images", "coherent", "synthesis"],
        additionalProperties=False,
    )


REVIEW_FRONT_YAW = {"front": 0.0, "right": 90.0, "back": 180.0, "left": -90.0}


def review_schema():
    view = dict(
        type="object",
        properties=dict(
            view=dict(type="string"),
            similar=dict(type="boolean"),
            observation=dict(type="string"),
        ),
        required=["view", "similar", "observation"],
        additionalProperties=False,
    )
    head_gate = dict(
        type="object",
        properties=dict(
            applicable=dict(type="boolean"),
            complete_face=dict(type="boolean"),
            neck_join_pass=dict(type="boolean"),
            identity_pass=dict(type="boolean"),
            face_proportions_pass=dict(type="boolean"),
            animation_geometry_pass=dict(type="boolean"),
            observation=dict(type="string"),
        ),
        required=[
            "applicable", "complete_face", "neck_join_pass", "identity_pass",
            "face_proportions_pass", "animation_geometry_pass", "observation",
        ],
        additionalProperties=False,
    )
    acceptance = dict(
        type="object",
        properties=dict(
            top_view=dict(type="string", enum=["approximate_allowed"]),
            face=dict(type="string", enum=["recognizable_identity_normal_proportions"]),
            animation=dict(type="string", enum=["geometry_readiness_only_rig_unverified"]),
        ),
        required=["top_view", "face", "animation"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            schema_version=dict(type="integer", const=2),
            passed=dict(type="boolean"),
            subject_match=dict(type="boolean"),
            proportions_pass=dict(type="boolean"),
            views=dict(type="array", items=view),
            details_pass=dict(type="boolean"),
            head_gate=head_gate,
            acceptance=acceptance,
            issues=dict(type="array", items=dict(type="string")),
            retry_guidance=dict(type="string"),
            rendered_front_view=dict(type="string", enum=list(REVIEW_FRONT_YAW)),
        ),
        required=[
            "schema_version", "passed", "subject_match", "proportions_pass", "views",
            "details_pass", "head_gate", "acceptance", "issues", "retry_guidance", "rendered_front_view",
        ],
        additionalProperties=False,
    )


def flatten_sources(request, manifest):
    index = {asset["id"]: asset for asset in manifest["artifacts"]}
    ordered = list(request["inputs"].values()) + [
        context["artifact"] for context in request["context"] if "artifact" in context
    ]
    result = []

    def append(reference, label):
        require(isinstance(reference, dict) and set(reference) == {"id", "revision"}, "invalid_input")
        asset = index.get(reference["id"])
        require(asset is not None and asset["revision"] == reference["revision"], "invalid_input")
        if asset["type"] == "image_set":
            payload = asset["payload"]
            require(payload.get("schema_version") == 1 and isinstance(payload.get("items"), list), "invalid_input")
            for item in payload["items"]:
                append(item["artifact"], label + " / " + str(item.get("label", "image")))
        else:
            require(asset["type"] == "image", "invalid_input")
            result.append(dict(asset=asset, label=label))

    for position, reference in enumerate(ordered):
        append(reference, "source" if position == 0 else "reference " + str(position + 1))
    require(result, "invalid_input")
    return result


def source_images(provider, key, sources, directory):
    """Decode and downscale every reference with the configured Godot runtime."""
    directory.mkdir(parents=True, exist_ok=False)
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        '[application]\nconfig/name="Private vision preparation"\n', encoding="utf-8"
    )
    images = []
    entries = []
    for index, source in enumerate(sources):
        asset = source["asset"]
        payload = asset["payload"]
        data = base64.b64decode(payload["content_base64"], validate=True)
        require(
            0 < len(data) <= 32 * 1024 * 1024
            and hashlib.sha256(data).hexdigest() == payload["content_sha256"]
            and payload["extension"].lower() in (".png", ".jpg", ".jpeg"),
            "invalid_input",
        )
        original = directory / ("original-" + str(index) + payload["extension"].lower())
        original.write_bytes(data)
        path = directory / ("reference-" + str(index) + ".png")
        images.append(dict(input=str(original), output=str(path)))
        entries.append(dict(image_id=asset["id"], label=source["label"], path=path, source=asset))
    report = directory / "prepared.json"
    request = directory / "prepare-request.json"
    request.write_text(canonical(dict(images=images, report=str(report))), encoding="utf-8")
    script = Path(provider.config["review_script_path"]).with_name("vision_prepare.gd")
    code = provider._run_owned(
        key,
        [
            provider.config["review_godot_path"],
            "--headless",
            "--path",
            str(project),
            "--script",
            str(script),
            "--",
            str(request),
        ],
        "prepare.log",
        "vision_prepare",
        120,
        directory,
    )
    if code is None:
        return None
    require(code == 0 and report.is_file(), "vision_output_invalid")
    prepared = json.loads(report.read_text(encoding="utf-8"))["images"]
    require(len(prepared) == len(entries), "vision_output_invalid")
    for entry, item in zip(entries, prepared):
        path = entry["path"].resolve()
        data = path.read_bytes()
        require(
            Path(item["path"]).resolve() == path
            and path.is_file()
            and not path.is_symlink()
            and validate_png(data)
            and hashlib.sha256(data).hexdigest() == item["sha256"],
            "vision_output_invalid",
        )
    return entries


def existing_source_images(sources, directory):
    entries = []
    for index, source in enumerate(sources):
        png = directory / ("reference-" + str(index) + ".png")
        jpeg = directory / ("reference-" + str(index) + ".jpg")
        path = png if png.is_file() else jpeg
        require(path.is_file() and not path.is_symlink(), "vision_output_invalid")
        entries.append(dict(image_id=source["asset"]["id"], label=source["label"], path=path, source=source["asset"]))
    return entries


def analysis_prompt(request, entries):
    prompt = str(request["parameters"].get("prompt", ""))
    contexts = [str(context.get("text", "")) for context in request["context"] if "text" in context]
    listing = "\n".join(entry["image_id"] + " = " + entry["label"] for entry in entries)
    return (
        "Inspect EVERY attached reference image individually before synthesizing. For each image identify its actual "
        "camera direction or detail region; never infer direction from filename, label, or array position. Then inspect "
        "all images together and determine the single subject to model (for example a human, dwarf, animal, vase, or "
        "another object), its anatomy or structure, proportions, materials, and expected details. Reject conflicting "
        "subjects honestly. The labels are lineage only, not visual evidence. Return one entry per listed image_id with "
        "no omissions or duplicates. User modeling intent is context, not permission to ignore visible evidence.\n"
        "User intent:\n" + "\n".join([prompt] + contexts).strip() + "\nImage lineage:\n" + listing
    )


def review_prompt(analysis, previous_issues):
    return (
        "Review the generated 3D model against ALL attached original references and the attached rendered model views. "
        "First decide whether the model is the same category and subject established by the reference analysis. For a "
        "character inspect every visible organ, limb, head, torso, hands, feet and their proportions; for other subjects "
        "inspect the equivalent structural parts. Compare every available generated direction with the closest original "
        "view and identify mismatches. Finally compare face, materials, clothing, ornaments, surface and other expected "
        "details. The generated head_front, head_three_quarter and head_side images are mandatory close-range evidence. "
        "Set rendered_front_view to the full-body generated view label (front, right, back or left) whose image actually "
        "shows the subject's anatomical or reference front. Use front when generated-front is correct. Determine this "
        "from visible evidence, never from filenames or render order; it describes camera evidence and does not relax "
        "any geometry or detail requirement. "
        "For every human or humanoid set head_gate.applicable=true and independently verify that the mouth, chin and "
        "lower face are complete, that no horizontal crop crosses the face, and that the head joins a complete neck at "
        "the collar without a gap or mask-like seam. Set complete_face=true and neck_join_pass=true only after all "
        "three head views support those conclusions. For non-humanoid subjects set applicable=false and the other "
        "head-gate booleans=false; do not invent human anatomy. Use schema_version=2 and the exact acceptance constants "
        "in the schema. The top view is approximate: set its similar=true when its direction and gross visible layout "
        "are consistent even if its elevation angle differs moderately or fine details are hidden. Do not require an "
        "identical top-view camera, but reject a wrong subject, missing anatomy, or contradictory layout. For a human "
        "face, identity_pass means the same person remains recognizable from the supplied face evidence, not a 1:1 "
        "photogrammetry replica. Judge identity together with normal feature placement and proportions; set "
        "face_proportions_pass independently. Set animation_geometry_pass only when the visible face, mouth, eyes and "
        "neck have no obvious geometric blocker to later jaw, eye and neck deformation. This is geometry readiness "
        "only: never claim that a skeleton, skin weights or an actual animation has been verified by this visual gate. "
        "passed=true only when subject_match, proportions_pass, every direction comparison, details_pass and the "
        "applicable head gate all pass with no obvious defect. Do not pass merely because a GLB or a plausible render "
        "exists. If anything fails, set passed=false, list concrete issues, and provide retry_guidance for a supported "
        "incremental correction. Do not assume a direction from render order: each render is explicitly named before "
        "its image. If a label does not match the visible direction, report a camera-label protocol issue rather than "
        "pretending that the wrong reference comparison passed.\nReference analysis:\n"
        + canonical(analysis)
        + "\nPrevious rejected-attempt issues:\n"
        + canonical(previous_issues)
    )


def _request_json(provider, key, directory, stage, prompt, schema, entries):
    from api_planner import validate_config

    config = validate_config(provider.config["planner"])
    directory.mkdir(parents=True, exist_ok=False)
    content = [dict(type="text", text=prompt)]
    for entry in entries:
        path = Path(entry["path"])
        content.append(dict(type="text", text="IMAGE " + entry["image_id"] + "; role/view: " + entry["label"]))
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        content.append(
            dict(
                type="image_url",
                image_url=dict(url="data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode()),
            )
        )
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(type="json_schema", json_schema=dict(name=stage, strict=True, schema=schema)),
        reasoning_effort="low",
        max_tokens=16384,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= 48 * 1024 * 1024, "vision_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    (directory / "planner-config.json").write_text(canonical(config), encoding="utf-8")
    code = provider._run_owned(
        key,
        [
            sys.executable,
            "-X",
            "utf8",
            str(Path(__file__).with_name("api_planner.py")),
            str(directory / "planner-config.json"),
            str(directory),
        ],
        "vision.log",
        "vision_" + stage,
        135,
        directory,
    )
    if code is None:
        return None
    require(code == 0, "vision_request_failed")
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    require(
        receipt["request_sha256"] == hashlib.sha256(raw).hexdigest()
        and receipt["instructions_sha256"] == hashlib.sha256(canonical(document).encode()).hexdigest(),
        "vision_output_invalid",
    )
    return document


def analyze(provider, key, request, sources, directory):
    entries = source_images(provider, key, sources, directory / "sources")
    if entries is None:
        return None
    document = _request_json(
        provider,
        key,
        directory / "request",
        "reference_analysis",
        analysis_prompt(request, entries),
        analysis_schema(),
        entries,
    )
    if document is None:
        return None
    require(set(document) == {"subject", "images", "coherent", "synthesis"}, "vision_output_invalid")
    expected = {entry["image_id"] for entry in entries}
    observed = [item.get("image_id") for item in document["images"]]
    require(
        len(observed) == len(entries) and set(observed) == expected and len(set(observed)) == len(observed),
        "vision_output_invalid",
    )
    require(
        document["coherent"] and all(item["same_subject"] for item in document["images"]), "vision_subject_incoherent"
    )
    return dict(document=document, entries=entries)


def select_generation_request(request, sources, analysis):
    """Use analyzed evidence and weights; input order is only a stable tie-break."""
    by_id = {source["asset"]["id"]: source for source in sources}
    candidates = []
    for index, item in enumerate(analysis["images"]):
        if item["content_kind"] != "full_subject" or item["view"] not in GENERATION_VIEWS:
            continue
        source = by_id[item["image_id"]]
        candidates.append((VIEW_WEIGHTS[item["view"]], -index, item["view"], source))
    if not candidates:
        full = [
            (VIEW_WEIGHTS.get(item["view"], 0), -index, item["view"], by_id[item["image_id"]])
            for index, item in enumerate(analysis["images"])
            if item["content_kind"] == "full_subject"
        ]
        require(full, "vision_no_full_subject")
        candidates = [max(full, key=lambda value: (value[0], value[1]))]
    else:
        candidates.sort(key=lambda value: (value[0], value[1]), reverse=True)
        front = [candidate for candidate in candidates if candidate[2] == "front"]
        candidates = (
            front + [candidate for candidate in candidates if candidate[2] != "front"] if front else [candidates[0]]
        )
        candidates = candidates[:4]
    selected = []
    for weight, _, view, source in candidates:
        asset = copy.deepcopy(source["asset"])
        provenance = dict(asset["payload"].get("provenance", {}))
        provenance.update(analyzed_view=view, generation_weight=weight)
        asset["payload"]["provenance"] = provenance
        selected.append(asset)
    references = [{key: asset[key] for key in ("id", "revision")} for asset in selected]
    child = copy.deepcopy(request)
    child["version"] = "1"
    child["inputs"] = {"source": references[0]}
    child["context"] = []
    child["parameters"]["prompt"] = ""
    child["context"] += [
        dict(artifact=reference, role="reference", scope="node", strength="reference") for reference in references[1:]
    ]
    return child, selected


def issue_geometry_scope(issue):
    value = str(issue).casefold()
    if str(issue).startswith(("Missing required rendered view:", "Duplicate rendered view:")):
        return "protocol"
    if any(term in value for term in (
        "missing arm", "missing leg", "missing limb", "arms are missing", "legs are missing",
        "full-body", "full body", "bust", "duplicated figure", "duplicate figure", "pose",
    )):
        return "blocking"
    if any(term in value for term in (
        "geometry", "topology", "neck", "chin", "mouth", "silhouette", "hairstyle", "haircut",
        "hair geometry", "hair volume", "pompadour", "helmet-like hair", "breadth", "projection",
        "facial identity", "face identity", "facial geometry", "eye shape", "nose shape", "lip shape",
    )):
        return "deferred"
    return "appearance"


def geometry_edit_required(review):
    if not review.get("subject_match", False) or not review.get("proportions_pass", False):
        return True
    head = review.get("head_gate", {})
    if head.get("applicable") and any(head.get(key) is False for key in (
        "complete_face", "neck_join_pass", "identity_pass", "face_proportions_pass", "animation_geometry_pass",
    )):
        return True
    return any(issue_geometry_scope(issue) in ("blocking", "deferred") for issue in review.get("issues", []))


def blocking_geometry_failure(review):
    if not review.get("subject_match", False) or not review.get("proportions_pass", False):
        return True
    head = review.get("head_gate", {})
    if head.get("applicable") and (not head.get("complete_face") or not head.get("neck_join_pass")):
        return True
    return any(issue_geometry_scope(issue) == "blocking" for issue in review.get("issues", []))


def appearance_feedback(review):
    return [str(issue) for issue in review.get("issues", []) if issue_geometry_scope(issue) == "appearance"]


def neck_repair_parameters(previous_model, previous_review):
    head = previous_review.get("head_gate", {})
    if (
        not previous_review.get("subject_match", False)
        or not previous_review.get("proportions_pass", False)
        or not head.get("applicable")
        or not head.get("complete_face")
        or head.get("neck_join_pass")
    ):
        return None
    for issue in previous_review.get("issues", []):
        value = str(issue).casefold()
        if any(term in value for term in ("hair", "arm", "leg", "bust", "proportion", "pose", "mouth", "chin", "full-body", "full body", "duplicate figure", "duplicated figure")):
            return None
    try:
        data = base64.b64decode(previous_model["payload"]["content_base64"], validate=True)
        size = struct.unpack_from("<I", data, 12)[0]
        document = json.loads(data[20 : 20 + size])
        extras = document.get("asset", {}).get("extras", {})
        landmarks = extras.get("maliang_head_landmarks", {})
        repair = extras.get("maliang_geometry_repair", {})
        if landmarks.get("confirmed") is not True or landmarks.get("head_geometry_mode") != "merged":
            return None
        if repair.get("operation") == "align_neck":
            return None
        neck_y = landmarks.get("body_neck_y")
        if isinstance(neck_y, bool) or not isinstance(neck_y, (int, float)):
            return None
        return dict(
            head_mesh="ReferenceHead",
            body_mesh="PriestBody",
            neck_y=float(neck_y),
            band_height=0.01,
            max_translation=0.1,
            axes=["z"],
        )
    except (KeyError, ValueError, TypeError, struct.error, json.JSONDecodeError):
        return None


def crown_repair_parameters(previous_model, previous_review):
    """Select only an explicitly confirmed, source-bound crown recipe."""
    head = previous_review.get("head_gate", {})
    if (
        not previous_review.get("subject_match", False)
        or not previous_review.get("proportions_pass", False)
        or not head.get("applicable")
        or not head.get("complete_face")
        or not head.get("neck_join_pass")
        or not any("hair" in str(issue).casefold() for issue in previous_review.get("issues", []))
    ):
        return None
    try:
        data = base64.b64decode(previous_model["payload"]["content_base64"], validate=True)
        size = struct.unpack_from("<I", data, 12)[0]
        document = json.loads(data[20 : 20 + size])
        binary_size, kind = struct.unpack_from("<II", data, 20 + size)
        require(kind == 0x004E4942 and 28 + size + binary_size <= len(data), "vision_output_invalid")
        geometry_sha256 = hashlib.sha256(data[28 + size : 28 + size + binary_size]).hexdigest()
        recipe = document.get("asset", {}).get("extras", {}).get("maliang_geometry_recipe", {})
        if (
            recipe.get("operation") != "reshape_crown"
            or recipe.get("confirmed") is not True
            or recipe.get("geometry_sha256") != geometry_sha256
        ):
            return None
        parameters = recipe["parameters"]
        require(isinstance(parameters, dict), "vision_output_invalid")
        return dict(mesh=recipe["mesh"], confirmed=True, **parameters)
    except (KeyError, ValueError, TypeError, struct.error, json.JSONDecodeError):
        return None


def select_retry_adjust_request(request, analysis, previous_model, previous_review):
    """Use the actual previous GLB for a supported local or appearance edit."""
    require(
        isinstance(previous_model, dict)
        and previous_model.get("type") == "mesh"
        and previous_model.get("id")
        and previous_model.get("revision"),
        "model_adjust_source_missing",
    )
    repair = neck_repair_parameters(previous_model, previous_review)
    if repair is not None:
        child = copy.deepcopy(request)
        child.update(
            node="model_adjust",
            version="2",
            inputs={"source": {key: previous_model[key] for key in ("id", "revision")}},
            context=[],
        )
        child["parameters"] = {"prompt": "", "operation": "align_neck", "repair": repair}
        return child, []
    repair = crown_repair_parameters(previous_model, previous_review)
    if repair is not None:
        child = copy.deepcopy(request)
        child.update(
            node="model_adjust",
            version="2",
            inputs={"source": {key: previous_model[key] for key in ("id", "revision")}},
            context=[],
        )
        child["parameters"] = {"prompt": "", "operation": "reshape_crown", "repair": repair}
        return child, []
    require(not blocking_geometry_failure(previous_review), "model3d_geometry_edit_unsupported")
    supported_feedback = appearance_feedback(previous_review)
    require(bool(supported_feedback), "model3d_geometry_edit_unsupported")

    def clip(value, limit):
        text = " ".join(str(value).split())
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    subject = analysis["subject"]
    description = clip(subject["category"] + ": " + subject["description"], 180)
    requirements = clip(subject["structure"] + " Expected details: " + subject["expected_details"], 220)
    child = copy.deepcopy(request)
    child.update(
        node="model_adjust",
        version="1",
        inputs={"source": {key: previous_model[key] for key in ("id", "revision")}},
        context=[],
    )
    prompt_prefix = (
        "Adjust the supplied existing 3D model, not a new subject. Preserve its geometry, silhouette, proportions, pose, "
        "body and costume layout. Correct only the listed material and appearance details. Subject: "
        + description
        + ". Reference requirements: "
        + requirements
        + ". Appearance corrections: "
    )
    require(len(prompt_prefix) < 1000, "invalid_input")
    feedback = clip("; ".join(supported_feedback), 1000 - len(prompt_prefix))
    child["parameters"]["prompt"] = prompt_prefix + feedback
    require(len(child["parameters"]["prompt"]) <= 1000, "invalid_input")
    return child, []


def render_review_views(provider, key, model_path, directory, yaw_override=None):
    directory.mkdir(parents=True, exist_ok=False)
    project = directory / "project"
    project.mkdir()
    (project / "project.godot").write_text('[application]\nconfig/name="Private mesh review"\n', encoding="utf-8")
    model_path = Path(model_path).resolve()
    data = model_path.read_bytes()
    require(len(data) >= 28 and data[:4] == b"glTF", "review_render_failed")
    size = struct.unpack_from("<I", data, 12)[0]
    require(20 + size <= len(data), "review_render_failed")
    frame = json.loads(data[20 : 20 + size]).get("asset", {}).get("extras", {}).get("maliang_review_frame", {})
    yaw = frame.get("yaw_degrees", 0.0) if yaw_override is None else yaw_override
    require(
        isinstance(frame, dict)
        and (not frame or frame.get("confirmed") is True and frame.get("schema_version") == 1)
        and isinstance(yaw, (int, float))
        and not isinstance(yaw, bool)
        and -180.0 <= yaw <= 180.0,
        "review_render_failed",
    )
    config = dict(
        model=str(model_path),
        output=str(directory),
        yaw_degrees=float(yaw),
        script_sha256=hashlib.sha256(Path(provider.config["review_script_path"]).read_bytes()).hexdigest(),
    )
    request = directory / "render-request.json"
    request.write_text(canonical(config), encoding="utf-8")
    code = provider._run_owned(
        key,
        [
            provider.config["review_godot_path"],
            "--path",
            str(project),
            "--script",
            provider.config["review_script_path"],
            "--rendering-method",
            "gl_compatibility",
            "--audio-driver",
            "Dummy",
            "--",
            str(request),
        ],
        "render.log",
        "review_render",
        120,
        directory,
    )
    if code is None:
        return None
    require(code == 0, "review_render_failed")
    return load_review_views(model_path, directory)


def review_yaw_correction(review):
    if review.get("passed"):
        return None
    correction = REVIEW_FRONT_YAW.get(review.get("rendered_front_view"), 0.0)
    return correction or None


def corrected_review_yaw(directory, review):
    correction = review_yaw_correction(review)
    require(correction is not None, "review_render_failed")
    report = json.loads((Path(directory) / "views.json").read_text(encoding="utf-8"))
    current = report.get("yaw_degrees", 0.0)
    require(
        isinstance(current, (int, float))
        and not isinstance(current, bool)
        and -180.0 <= current <= 180.0,
        "review_render_failed",
    )
    return (float(current) + correction + 180.0) % 360.0 - 180.0


def render_corrected_review_views(provider, key, model_path, directory, yaw):
    report_path = Path(directory) / "views.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        require(report.get("yaw_degrees") == float(yaw), "review_render_failed")
        return load_review_views(model_path, directory)
    return render_review_views(provider, key, model_path, directory, yaw_override=yaw)


HEAD_REVIEW_VIEWS = frozenset(("head_front", "head_three_quarter", "head_side"))
HUMANOID_TERMS = (
    "human",
    "humanoid",
    "person",
    "character",
    "priest",
    "man",
    "woman",
    "dwarf",
    "elf",
    "robot",
    "人",
    "角色",
    "人形",
)


def head_gate_required(analysis):
    category = str(analysis.get("subject", {}).get("category", "")).casefold()
    return any(term in category for term in HUMANOID_TERMS)


def load_review_views(model_path, directory):
    directory = Path(directory).resolve()
    report = json.loads((directory / "views.json").read_text(encoding="utf-8"))
    require(report["model_sha256"] == hashlib.sha256(Path(model_path).read_bytes()).hexdigest(), "review_render_failed")
    entries = []
    for item in report["views"]:
        path = Path(item["path"]).resolve()
        require(path.is_relative_to(directory) and path.is_file() and not path.is_symlink(), "review_render_failed")
        data = path.read_bytes()
        require(validate_png(data) and hashlib.sha256(data).hexdigest() == item["sha256"], "review_render_failed")
        entries.append(dict(image_id="generated-" + item["view"], label="generated " + item["view"], path=path))
    observed = {entry["image_id"].removeprefix("generated-") for entry in entries}
    require(len(entries) == len(observed), "review_render_failed")
    required = {"front", "right", "back", "left", "top"} | HEAD_REVIEW_VIEWS
    require(required <= observed, "review_render_failed")
    return entries


def validate_review(document, generated_entries, require_head=None):
    expected = {entry["image_id"].removeprefix("generated-") for entry in generated_entries}
    observed = []
    for item in document["views"]:
        # Accept generated prefixes and human-readable orientation/comparison
        # suffixes without weakening the requirement for every expected view.
        value = re.sub(r"^generated[-_ ]+", "", item.get("view", "").strip().casefold())
        for name in sorted(expected, key=len, reverse=True):
            suffix = value[len(name) :] if value.startswith(name) else None
            if suffix is not None and (not suffix or suffix[0] in " (-_:/"):
                value = name
                break
        else:
            value = value.split(" (", 1)[0].strip()
        item["view"] = value
        observed.append(item["view"])
    missing = sorted(expected - set(observed))
    duplicates = sorted(view for view in expected if observed.count(view) > 1)
    head = document.get("head_gate")
    head_booleans = (
        "applicable", "complete_face", "neck_join_pass", "identity_pass",
        "face_proportions_pass", "animation_geometry_pass",
    )
    acceptance = {
        "top_view": "approximate_allowed",
        "face": "recognizable_identity_normal_proportions",
        "animation": "geometry_readiness_only_rig_unverified",
    }
    require(
        document.get("schema_version") == 2
        and document.get("acceptance") == acceptance
        and isinstance(head, dict)
        and set(head) == {*head_booleans, "observation"}
        and all(isinstance(head[key], bool) for key in head_booleans)
        and isinstance(head["observation"], str)
        and isinstance(document.get("issues"), list)
        and isinstance(document.get("rendered_front_view"), str)
        and document["rendered_front_view"] in REVIEW_FRONT_YAW,
        "vision_output_invalid",
    )
    if missing or duplicates:
        document["passed"] = False
        document["review_incomplete"] = True
        document["issues"] = list(document["issues"]) + ["Missing required rendered view: " + view for view in missing]
        document["issues"] += ["Duplicate rendered view: " + view for view in duplicates]
    required = head["applicable"] if require_head is None else bool(require_head or head["applicable"])
    if require_head:
        require(head["applicable"], "vision_output_invalid")
        require(HEAD_REVIEW_VIEWS <= expected, "vision_output_invalid")
    head_views_pass = all(
        any(item["view"] == view and item["similar"] for item in document["views"])
        for view in HEAD_REVIEW_VIEWS
    ) if required else True
    head_pass = not required or (
        all(head[key] for key in head_booleans if key != "applicable") and head_views_pass
    )
    passed = (
        document["passed"]
        and document["subject_match"]
        and document["proportions_pass"]
        and document["details_pass"]
        and all(item["similar"] for item in document["views"])
        and head_pass
        and not document["issues"]
    )
    document["passed"] = passed
    return document


def attach_head_review(model, review_document, analysis):
    """Embed the accepted human review into a derived GLB for downstream rigging."""
    if not head_gate_required(analysis):
        return model
    require(review_document["passed"] and review_document["head_gate"]["applicable"], "vision_output_invalid")
    result = copy.deepcopy(model)
    payload = result["payload"]
    data = base64.b64decode(payload["content_base64"], validate=True)
    original_sha = hashlib.sha256(data).hexdigest()
    require(
        original_sha == payload["content_sha256"] == result["revision"]
        and len(data) >= 28
        and data[:4] == b"glTF"
        and struct.unpack_from("<I", data, 8)[0] == len(data),
        "vision_output_invalid",
    )
    json_size = struct.unpack_from("<I", data, 12)[0]
    require(20 + json_size + 8 <= len(data), "vision_output_invalid")
    document = json.loads(data[20 : 20 + json_size])
    binary_chunk = data[20 + json_size :]
    views = {
        item["view"]: bool(item["similar"])
        for item in review_document["views"]
        if item["view"] in HEAD_REVIEW_VIEWS
    }
    require(set(views) == HEAD_REVIEW_VIEWS and all(views.values()), "vision_output_invalid")
    extras = document.setdefault("asset", {}).setdefault("extras", {})
    recovery = review_document.get("orientation_recovery")
    if recovery is not None:
        require(
            recovery.get("model_sha256") == original_sha
            and recovery.get("geometry_changed") is False
            and isinstance(recovery.get("yaw_degrees"), (int, float))
            and -180.0 <= recovery["yaw_degrees"] <= 180.0,
            "vision_output_invalid",
        )
        extras["maliang_review_frame"] = dict(
            schema_version=1,
            yaw_degrees=float(recovery["yaw_degrees"]),
            confirmed=True,
            source_sha256=original_sha,
        )
    landmarks = extras.get("maliang_head_landmarks")
    merged = isinstance(landmarks, dict) and landmarks.get("confirmed") is True
    extras["maliang_head_review"] = dict(
        schema_version=2,
        mode="automatic",
        geometry_sha256=original_sha,
        head_geometry_mode="merged" if merged else "integrated",
        passed=True,
        acceptance=copy.deepcopy(review_document["acceptance"]),
        head_gate=copy.deepcopy(review_document["head_gate"]),
        head_views=views,
        animation_geometry_ready=True,
        rigging_verified=False,
        animation_verified=False,
    )
    encoded = canonical(document).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    output = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + len(binary_chunk))
    output += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded + binary_chunk
    require(len(output) <= 64 * 1024 * 1024, "vision_output_invalid")
    revision = hashlib.sha256(output).hexdigest()
    result["revision"] = revision
    payload.update(
        content_base64=base64.b64encode(output).decode(),
        content_sha256=revision,
        bytes=len(output),
    )
    provenance = dict(payload.get("provenance", {}))
    provenance.update(geometry_sha256=original_sha, head_review_embedded=True)
    payload["provenance"] = provenance
    return result


def attach_capability_review(model, review_document):
    """Deliver the last reviewed GLB with explicit unresolved capability evidence."""
    require(review_document.get("passed") is False and isinstance(review_document.get("issues"), list), "vision_output_invalid")
    result = copy.deepcopy(model)
    payload = result["payload"]
    data = base64.b64decode(payload["content_base64"], validate=True)
    original_sha = hashlib.sha256(data).hexdigest()
    require(
        original_sha == payload["content_sha256"] == result["revision"]
        and len(data) >= 28
        and data[:4] == b"glTF"
        and struct.unpack_from("<I", data, 8)[0] == len(data),
        "vision_output_invalid",
    )
    json_size = struct.unpack_from("<I", data, 12)[0]
    require(20 + json_size + 8 <= len(data), "vision_output_invalid")
    document = json.loads(data[20 : 20 + json_size])
    binary_chunk = data[20 + json_size :]
    extras = document.setdefault("asset", {}).setdefault("extras", {})
    recovery = review_document.get("orientation_recovery")
    if recovery is not None:
        require(
            recovery.get("model_sha256") == original_sha
            and recovery.get("geometry_changed") is False
            and isinstance(recovery.get("yaw_degrees"), (int, float))
            and -180.0 <= recovery["yaw_degrees"] <= 180.0,
            "vision_output_invalid",
        )
        extras["maliang_review_frame"] = dict(
            schema_version=1,
            yaw_degrees=float(recovery["yaw_degrees"]),
            confirmed=True,
            source_sha256=original_sha,
        )
    extras["maliang_capability_review"] = dict(
        schema_version=1,
        geometry_sha256=original_sha,
        capability_limited=True,
        visual_review_passed=False,
        delivery_acceptance="capability_limited_with_unresolved_issues",
        unresolved_issues=copy.deepcopy(review_document["issues"]),
        visual_review=copy.deepcopy(review_document),
    )
    encoded = canonical(document).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    output = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + len(binary_chunk))
    output += struct.pack("<II", len(encoded), 0x4E4F534A) + encoded + binary_chunk
    require(len(output) <= 64 * 1024 * 1024, "vision_output_invalid")
    revision = hashlib.sha256(output).hexdigest()
    result["revision"] = revision
    payload.update(
        content_base64=base64.b64encode(output).decode(),
        content_sha256=revision,
        bytes=len(output),
    )
    provenance = dict(payload.get("provenance", {}))
    provenance.update(
        geometry_sha256=original_sha,
        capability_limited=True,
        visual_review_passed=False,
        delivery_acceptance="capability_limited_with_unresolved_issues",
        unresolved_issues=copy.deepcopy(review_document["issues"]),
        capability_review_embedded=True,
    )
    payload["provenance"] = provenance
    return result


def review(provider, key, analysis, original_entries, generated_entries, previous_issues, directory):
    document = _request_json(
        provider,
        key,
        directory,
        "generated_mesh_review",
        review_prompt(analysis, previous_issues),
        review_schema(),
        list(original_entries) + list(generated_entries),
    )
    if document is None:
        return None
    return validate_review(document, generated_entries, head_gate_required(analysis))


def merge_incomplete_reviews(first, second, generated_entries, require_head):
    """Merge complementary evidence of the same renders, never conflicting votes."""
    documents = [first, second]
    require(all(document.get("schema_version") == 2 for document in documents), "vision_output_invalid")
    require(first.get("rendered_front_view") == second.get("rendered_front_view"), "vision_output_invalid")
    expected = [entry["image_id"].removeprefix("generated-") for entry in generated_entries]
    views = {}
    for document in documents:
        for item in document["views"]:
            previous = views.get(item["view"])
            if previous is not None:
                require(previous["similar"] == item["similar"], "vision_output_invalid")
            views[item["view"]] = copy.deepcopy(item)
    if not set(expected) <= set(views):
        return None
    head_keys = (
        "applicable", "complete_face", "neck_join_pass", "identity_pass",
        "face_proportions_pass", "animation_geometry_pass",
    )
    for key in head_keys:
        require(first["head_gate"][key] == second["head_gate"][key], "vision_output_invalid")
    issues = [
        issue
        for document in documents
        for issue in document["issues"]
        if not str(issue).startswith(("Missing required rendered view:", "Duplicate rendered view:"))
    ]
    ordered = [views[name] for name in expected]
    ordered.extend(item for name, item in views.items() if name not in expected)
    merged = copy.deepcopy(second)
    merged.pop("review_incomplete", None)
    merged["views"] = ordered
    merged["issues"] = issues
    for key in ("subject_match", "proportions_pass", "details_pass"):
        merged[key] = all(document[key] for document in documents)
    merged["passed"] = (
        merged["subject_match"]
        and merged["proportions_pass"]
        and merged["details_pass"]
        and all(item["similar"] for item in ordered)
        and not issues
    )
    result = validate_review(merged, generated_entries, require_head)
    result["evidence_recovery"] = "merged_incomplete_reviews_same_model"
    return result


def recover_saved_review(directory, generated_entries, require_head):
    """Read a completed API response without issuing another network request."""
    directory = Path(directory)
    path = directory / "api-plan.json"
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    require(
        receipt["request_sha256"] == hashlib.sha256((directory / "api-request.json").read_bytes()).hexdigest()
        and receipt["instructions_sha256"] == hashlib.sha256(canonical(document).encode()).hexdigest(),
        "vision_output_invalid",
    )
    return validate_review(document, generated_entries, require_head)


def complete_review(
    provider,
    key,
    analysis,
    original_entries,
    generated_entries,
    previous_issues,
    directory,
    document=None,
):
    """Recover/retry review evidence on the same GLB, never a new model."""
    directory = Path(directory)
    if document is not None and "schema_version" not in document:
        # V1 evidence has no explicit approximate-top or animation-readiness
        # decision. Re-review the identical render instead of upgrading its meaning.
        document = None
        directory = directory.with_name(directory.name + "-v2")
    if document is None:
        document = recover_saved_review(directory, generated_entries, head_gate_required(analysis))
    if document is None:
        document = review(provider, key, analysis, original_entries, generated_entries, previous_issues, directory)
    if document is None or not document.get("review_incomplete"):
        return document
    retry_directory = directory.with_name(directory.name + "-incomplete-retry")
    retried = recover_saved_review(retry_directory, generated_entries, head_gate_required(analysis))
    if retried is None:
        retried = review(
            provider,
            key,
            analysis,
            original_entries,
            generated_entries,
            list(previous_issues) + list(document["issues"]),
            retry_directory,
        )
    if retried is None:
        return None
    if retried.get("review_incomplete"):
        merged = merge_incomplete_reviews(
            document, retried, generated_entries, head_gate_required(analysis)
        )
        if merged is not None:
            return merged
    require(not retried.get("review_incomplete"), "model3d_review_incomplete")
    return retried
