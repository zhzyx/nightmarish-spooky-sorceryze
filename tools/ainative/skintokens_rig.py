"""Independent local SkinTokens auto-rigging pipeline. No cloud service, no Blender.

This module is a self-contained addition to the Maliang toolchain. It never
imports or changes the existing ComfyUI/Kimi/motion providers, and the
Workbench only calls it for the explicit SkinTokens route. Removing this file,
its config and the route wiring fully rolls the feature back.

Trusted local configuration (copy skintokens-config.example.json outside the
repository, or keep it under the ignored local runtime):

    {
      "cli": "ABSOLUTE_PATH/skintokens-cli",
      "model_dir": "ABSOLUTE_PATH/SkinTokens-GGUF/F16",
      "device": "cpu",
      "postprocess": false,
      "timeout_seconds": 3600,
      "fingerprint_weights": true
    }

CLI:

    python tools/ainative/skintokens_rig.py --config CONFIG \
        --source INPUT.glb --output NEW_OUTPUT.glb [--report NEW_REPORT.json]

The source is never modified. The output and report must be new files; nothing
is overwritten. A failed run removes only its own partial output and never
retries inference automatically. Quality of the learned rig is not asserted by
this adapter; inspect deformation in the Workbench/Godot before production use.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WEIGHT_FILES = ("mesh-encoder.gguf", "skin-vae.gguf", "tokenrig.gguf")
DEVICES = ("cpu", "vulkan", "auto")
OPERATION = "skintokens_local_rig"


class PipelineError(Exception):
    """A definitive local configuration, input or execution failure."""


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path=None):
    """Read and validate the trusted config. No inference or network access."""
    config_path = path or os.environ.get("AINATIVE_SKINTOKENS_CONFIG", "")
    if not config_path:
        raise PipelineError(
            "缺少配置：请传 --config 或设置 AINATIVE_SKINTOKENS_CONFIG 指向本机 JSON 配置。"
        )
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PipelineError(f"无法读取配置 {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PipelineError("配置必须是 JSON 对象。")
    for key in ("cli", "model_dir"):
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise PipelineError(f"配置缺少非空字符串字段：{key}")
    cli = Path(data["cli"])
    if not cli.is_file():
        raise PipelineError(f"skintokens-cli 不存在：{cli}（请先编译，见 SKINTOKENS.md）")
    model_dir = Path(data["model_dir"])
    missing = [name for name in WEIGHT_FILES if not (model_dir / name).is_file()]
    if missing:
        raise PipelineError(f"模型权重目录 {model_dir} 缺少文件：{', '.join(missing)}")
    device = data.get("device", "cpu")
    if device not in DEVICES:
        raise PipelineError(f"device 必须是 {DEVICES} 之一。")
    timeout = data.get("timeout_seconds", 3600)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 86400:
        raise PipelineError("timeout_seconds 必须是 (0, 86400] 内的数值。")
    return {
        "config_path": str(Path(config_path).resolve()),
        "cli": str(cli.resolve()),
        "model_dir": str(model_dir.resolve()),
        "device": device,
        "postprocess": bool(data.get("postprocess", False)),
        "timeout_seconds": float(timeout),
        "fingerprint_weights": bool(data.get("fingerprint_weights", True)),
    }


def read_glb_json(path):
    """Return the glTF JSON document of a .glb, with strict container checks."""
    raw = Path(path).read_bytes()
    if len(raw) < 20 or raw[:4] != b"glTF":
        raise PipelineError(f"不是 GLB 容器：{path}")
    version = int.from_bytes(raw[4:8], "little")
    declared = int.from_bytes(raw[8:12], "little")
    if version != 2 or declared != len(raw):
        raise PipelineError(f"GLB 头无效（版本 {version}，声明长度 {declared}，实际 {len(raw)}）：{path}")
    chunk_length = int.from_bytes(raw[12:16], "little")
    if raw[16:20] != b"JSON" or 20 + chunk_length > len(raw):
        raise PipelineError(f"GLB 缺少完整 JSON chunk：{path}")
    try:
        document = json.loads(raw[20:20 + chunk_length].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PipelineError(f"GLB JSON 无法解析：{path}：{exc}") from exc
    if not isinstance(document, dict):
        raise PipelineError(f"GLB JSON 必须是对象：{path}")
    return document


def validate_source(path):
    source = Path(path)
    if source.suffix.lower() != ".glb" or not source.is_file():
        raise PipelineError(f"源模型必须是已存在的 .glb 文件：{path}")
    document = read_glb_json(source)
    if not document.get("meshes"):
        raise PipelineError("源 GLB 不含网格，无法绑骨。")
    return {"source": str(source.resolve()), "source_sha256": _sha256(source)}


def summarize_rig(document):
    skins = document.get("skins") or []
    joints = sorted({joint for skin in skins for joint in skin.get("joints", []) if isinstance(joint, int)})
    if not skins or not joints:
        raise PipelineError("输出 GLB 不含骨骼蒙皮（skins/joints），绑骨结果无效。")
    if not document.get("meshes"):
        raise PipelineError("输出 GLB 不含网格。")
    return {"skin_count": len(skins), "joint_count": len(joints)}


def _weights_manifest(config):
    manifest = []
    for name in WEIGHT_FILES:
        item = Path(config["model_dir"]) / name
        entry = {"file": name, "bytes": item.stat().st_size}
        if config["fingerprint_weights"]:
            entry["sha256"] = _sha256(item)
        manifest.append(entry)
    return manifest


def run(config, source, output, report_path=None):
    """Execute exactly one local rig job; returns the provenance report."""
    started = time.monotonic()
    target = Path(output)
    if target.suffix.lower() != ".glb":
        raise PipelineError("输出路径必须以 .glb 结尾。")
    if target.exists():
        raise PipelineError(f"输出已存在，拒绝覆盖：{target}（每个绑定结果都是不可变新版本）")
    if report_path is not None and Path(report_path).exists():
        raise PipelineError(f"报告已存在，拒绝覆盖：{report_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        config["cli"], "rig", config["model_dir"],
        str(source), str(target), "--device", config["device"],
    ]
    if config["postprocess"]:
        command.append("--postprocess")
    created = False
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=config["timeout_seconds"],
        )
    except subprocess.TimeoutExpired as exc:
        # The target did not exist before this run, so anything present is ours.
        target.unlink(missing_ok=True)
        raise PipelineError(
            f"本地绑骨超时（{config['timeout_seconds']}s）。不会自动重试；请检查输入网格与设备配置。"
        ) from exc
    if completed.returncode != 0:
        target.unlink(missing_ok=True)
        diagnostic = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise PipelineError(f"skintokens-cli 失败（退出码 {completed.returncode}）：{diagnostic}")
    created = target.is_file()
    if not created:
        raise PipelineError("skintokens-cli 未生成输出文件。")
    try:
        summary = summarize_rig(read_glb_json(target))
    except PipelineError:
        target.unlink(missing_ok=True)  # remove only this run's own invalid output
        raise
    report = {
        "schema_version": 1,
        "provider": "skintokens_local",
        "operation": OPERATION,
        "source": str(source),
        "source_sha256": validate_source(source)["source_sha256"],
        "output": str(target.resolve()),
        "output_sha256": _sha256(target),
        "rig": summary,
        "device": config["device"],
        "postprocess": config["postprocess"],
        "cli": {"path": config["cli"], "sha256": _sha256(config["cli"])},
        "weights": _weights_manifest(config),
        "seconds": round(time.monotonic() - started, 3),
        "blender_used": False,
        "cloud_used": False,
        "fallback_used": False,
        "quality": "learned_auto_rig_not_reviewed",
    }
    if report_path is not None:
        report_file = Path(report_path)
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with report_file.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="本机 JSON 配置；缺省读取 AINATIVE_SKINTOKENS_CONFIG")
    parser.add_argument("--source", required=True, help="已存在的输入 .glb（不会被修改）")
    parser.add_argument("--output", required=True, help="新的输出 .glb（已存在则拒绝）")
    parser.add_argument("--report", help="可选的新 provenance JSON 路径")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        source = validate_source(args.source)
        report = run(config, source["source"], args.output, args.report)
    except PipelineError as exc:
        print(json.dumps({"state": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"state": "succeeded", "report": report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
