"""Text-only assessment of measured humanoid rigging evidence.

The local Godot validator remains the authority for structure and numeric gates.
The language model receives JSON text only and can route bounded repair advice;
it cannot override a failed local gate or claim independent visual evidence.
"""

import hashlib
import json
import math
from pathlib import Path

import api_planner
from extensions import canonical, require

MAX_ATTEMPTS = 3
STAGES = ("skeleton", "skin", "rest", "rom", "capability")
TARGETS = ("none", "rigging_node", "joint_corrections", "skin_weights", "rom_animation")
COMMANDS = ("none", "refit_sagittal_leg_corrections", "clean_and_refit")
CONTROLS = {
    "none": "none",
    "rigging_node": "fit",
    "joint_corrections": "joint_corrections",
    "skin_weights": "skin_weights",
    "rom_animation": "rom_animation",
}


def review_schema():
    issue = dict(
        type="object",
        properties=dict(
            code=dict(type="string"),
            stage=dict(type="string", enum=list(STAGES)),
            check=dict(type="string"),
            message=dict(type="string"),
            actual=dict(type=["number", "null"]),
            threshold=dict(type=["number", "null"]),
            target=dict(type="string", enum=list(TARGETS)),
        ),
        required=["code", "stage", "check", "message", "actual", "threshold", "target"],
        additionalProperties=False,
    )
    repair = dict(
        type="object",
        properties=dict(
            command=dict(type="string", enum=list(COMMANDS)),
            parameters=dict(type="object", additionalProperties=False),
        ),
        required=["command", "parameters"],
        additionalProperties=False,
    )
    return dict(
        type="object",
        properties=dict(
            schema_version=dict(type="integer", const=1),
            passed=dict(type="boolean"),
            summary=dict(type="string"),
            issues=dict(type="array", items=issue),
            repair=repair,
        ),
        required=["schema_version", "passed", "summary", "issues", "repair"],
        additionalProperties=False,
    )


def _prompt():
    return """你是标准人形骨骼绑定后的文本验收器。输入只有本地 Godot 检测器产生的 JSON 实测证据，没有图片，也不得声称看过模型或画面。
请核对骨骼结构、蒙皮权重、Rest 还原、抬臂／下蹲／转身位移、关节协同、足底接触和胸口外扩。本地 validation.passed、scene_valid、issues、unsupported 及数值阈值是硬门禁：本地未通过时，你的 passed 必须为 false；不得放宽阈值、删除问题或虚构修复结果。
只根据证据判断。输出中文 summary；每个 issue 给出稳定 code、阶段、检查项、实际数值、阈值和修复目标。没有对应数值时 actual/threshold 使用 null。passed=true 时 issues 必须为空且 repair.command=none。
修复建议只能选择：none；refit_sagittal_leg_corrections（腿部骨点矢状面校正后重新 Fit）；clean_and_refit（清理重复／退化面后重新 Fit）。parameters 必须为空对象。肩胸权重或动画问题可路由到对应控件，但不得编造当前节点未声明的自动命令。建议不代表已执行；最终状态仍须保存重载并复测。
"""


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _request_ai(evidence, directory):
    from kimi_provider import DEFAULT_ENDPOINT, DEFAULT_MODEL

    config = dict(endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, key_env="KIMI_API_KEY")
    api_planner.validate_config(config)
    directory.mkdir()
    schema = review_schema()
    prompt = _prompt()
    content = prompt + "\n待审核 JSON 证据：\n" + canonical(evidence)
    body = dict(
        model=config["model"],
        messages=[dict(role="user", content=content)],
        response_format=dict(
            type="json_schema",
            json_schema=dict(name="humanoid_rigging_text_review", strict=True, schema=schema),
        ),
        reasoning_effort="low",
        max_tokens=8192,
        stream=False,
    )
    raw = canonical(body).encode("utf-8")
    require(len(raw) <= api_planner.MAX_REQUEST, "text_review_request_too_large")
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    (directory / "evidence.json").write_text(canonical(evidence), encoding="utf-8")
    (directory / "schema.json").write_text(canonical(schema), encoding="utf-8")
    (directory / "api-request.json").write_bytes(raw)
    api_planner.perform(config, directory)
    document = json.loads((directory / "api-plan.json").read_text(encoding="utf-8"))
    receipt = json.loads((directory / "api-receipt.json").read_text(encoding="utf-8"))
    require(
        receipt.get("request_sha256") == hashlib.sha256(raw).hexdigest()
        and receipt.get("instructions_sha256") == hashlib.sha256(canonical(document).encode()).hexdigest(),
        "text_review_output_invalid",
    )
    return document, receipt


def _text(value, code="text_review_output_invalid"):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 4000, code)


def _number_or_null(value):
    require(
        value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)),
        "text_review_output_invalid",
    )


