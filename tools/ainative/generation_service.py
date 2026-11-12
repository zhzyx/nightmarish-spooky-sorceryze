"""Local generation settings and read-only ComfyUI capability discovery.

Discovery never uploads inputs or submits prompts. Remote checkpoint hashes are
unknown unless a separately configured legacy deployment provides real hashes.
GUI runs therefore use a persisted run-scoped provider identity, preventing
cross-run reuse under an unverified model identity.
"""

import ipaddress
import json
import os
import re
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path

from kimi_work_image_provider import MESSAGES as KIMI_WORK_IMAGE_MESSAGES
from multi_image_provider import MESSAGES as MULTI_IMAGE_MESSAGES

KINDS = ("text_to_image", "image_to_image", "image_to_mesh", "text_to_mesh")
IMAGE_NODES = {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"}
MESH_NODES = {
    "LoadImage",
    "ImageOnlyCheckpointLoader",
    "CLIPVisionEncode",
    "Hunyuan3Dv2Conditioning",
    "EmptyLatentHunyuan3Dv2",
    "KSampler",
    "VAEDecodeHunyuan3D",
    "VoxelToMesh",
    "MeshSmoothNormals",
    "SaveGLB",
}
MESSAGES = {
    "cli_missing": "未找到可用的 Codex CLI。请选择本机已安装的 Codex 程序。",
    "cli_check_failed": "无法检测 Codex CLI，请检查程序路径和本机运行环境。",
    "cli_image_unavailable": "当前 Codex CLI 未提供内置图像生成能力，请更新或检查已有账号的功能。",
    "cli_unavailable": "未找到可用的 Codex CLI。请选择本机已安装的 Codex 程序。",
    "cli_login_required": "Codex CLI 需要使用你已有的 ChatGPT 登录；请先完成 CLI 登录，再检测连接。",
    "service_not_configured": "尚未配置真实生成服务。请打开“本机设置”，选择 GPT CLI 网格建模或其他生成方式，检测并保存；离线复制仍可使用。",
    "service_config_invalid": "生成设置无效。请在“本机设置”检查生成方式及其所需的本机程序或服务参数并保存。",
    "service_address_invalid": "服务地址无效。请填写 http:// 或 https:// 服务根地址，不要包含账号、密码、查询参数或接口路径。",
    "service_unreachable": "无法连接 ComfyUI。请确认服务已启动、地址与端口正确，再点击“检测连接与模型”。",
    "service_protocol_invalid": "该地址未返回兼容的 ComfyUI 节点信息。请检查服务地址与 ComfyUI 版本。",
    "service_nodes_missing": "ComfyUI 缺少此生成类型需要的节点。请在“本机设置”检测连接，查看缺失节点并安装对应功能后重试。",
    "image_model_missing": "图像模型尚未选择或服务中不存在。请在“本机设置”检测并选择可用图像模型，再保存。",
    "mesh_model_missing": "网格模型尚未选择或服务中不存在。请在“本机设置”检测并选择可用网格模型，再保存。",
    "source_missing": "缺少源图像或源文件。请设置有效源文件，或连接已配置的上游节点后重试。",
    "source_invalid": "源文件格式无效或不受此节点支持。图像输入请选择 PNG/JPEG；网格复制请选择 GLB 或内嵌 glTF。",
    "prompt_missing": "缺少生成提示词。请在节点的提示词参数或文字说明中填写内容后重试。",
    "node_unsupported": "当前生成服务不支持该节点类型。请检查节点类型及“本机设置”的服务模式。",
    "run_service_missing": "本次运行的生成服务快照缺失，不能安全恢复。请保留当前记录并重新创建运行。",
    "editor_command_failed": "操作未完成。请检查节点输入与本机设置；本机诊断已记录不含凭据的错误类别。",
    "modeling_runtime_missing": "指令建模需要有效的 Godot 程序和内置构造工具，请使用包含该功能的马良引擎。",
    "sculpt_runtime_missing": "复杂网格构造器尚未就绪，请在设置的环境页选择 Blender 4 或更高版本，并检查内置构造工具。",
    "kimi_key_missing": "未检测到 KIMI_API_KEY（或 MOONSHOT_API_KEY）环境变量；请在本机设置后重启马良。",
    "kimi_endpoint_invalid": "Kimi 服务地址或模型不受支持；只允许官方 HTTPS 建模接口。",
    "kimi_auth_required": "Kimi 接口未接受当前凭据；请检查密钥产品与接口是否匹配。",
    "kimi_model_unavailable": "当前 Kimi 接口未提供所选模型，请检测模型列表并修正设置。",
    "kimi_rate_limited": "Kimi 接口当前限流；本任务未自动重发，请稍后显式重试。",
    "kimi_unreachable": "无法连接 Kimi 官方接口；请检查网络后重试，系统不会自动重复提交。",
    "api_timeout": "Kimi 建模请求超时；远程回执可能不明，不会自动重发。",
}
# Keep image-tool failures actionable without replacing generic routing errors.
MESSAGES.update({key: value for key, value in KIMI_WORK_IMAGE_MESSAGES.items() if key not in MESSAGES})
MESSAGES.update(MULTI_IMAGE_MESSAGES)


class ServiceError(ValueError):
    def __init__(self, code, *, missing_nodes=()):
        self.code = code if code in MESSAGES else "editor_command_failed"
        # Only known class identifiers may enter a user-visible diagnostic.
        self.missing_nodes = sorted(set(missing_nodes) & (IMAGE_NODES | MESH_NODES | {"ImageScale", "VAEEncode"}))
        message = MESSAGES[self.code]
        if self.missing_nodes:
            message += " 缺少：" + "、".join(self.missing_nodes)
        super().__init__(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ServiceError("service_address_invalid")


def settings(value):
    if not isinstance(value, dict) or set(value) - {
        "schema_version",
        "mode",
        "endpoint",
        "image_model",
        "mesh_model",
        "cli_path",
        "godot_path",
        "builder_path",
        "blender_path",
        "kimi_model",
        "api_model",
        "api_key_env",
        "image_tool_path",
        "image_pythonw_path",
        "model3d_tool_path",
        "model3d_pythonw_path",
        "model3d_model",
        "image_board_godot_path",
        "image_board_builder_path",
    }:
        raise ServiceError("service_config_invalid")
    result = dict(schema_version=1, mode="offline", endpoint="http://127.0.0.1:8188", image_model="", mesh_model="")
    result.update(value)
    if (
        result["schema_version"] != 1
        or isinstance(result["schema_version"], bool)
        or result["mode"]
        not in (
            "offline",
            "comfy",
            "codex",
            "codex_modeling",
            "codex_sculpt",
            "kimi_native",
            "local_mesh",
            "api_modeling",
            "api_sculpt",
        )
    ):
        raise ServiceError("service_config_invalid")
    if not all(isinstance(result[key], str) for key in ("endpoint", "image_model", "mesh_model")):
        raise ServiceError("service_config_invalid")
    for key in ("image_board_godot_path", "image_board_builder_path"):
        if key in result:
            if not isinstance(result[key], str):
                raise ServiceError("service_config_invalid")
            result[key] = result[key].strip()
    for key in ("image_model", "mesh_model"):
        name = result[key]
        if name and (
            name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/") or any(ord(c) < 32 for c in name)
        ):
            raise ServiceError("service_config_invalid")
    if result["mode"] in ("api_modeling", "api_sculpt"):
        from api_planner import validate_config

        try:
            validate_config(
                dict(endpoint=result["endpoint"], model=result.get("api_model"), key_env=result.get("api_key_env"))
            )
        except ValueError:
            raise ServiceError("service_config_invalid") from None
        runtime = "godot_path" if result["mode"] == "api_modeling" else "blender_path"
        if not all(isinstance(result.get(k), str) and result[k].strip() for k in (runtime, "builder_path")):
            raise ServiceError("modeling_runtime_missing")
        if (
            any(
                k in result
                for k in ("cli_path", "kimi_model", "blender_path" if runtime == "godot_path" else "godot_path")
            )
            or result["image_model"]
            or result["mesh_model"]
        ):
            raise ServiceError("service_config_invalid")
        return result
    if "api_model" in result or "api_key_env" in result:
        raise ServiceError("service_config_invalid")
    if result["mode"] in ("codex", "codex_modeling", "codex_sculpt"):
        result.setdefault("cli_path", "codex")
        if not isinstance(result["cli_path"], str) or not result["cli_path"].strip():
            raise ServiceError("cli_unavailable")
    elif "cli_path" in result:
        raise ServiceError("service_config_invalid")
    if result["mode"] == "kimi_native":
        from kimi_provider import (
            DEFAULT_ENDPOINT,
            DEFAULT_MODEL,
            MODEL3D_GENERATE_MODELS,
            validate_endpoint,
            validate_model,
        )

        result.setdefault("endpoint", DEFAULT_ENDPOINT)
        result.setdefault("kimi_model", DEFAULT_MODEL)
        result.setdefault("model3d_model", "v3.1")
        try:
            result["endpoint"] = validate_endpoint(result["endpoint"])
            result["kimi_model"] = validate_model(result["kimi_model"])
        except ValueError:
            raise ServiceError("kimi_endpoint_invalid") from None
        if result["image_model"] or result["mesh_model"]:
            raise ServiceError("service_config_invalid")
        if not isinstance(result["model3d_model"], str) or result["model3d_model"] not in MODEL3D_GENERATE_MODELS:
            raise ServiceError("service_config_invalid")
        for key in ("image_tool_path", "image_pythonw_path", "model3d_tool_path", "model3d_pythonw_path"):
            if key in result:
                if not isinstance(result[key], str):
                    raise ServiceError("service_config_invalid")
                result[key] = result[key].strip()
    elif "kimi_model" in result or any(
        key in result
        for key in (
            "image_tool_path",
            "image_pythonw_path",
            "model3d_tool_path",
            "model3d_pythonw_path",
            "model3d_model",
        )
    ):
        raise ServiceError("service_config_invalid")
    if result["mode"] == "codex_modeling":
        if not all(isinstance(result.get(key), str) and result[key].strip() for key in ("godot_path", "builder_path")):
            raise ServiceError("modeling_runtime_missing")
        if "blender_path" in result:
            raise ServiceError("service_config_invalid")
    elif result["mode"] == "codex_sculpt":
        if not all(
            isinstance(result.get(key), str) and result[key].strip() for key in ("blender_path", "builder_path")
        ):
            raise ServiceError("sculpt_runtime_missing")
        if "godot_path" in result:
            raise ServiceError("service_config_invalid")
    elif result["mode"] != "kimi_native" and any(key in result for key in ("godot_path", "builder_path")):
        raise ServiceError("service_config_invalid")
    elif result["mode"] != "kimi_native" and "blender_path" in result:
        raise ServiceError("service_config_invalid")
    if result["mode"] in ("comfy", "codex", "local_mesh"):
        try:
            url = urllib.parse.urlsplit(result["endpoint"].strip())
            valid = (
                url.scheme in ("http", "https")
                and url.hostname
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment
                and url.path in ("", "/")
            )
            _ = url.port
        except ValueError:
            valid = False
        if not valid:
            raise ServiceError("service_address_invalid")
        result["endpoint"] = result["endpoint"].strip().rstrip("/")
        if result["mode"] in ("codex", "local_mesh") and (
            url.hostname not in ("127.0.0.1", "localhost", "::1") or url.scheme != "http"
        ):
            raise ServiceError("service_address_invalid")
    return result


def load_settings(path):
    if not path or not Path(path).is_file():
        return settings({})
    try:
        return settings(json.loads(Path(path).read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, TypeError) as error:
        if isinstance(error, ServiceError):
            raise
        raise ServiceError("service_config_invalid") from None


def read_endpoint(endpoint, route):
    try:
        request = urllib.request.Request(endpoint + route, method="GET")
        host = urllib.parse.urlsplit(endpoint).hostname
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host == "localhost"
        handlers = [urllib.request.ProxyHandler({})] if local else []
        with urllib.request.build_opener(*handlers, NoRedirect()).open(request, timeout=8) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise ServiceError("service_protocol_invalid")
        return json.loads(data)
    except ServiceError:
        raise
    except (urllib.error.URLError, OSError, TimeoutError):
        raise ServiceError("service_unreachable") from None
    except (ValueError, UnicodeError):
        raise ServiceError("service_protocol_invalid") from None


def model_names(info, node):
    try:
        choices = info[node]["input"]["required"]["ckpt_name"][0]
        if not isinstance(choices, list) or not all(isinstance(name, str) for name in choices):
            return []
        return sorted(set(choices))
    except (KeyError, TypeError, IndexError):
        return []


def capability(kind, config, info, models, extra_image=False):
    if config["mode"] == "local_mesh" and (kind != "image_to_mesh" or extra_image):
        return dict(
            ready=False,
            code="service_not_configured",
            message="本机网格仅接受直接图生网格，不提供重绘。",
            missing_nodes=[],
        )
    required = set(MESH_NODES if kind == "image_to_mesh" else IMAGE_NODES)
    if kind == "image_to_image":
        required.discard("EmptyLatentImage")
        required |= {"LoadImage", "ImageScale", "VAEEncode"}
    if kind == "text_to_mesh":
        required = (IMAGE_NODES - {"SaveImage"}) | (MESH_NODES - {"LoadImage"})
    if extra_image:
        required.discard("EmptyLatentImage")
        required |= (IMAGE_NODES - {"EmptyLatentImage", "SaveImage"}) | {"LoadImage", "ImageScale", "VAEEncode"}
    missing = sorted(required - set(info))
    code = ""
    if missing:
        code = "service_nodes_missing"
    elif (kind != "image_to_mesh" or extra_image) and config["image_model"] not in models["image"]:
        code = "image_model_missing"
    elif kind.endswith("mesh") and config["mesh_model"] not in models["mesh"]:
        code = "mesh_model_missing"
    message = MESSAGES[code] if code else "已就绪；模型由服务提供，远端权重摘要未验证。"
    if missing:
        message += " 缺少：" + "、".join(missing)
    return dict(ready=not code, code=code, message=message, missing_nodes=missing)


def _probe_service(value):
    reported_mode = value.get("mode", "comfy") if isinstance(value, dict) else "comfy"
    fallback_mode = (
        reported_mode
        if reported_mode
        in (
            "comfy",
            "codex",
            "codex_modeling",
            "codex_sculpt",
            "kimi_native",
            "local_mesh",
            "api_modeling",
            "api_sculpt",
        )
        else "comfy"
    )
    try:
        config = settings(value)
        if config["mode"] in ("api_modeling", "api_sculpt"):
            return _probe_api(config), {}
        if config["mode"] == "kimi_native":
            return _probe_kimi(config), {}
        if config["mode"] == "codex_sculpt":
            return _probe_sculpt(config), {}
        if config["mode"] == "codex_modeling":
            return _probe_modeling(config), {}
        if config["mode"] == "codex":
            return _probe_codex(config)
        if config["mode"] == "offline":
            return dict(
                mode="offline",
                connected=False,
                models={"image": [], "mesh": []},
                capabilities={
                    kind: dict(ready=False, code="service_not_configured", message=MESSAGES["service_not_configured"])
                    for kind in KINDS
                },
                backend_revision="",
                message="当前为离线复制演示；未连接真实生成服务。",
            ), {}
        info = read_endpoint(config["endpoint"], "/object_info")
        if not isinstance(info, dict) or not info or not any(key in info for key in IMAGE_NODES | MESH_NODES):
            raise ServiceError("service_protocol_invalid")
        models = dict(
            image=model_names(info, "CheckpointLoaderSimple"), mesh=model_names(info, "ImageOnlyCheckpointLoader")
        )
        revision = "unreported"
        try:
            stats = read_endpoint(config["endpoint"], "/system_stats")
            reported = stats.get("system", {}).get("comfyui_version") if isinstance(stats, dict) else None
            if isinstance(reported, str) and len(reported) < 200 and not any(ord(c) < 32 for c in reported):
                revision = reported
        except ServiceError:
            pass
        result = dict(
            mode=config["mode"],
            connected=True,
            models=models,
            capabilities={kind: capability(kind, config, info, models) for kind in KINDS},
            variants={"image_to_mesh_redraw": capability("image_to_mesh", config, info, models, extra_image=True)},
            backend_revision=revision,
            message="已连接 ComfyUI；请选择需要的模型并保存。",
        )
        return result, info
    except ServiceError as error:
        return dict(
            mode=fallback_mode,
            connected=False,
            models={"image": [], "mesh": []},
            capabilities={kind: dict(ready=False, code=error.code, message=str(error)) for kind in KINDS},
            backend_revision="",
            message=str(error),
            code=error.code,
        ), {}


def check_service(value):
    return _probe_service(value)[0]


def _probe_api(config):
    from api_planner import check_configuration
    from modeling_provider import MESSAGES as API_MESSAGES

    auth = check_configuration(
        dict(endpoint=config["endpoint"], model=config["api_model"], key_env=config["api_key_env"])
    )
    runtime = "godot_path" if config["mode"] == "api_modeling" else "blender_path"
    ready = auth["connected"] and Path(config[runtime]).is_file() and Path(config["builder_path"]).is_file()
    code = "" if ready else auth["code"] or "modeling_runtime_missing"
    return dict(
        mode=config["mode"],
        connected=ready,
        code=code,
        models=dict(image=[], mesh=[]),
        backend_revision="configured-api-v1",
        message="仅核对本机配置；API 可达性和生成能力以任务回执为准。",
        capabilities={
            kind: dict(
                ready=ready and kind.endswith("mesh"),
                code=code if kind.endswith("mesh") else "service_not_configured",
                message=API_MESSAGES.get(code, MESSAGES.get(code, "仅支持语义建模")),
            )
            for kind in KINDS
        },
    )


def _probe_kimi(config):
    from kimi_provider import check_model3d_tool
    from kimi_work_image_provider import GENERATION_VERSION, check_image_tool

    model3d_report = check_model3d_tool(config.get("model3d_tool_path", ""), config.get("model3d_pythonw_path", ""))
    ready = bool(model3d_report.get("connected"))
    message = model3d_report.get("message", "")
    mesh = dict(
        ready=ready,
        code=model3d_report.get("code", ""),
        message=message,
        missing_nodes=[],
    )
    image_report = check_image_tool(config.get("image_tool_path", ""), config.get("image_pythonw_path", ""))
    image_ready = bool(image_report.get("connected"))
    image = dict(
        ready=image_ready,
        code=image_report.get("code", ""),
        message=image_report.get("message", MESSAGES["image_tool_invalid"]),
        missing_nodes=[],
    )
    if ready and image_ready:
        summary = "Mesh 使用 Tripo API 直接生成 GLB；二维使用独立 Kimi Work 图像服务。检测未上传或生成，不调用 Blender、ComfyUI、混元或 Codex。"
    elif image_ready:
        summary = "Kimi Work 图像工具已就绪；Mesh 状态独立显示。检测未上传参考图或生成图像。" + message
    else:
        summary = "Tripo API 直接三维工具已就绪；二维需另行配置 Kimi Work 图像工具。" if ready else message
    return dict(
        mode="kimi_native",
        connected=ready or image_ready,
        model3d=model3d_report,
        kimi_work_image=image_report,
        models=dict(
            image=["Kimi Work agent-gw generate_image " + GENERATION_VERSION] if image_ready else [],
            mesh=["Tripo API generate_3d_model v1 (" + config["model3d_model"] + ")"] if ready else [],
        ),
        capabilities=dict(
            text_to_image=dict(image),
            image_to_image=dict(image),
            text_to_mesh=mesh,
            image_to_mesh=dict(mesh),
        ),
        backend_revision="kimi-native-3d-v1|"
        + config["model3d_model"]
        + "|"
        + model3d_report.get("tool_fingerprint", model3d_report.get("code", "unavailable"))
        + "|kimi-work-image-v2|"
        + image_report.get("tool_fingerprint", image_report.get("code", "unavailable")),
        message=summary,
    )


def _probe_modeling(config):
    from codex_provider import check_cli
    from modeling_provider import check_modeling_cli

    cli = check_modeling_cli(config["cli_path"])
    image_cli = check_cli(config["cli_path"])
    runtime = all(Path(config[key]).is_file() for key in ("godot_path", "builder_path"))
    ready = cli.get("connected", False) and runtime
    mesh = dict(
        ready=ready,
        code="" if ready else cli.get("code") or "modeling_runtime_missing",
        message="GPT 建模指令与 Godot 构造器已就绪；适合原语组合，复杂人物与有机造型尚未验证。"
        if ready
        else cli.get("message", "")
        if not cli.get("connected")
        else MESSAGES["modeling_runtime_missing"],
        missing_nodes=[],
    )
    image = dict(
        ready=image_cli.get("connected", False),
        code=image_cli.get("code", ""),
        message=image_cli.get("message", ""),
        missing_nodes=[],
    )
    return dict(
        mode="codex_modeling",
        connected=ready,
        cli=cli,
        models=dict(image=["builtin"], mesh=[]),
        capabilities=dict(text_to_image=image, image_to_image=image, text_to_mesh=mesh, image_to_mesh=mesh),
        backend_revision=cli.get("version", "") + "|godot-modeling-v1",
        message="图像由 Codex CLI 生成；网格由 GPT 建模指令和 Godot 构造，无需 ComfyUI 或三维 AI 权重。",
    )


def _blender_runtime(config):
    executable = shutil.which(config["blender_path"])
    builder = Path(config["builder_path"])
    if (
        not executable
        or not builder.is_file()
        or not all(
            builder.with_name(name).is_file()
            for name in (
                "anatomy_base.py",
                "anatomy_body.py",
                "character_detail.py",
                "organic_detail.py",
                "period_groom.py",
                "anatomy_calibration.py",
            )
        )
    ):
        return None
    try:
        from sculpt_provider import load_operator_calibration

        load_operator_calibration(builder)
        process = subprocess.run(
            [executable, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        match = re.search(rb"Blender\s+(\d+)\.(\d+)", process.stdout)
        if process.returncode != 0 or not match or int(match.group(1)) < 4:
            return None
        return dict(executable=str(Path(executable).resolve()), version=match.group(0).decode("ascii"))
    except (OSError, ValueError, SyntaxError, ImportError, subprocess.TimeoutExpired):
        return None


def _probe_sculpt(config):
    from codex_provider import check_cli
    from modeling_provider import check_modeling_cli

    runtime = _blender_runtime(config)
    cli = (
        check_modeling_cli(config["cli_path"])
        if runtime
        else dict(connected=False, code="sculpt_runtime_missing", message=MESSAGES["sculpt_runtime_missing"])
    )
    image_cli = check_cli(config["cli_path"])
    ready = bool(cli.get("connected") and runtime)
    mesh = dict(
        ready=ready,
        code="" if ready else cli.get("code") or "sculpt_runtime_missing",
        message="GPT 建模计划与 Blender 构造器已连接；具体人物、有机形态和遮挡补全结果需运行后检查。"
        if ready
        else cli.get("message", "")
        if not cli.get("connected")
        else MESSAGES["sculpt_runtime_missing"],
        missing_nodes=[],
    )
    image = dict(
        ready=image_cli.get("connected", False),
        code=image_cli.get("code", ""),
        message=image_cli.get("message", ""),
        missing_nodes=[],
    )
    return dict(
        mode="codex_sculpt",
        connected=ready,
        cli=cli,
        runtime=runtime,
        models=dict(image=["builtin"], mesh=[]),
        capabilities=dict(text_to_image=image, image_to_image=image, text_to_mesh=mesh, image_to_mesh=mesh),
        backend_revision=cli.get("version", "") + "|sculpt-v2|" + (runtime["version"] if runtime else "unavailable"),
        message="图像和建模规划使用 GPT CLI；Blender 在本机执行控制网格、放样和表面融合，无需 ComfyUI 或三维 AI 权重。",
    )


def _probe_codex(config, *, inspect_cli=True):
    from codex_provider import check_cli

    cli = (
        check_cli(config["cli_path"])
        if inspect_cli
        else {"code": "cli_not_checked", "message": "本次图生网格只使用本机模型。"}
    )
    mesh_config = {k: v for k, v in config.items() if k != "cli_path"}
    mesh_config.update(mode="comfy", image_model="")
    mesh_report, info = _probe_service(mesh_config)
    image_ready = bool(cli.get("connected") and cli.get("image_generation"))
    mesh_ready = (
        capability("image_to_mesh", mesh_config, info, mesh_report.get("models", {}))
        if info
        else dict(
            ready=False, code="service_unreachable", message="本机网格模型尚未连接，请启动本机模型。", missing_nodes=[]
        )
    )
    image = dict(
        ready=image_ready,
        code=cli.get("code", "cli_unavailable"),
        message=cli.get("message", MESSAGES["cli_unavailable"]),
        missing_nodes=[],
    )
    combined = mesh_ready if image_ready else image
    report = dict(
        mode="codex",
        connected=image_ready or mesh_ready["ready"],
        cli=cli,
        models=dict(image=["builtin"], mesh=mesh_report.get("models", {}).get("mesh", [])),
        capabilities={
            "text_to_image": image,
            "image_to_image": image,
            "image_to_mesh": mesh_ready,
            "text_to_mesh": combined,
        },
        variants={"image_to_mesh_redraw": combined},
        backend_revision=cli.get("version", "") + "|local-mesh:" + mesh_report.get("backend_revision", ""),
        message="Codex CLI 图像能力已连接；图像使用当前登录额度，网格由本机模型执行。"
        if image_ready
        else ("本机网格模型已就绪。" if mesh_ready["ready"] else "") + image["message"],
    )
    return report, info


def register_workflow(registry):
    from multi_image_provider import register_images

    register_images(registry)


def image_batch_settings(config):
    if config.get("mode") == "kimi_native":
        builder = config.get("builder_path") or config.get("image_board_builder_path", "")
        board = dict(
            board_godot_path=config.get("godot_path") or config.get("image_board_godot_path", ""),
            board_builder_path=str(Path(builder).with_name("image_contact_sheet.gd")) if builder else "",
        )
    else:
        board = dict(
            board_godot_path=config.get("image_board_godot_path", ""),
            board_builder_path=config.get("image_board_builder_path", ""),
        )
    return dict(enabled=True, board_config=board)


def adapt_image_providers(providers, database, batch):
    if not batch or not batch.get("enabled"):
        return providers
    from multi_image_provider import MultiImageProvider

    for name in ("comfy", "codex", "kimi_work_image"):
        if name in providers:
            providers[name] = MultiImageProvider(
                providers[name],
                Path(database).resolve().parent / "multi-image-state" / name,
                batch.get("board_config", {}),
            )
    return providers


def check_inputs(model):
    for node in model["nodes"]:
        kind = node.get("type", "copy")
        if kind not in (*KINDS, "copy"):
            raise ServiceError("node_unsupported")
        incoming = [edge for edge in model["edges"] if edge["to"] == node["id"]]
        source = node.get("source", "")
        source_paths = node.get("source_paths", [source] if source else [])
        context_paths = node.get("image_context_paths", [])
        if not isinstance(source_paths, list) or not isinstance(context_paths, list):
            raise ServiceError("source_invalid")
        if (
            kind.startswith("image_")
            and not incoming
            and not source
            and not any(source_paths)
            and not node.get("source_snapshot")
            and not node.get("source_snapshots")
        ):
            raise ServiceError("source_missing")
        if kind == "copy" and len(source_paths) + len(context_paths) > 1:
            raise ServiceError("source_invalid")
        for path in [*source_paths, *context_paths]:
            if not isinstance(path, str) or path and not Path(path).is_file():
                raise ServiceError("source_missing")
            if kind != "copy" and path and Path(path).suffix.lower() not in (".png", ".jpg", ".jpeg"):
                raise ServiceError("source_invalid")
        if kind in KINDS and kind != "image_to_mesh":
            prompt = str(node.get("parameters", {}).get("prompt", "")) + str(node.get("text", ""))
            if not prompt.strip():
                raise ServiceError("prompt_missing")


def prepare_provider(config, model, database, run_id):
    from comfy_provider import ComfyProvider, LocalMeshProvider, register
    from editor_demo import factory

    registry, providers = factory()
    generated = [node for node in model["nodes"] if node.get("type", "copy") in KINDS]
    if not generated:
        return registry, providers, {"mode": "offline"}
    if config["mode"] in ("api_modeling", "api_sculpt"):
        report = _probe_api(config)
        if not report["connected"] or any(not node["type"].endswith("mesh") for node in generated):
            raise ServiceError(report.get("code") or "service_not_configured")
        from modeling_provider import ModelingProvider
        from sculpt_provider import SculptProvider

        provider_id = "api-modeling" if config["mode"] == "api_modeling" else "api-sculpt"
        runtime = "godot_path" if config["mode"] == "api_modeling" else "blender_path"
        provider_config = dict(
            planner=dict(endpoint=config["endpoint"], model=config["api_model"], key_env=config["api_key_env"]),
            storage=str(Path(database).resolve().parent / (provider_id + "-state")),
            builder_path=config["builder_path"],
        )
        provider_config[runtime] = config[runtime]
        register(registry)
        providers[provider_id] = (ModelingProvider if runtime == "godot_path" else SculptProvider)(provider_config)
        for node in generated:
            node["provider"] = provider_id
        return registry, providers, dict(mode=config["mode"], provider=provider_config)
    if config["mode"] == "kimi_native":
        from kimi_provider import KimiNativeDirectProvider
        from kimi_work_image_provider import KimiWorkImageProvider

        report = _probe_kimi(config)
        for node in generated:
            capability_report = report["capabilities"][node["type"]]
            if not capability_report["ready"]:
                raise ServiceError(capability_report.get("code") or "service_not_configured")
        mesh_nodes = [node for node in generated if node["type"].endswith("mesh")]
        image_nodes = [node for node in generated if not node["type"].endswith("mesh")]
        provider_config = dict(
            tool_path=config.get("model3d_tool_path", ""),
            pythonw_path=config.get("model3d_pythonw_path", ""),
            storage=str(Path(database).resolve().parent / "kimi-native-3d-state"),
            model=config["model3d_model"],
        )
        snapshot = dict(mode="kimi_native", provider=provider_config if mesh_nodes else None)
        register_workflow(registry)
        if mesh_nodes:
            providers["kimi_native"] = KimiNativeDirectProvider(provider_config)
        if image_nodes:
            image_config = dict(
                tool_path=config.get("image_tool_path", ""),
                pythonw_path=config.get("image_pythonw_path", ""),
                storage=str(Path(database).resolve().parent / "kimi-work-image-state"),
            )
            providers["kimi_work_image"] = KimiWorkImageProvider(image_config)
            snapshot["image_provider"] = image_config
        for node in generated:
            node["provider"] = "kimi_native" if node["type"].endswith("mesh") else "kimi_work_image"
        return registry, providers, snapshot
    if config["mode"] == "codex_sculpt":
        from codex_provider import CodexProvider, check_cli

        image_config = dict(
            cli_path=config["cli_path"], storage=str(Path(database).resolve().parent / "codex-state"), mesh_config=None
        )
        if all(not node["type"].endswith("mesh") for node in generated):
            # A pure image workflow must not import the optional sculpt stack,
            # probe Blender or persist an unused mesh dependency for reopen.
            image_report = check_cli(config["cli_path"])
            if not image_report.get("connected"):
                raise ServiceError(image_report.get("code") or "cli_image_unavailable")
            register_workflow(registry)
            providers["codex"] = CodexProvider(image_config)
            for node in generated:
                node["provider"] = "codex"
            return registry, providers, dict(mode="codex_sculpt", provider=None, image_provider=image_config)

        report = _probe_sculpt(config)
        for node in generated:
            capability_report = report["capabilities"][node["type"]]
            if not capability_report["ready"]:
                raise ServiceError(capability_report.get("code", "service_not_configured"))
        try:
            from sculpt_provider import SculptProvider
        except ImportError:
            raise ServiceError("sculpt_runtime_missing") from None
        runtime = report["runtime"]
        provider_config = dict(
            cli_path=config["cli_path"],
            storage=str(Path(database).resolve().parent / "sculpt-state"),
            blender_path=runtime["executable"] if runtime else config["blender_path"],
            builder_path=config["builder_path"],
        )
        register_workflow(registry)
        providers["codex-sculpt"] = SculptProvider(provider_config)
        providers["codex"] = CodexProvider(image_config)
        for node in generated:
            node["provider"] = "codex-sculpt" if node["type"].endswith("mesh") else "codex"
        return registry, providers, dict(mode="codex_sculpt", provider=provider_config, image_provider=image_config)
    if config["mode"] == "codex_modeling":
        from codex_provider import CodexProvider
        from modeling_provider import ModelingProvider

        report = _probe_modeling(config)
        for node in generated:
            capability_report = report["capabilities"][node["type"]]
            if not capability_report["ready"]:
                raise ServiceError(capability_report.get("code", "service_not_configured"))
        provider_config = dict(
            cli_path=config["cli_path"],
            storage=str(Path(database).resolve().parent / "modeling-state"),
            godot_path=config["godot_path"],
            builder_path=config["builder_path"],
        )
        image_config = dict(
            cli_path=config["cli_path"], storage=str(Path(database).resolve().parent / "codex-state"), mesh_config=None
        )
        register_workflow(registry)
        providers["codex-modeling"] = ModelingProvider(provider_config)
        providers["codex"] = CodexProvider(image_config)
        for node in generated:
            node["provider"] = "codex-modeling" if node["type"].endswith("mesh") else "codex"
        return registry, providers, dict(mode="codex_modeling", provider=provider_config, image_provider=image_config)
    if config["mode"] == "codex":
        from codex_provider import CodexProvider

        requires_cli = any(
            node["type"] != "image_to_mesh"
            or str(node.get("parameters", {}).get("prompt", "")).strip()
            or str(node.get("text", "")).strip()
            for node in generated
        )
        report, info = _probe_codex(config, inspect_cli=requires_cli)
        for node in generated:
            kind = node["type"]
            ready = report["capabilities"][kind]
            prompt = str(node.get("parameters", {}).get("prompt", "")) + str(node.get("text", ""))
            if kind == "image_to_mesh" and prompt.strip():
                ready = report["variants"]["image_to_mesh_redraw"]
            if not ready["ready"]:
                raise ServiceError(
                    ready.get("code", "service_not_configured"), missing_nodes=ready.get("missing_nodes", ())
                )
        mesh = None
        if any(node["type"].endswith("mesh") for node in generated):
            mesh = dict(
                endpoint=config["endpoint"],
                storage=str(Path(database).resolve().parent / "comfy-state"),
                checkpoints={"image": dict(name="", sha256=None), "mesh": dict(name=config["mesh_model"], sha256=None)},
                backend_revision=report["backend_revision"] + "|unverified-weights;run=" + run_id,
            )
        provider_config = dict(
            cli_path=config["cli_path"], storage=str(Path(database).resolve().parent / "codex-state"), mesh_config=mesh
        )
        register_workflow(registry)
        providers["codex"] = CodexProvider(provider_config)
        for node in generated:
            node["provider"] = "codex"
        return registry, providers, dict(mode="codex", provider=provider_config)
    if config["mode"] not in ("comfy", "local_mesh"):
        raise ServiceError("service_not_configured")
    report, info = _probe_service(config)
    if not report["connected"]:
        raise ServiceError(report.get("code", "service_unreachable"))
    for node in generated:
        kind = node["type"]
        prompt = str(node.get("parameters", {}).get("prompt", "")) + str(node.get("text", ""))
        uses_image_edit = kind != "image_to_mesh" or bool(prompt.strip())
        has_reference = any(
            node.get(field)
            for field in (
                "source",
                "source_snapshot",
                "source_paths",
                "source_snapshots",
                "image_context",
                "image_context_snapshot",
                "image_context_paths",
                "image_context_snapshots",
            )
        )
        image_conditioning = uses_image_edit and (kind.startswith("image_") or has_reference)
        ready = capability(kind, config, info, report["models"], extra_image=image_conditioning)
        if not ready["ready"]:
            raise ServiceError(ready["code"], missing_nodes=ready["missing_nodes"])
    provider_config = dict(
        endpoint=config["endpoint"],
        storage=str(Path(database).resolve().parent / "comfy-state"),
        checkpoints={role: dict(name=config[role + "_model"], sha256=None) for role in ("image", "mesh")},
        backend_revision=report["backend_revision"] + "|unverified-weights;run=" + run_id,
    )
    register_workflow(registry)
    providers["comfy"] = (LocalMeshProvider if config["mode"] == "local_mesh" else ComfyProvider)(provider_config)
    return registry, providers, dict(mode=config["mode"], provider=provider_config)


def save_run_service(database, run_id, snapshot):
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS editor_run_services(run_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("INSERT INTO editor_run_services VALUES(?,?)", (run_id, json.dumps(snapshot, ensure_ascii=False)))


def run_service(database, run_id):
    with closing(sqlite3.connect(database)) as db, db:
        table = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='editor_run_services'"
        ).fetchone()
        if not table:
            return None
        row = db.execute("SELECT body FROM editor_run_services WHERE run_id=?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def restore_provider(snapshot):
    from comfy_provider import ComfyProvider, LocalMeshProvider
    from editor_demo import factory

    registry, providers = factory()
    if snapshot["mode"] in ("comfy", "local_mesh"):
        register_workflow(registry)
        providers["comfy"] = (LocalMeshProvider if snapshot["mode"] == "local_mesh" else ComfyProvider)(
            snapshot["provider"]
        )
    elif snapshot["mode"] in ("api_modeling", "api_sculpt"):
        from modeling_provider import ModelingProvider
        from sculpt_provider import SculptProvider

        register_workflow(registry)
        if snapshot["mode"] == "api_modeling":
            providers["api-modeling"] = ModelingProvider(snapshot["provider"])
        else:
            providers["api-sculpt"] = SculptProvider(snapshot["provider"])
    elif snapshot["mode"] == "kimi_native":
        from kimi_provider import KimiNativeDirectProvider, KimiNativeProvider
        from kimi_work_image_provider import KimiWorkImageProvider

        register_workflow(registry)
        # Old Mesh-only snapshots intentionally have no image_provider field.
        if snapshot["provider"] is not None:
            provider_class = KimiNativeDirectProvider if "tool_path" in snapshot["provider"] else KimiNativeProvider
            providers["kimi_native"] = provider_class(snapshot["provider"])
        if snapshot.get("image_provider") is not None:
            providers["kimi_work_image"] = KimiWorkImageProvider(snapshot["image_provider"])
    elif snapshot["mode"] == "codex":
        from codex_provider import CodexProvider

        register_workflow(registry)
        providers["codex"] = CodexProvider(snapshot["provider"])
    elif snapshot["mode"] == "codex_modeling":
        from codex_provider import CodexProvider
        from modeling_provider import ModelingProvider

        register_workflow(registry)
        providers["codex-modeling"] = ModelingProvider(snapshot["provider"])
        providers["codex"] = CodexProvider(snapshot["image_provider"])
    elif snapshot["mode"] == "codex_sculpt":
        from codex_provider import CodexProvider

        register_workflow(registry)
        if snapshot["provider"] is not None:
            try:
                from sculpt_provider import SculptProvider
            except ImportError:
                raise ServiceError("sculpt_runtime_missing") from None
            providers["codex-sculpt"] = SculptProvider(snapshot["provider"])
        providers["codex"] = CodexProvider(snapshot["image_provider"])
    if snapshot.get("image_batch", {}).get("enabled"):
        batch = snapshot["image_batch"]
        stored = snapshot.get("provider") or snapshot.get("image_provider") or {}
        storage = stored.get("storage", str(Path.cwd()))
        # New runs persist the exact parent state location. Legacy fallback is
        # retained only for snapshots written before multi-image support.
        database = batch.get("database", str(Path(storage) / "restore.sqlite"))
        providers = adapt_image_providers(providers, database, batch)
    return registry, providers


def failure(error):
    code = error.code if isinstance(error, ServiceError) else "editor_command_failed"
    if isinstance(error, FileNotFoundError):
        code = "source_missing"
    elif isinstance(error, ValueError):
        known = {
            "unsupported asset": "source_invalid",
            "image context required": "source_invalid",
            "glTF must embed dependencies": "source_invalid",
            "invalid GLB": "source_invalid",
            "unregistered node version": "node_unsupported",
        }
        code = known.get(str(error), str(error) if str(error) in MULTI_IMAGE_MESSAGES else code)
    return dict(
        ok=False,
        error=code,
        message=str(error) if isinstance(error, ServiceError) else MESSAGES[code],
        diagnostic=dict(code=code, exception_type=type(error).__name__),
    )