def validate_document(document):
    require(isinstance(document, dict) and set(document) == {"schema_version", "passed", "summary", "issues", "repair"}, "text_review_output_invalid")
    require(document["schema_version"] == 1 and isinstance(document["passed"], bool), "text_review_output_invalid")
    _text(document["summary"])
    require(isinstance(document["issues"], list) and len(document["issues"]) <= 100, "text_review_output_invalid")
    for issue in document["issues"]:
        require(isinstance(issue, dict) and set(issue) == {"code", "stage", "check", "message", "actual", "threshold", "target"}, "text_review_output_invalid")
        for key in ("code", "check", "message"):
            _text(issue[key])
        require(issue["stage"] in STAGES and issue["target"] in TARGETS, "text_review_output_invalid")
        _number_or_null(issue["actual"])
        _number_or_null(issue["threshold"])
    repair = document["repair"]
    require(isinstance(repair, dict) and set(repair) == {"command", "parameters"}, "text_review_output_invalid")
    require(repair["command"] in COMMANDS and repair["parameters"] == {}, "text_review_output_invalid")
    if document["passed"]:
        require(not document["issues"] and repair["command"] == "none", "text_review_output_invalid")
    else:
        require(bool(document["issues"]), "text_review_output_invalid")
    return document


def _local_issues(validation):
    result = []
    for message in list(validation.get("issues", [])) + list(validation.get("unsupported", [])):
        result.append(
            dict(
                code="local_gate_failed",
                stage="capability",
                check="godot_numeric_validation",
                message=str(message),
                actual=None,
                threshold=None,
                target="rigging_node",
            )
        )
    return result


def review_candidate(request):
    required = {"source", "candidate", "directory", "validation", "attempts", "retry_count", "max_retries"}
    require(isinstance(request, dict) and set(request) == required, "invalid_input")
    source = Path(request["source"]).expanduser().resolve()
    candidate = Path(request["candidate"]).expanduser().resolve()
    directory = Path(request["directory"]).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() in (".glb", ".gltf"), "source_missing")
    require(candidate.is_file() and candidate.suffix.lower() == ".tscn", "candidate_missing")
    require(not directory.exists(), "review_output_exists")
    validation = request["validation"]
    require(
        isinstance(validation, dict)
        and isinstance(validation.get("passed"), bool)
        and isinstance(validation.get("scene_valid"), bool)
        and isinstance(validation.get("issues"), list)
        and isinstance(validation.get("unsupported"), list),
        "invalid_input",
    )
    attempts = request["attempts"]
    retry_count = request["retry_count"]
    max_retries = request["max_retries"]
    require(isinstance(attempts, list) and all(isinstance(item, dict) for item in attempts), "invalid_input")
    require(
        isinstance(retry_count, int)
        and not isinstance(retry_count, bool)
        and isinstance(max_retries, int)
        and not isinstance(max_retries, bool)
        and 0 <= retry_count <= max_retries <= MAX_ATTEMPTS,
        "invalid_input",
    )
    source_sha = _sha256(source)
    candidate_sha = _sha256(candidate)
    evidence = dict(
        node="humanoid_rig",
        tab="rigging",
        source_sha256=source_sha,
        candidate_sha256=candidate_sha,
        validation=validation,
        attempts=attempts,
        retry_count=retry_count,
        max_retries=max_retries,
        evidence_kind="godot_measured_text_only",
    )
    directory.mkdir(parents=True)
    document, api_receipt = _request_ai(evidence, directory / "request")
    document = validate_document(document)
    local_passed = validation["passed"] and validation["scene_valid"] and not validation["issues"] and not validation["unsupported"]
    passed = local_passed and document["passed"]
    issues = list(document["issues"])
    if not local_passed:
        issues.extend(_local_issues(validation))
    feedback = []
    for issue in issues:
        target = issue["target"]
        feedback.append(
            dict(
                node="humanoid_rig",
                tab="rigging",
                control=CONTROLS[target],
                stage=issue["stage"],
                code=issue["code"],
                check=issue["check"],
                actual=issue["actual"],
                threshold=issue["threshold"],
                message=issue["message"],
                source_sha256=source_sha,
                candidate_sha256=candidate_sha,
                evidence="request/evidence.json",
                recommended_command=document["repair"]["command"],
                recommended_parameters=document["repair"]["parameters"],
                auto_modify=document["repair"]["command"] != "none" and validation["scene_valid"] and retry_count < max_retries,
                requires_source_ai_review=False,
                retry_count=retry_count,
                max_retries=max_retries,
            )
        )
    result = dict(
        schema_version=1,
        text_only=True,
        synthetic=False,
        passed=passed,
        local_passed=local_passed,
        summary=document["summary"] if local_passed else "本地硬门禁未通过；文本审核不能改判为通过。",
        source_sha256=source_sha,
        candidate_sha256=candidate_sha,
        issues=issues,
        feedback=feedback,
        repair=document["repair"],
        retry_count=retry_count,
        max_retries=max_retries,
        review_document=document,
        api_receipt=api_receipt,
        evidence_path="request/evidence.json",
        report_path="review-receipt.json",
    )
    (directory / "review-receipt.json").write_text(canonical(result), encoding="utf-8")
    return result
