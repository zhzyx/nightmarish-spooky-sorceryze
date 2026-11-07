"""Local generation settings and read-only ComfyUI capability discovery.

Discovery never uploads inputs or submits prompts. Remote checkpoint hashes are
unknown unless a separately configured legacy deployment provides real hashes.
GUI runs therefore use a persisted run-scoped provider identity, preventing
cross-run reuse under an unverified model identity.
"""

import ipaddress
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path

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
    "service_not_configured": "尚未配置真实生成服务。请打开“本机设置”，选择 ComfyUI，检测连接并保存模型；离线复制仍可使用。",
    "service_config_invalid": "生成服务设置无效。请在“本机设置”重新填写服务类型、地址及模型并保存。",
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
}


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
    }:
        raise ServiceError("service_config_invalid")
    result = dict(schema_version=1, mode="offline", endpoint="http://127.0.0.1:8188", image_model="", mesh_model="")
    result.update(value)
    if (
        result["schema_version"] != 1
        or isinstance(result["schema_version"], bool)
        or result["mode"] not in ("offline", "comfy", "codex")
    ):
        raise ServiceError("service_config_invalid")
    if not all(isinstance(result[key], str) for key in ("endpoint", "image_model", "mesh_model")):
        raise ServiceError("service_config_invalid")
    for key in ("image_model", "mesh_model"):
        name = result[key]
        if name and (
            name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/") or any(ord(c) < 32 for c in name)
        ):
            raise ServiceError("service_config_invalid")
    if result["mode"] == "codex":
        result.setdefault("cli_path", "codex")
        if not isinstance(result["cli_path"], str) or not result["cli_path"].strip():
            raise ServiceError("cli_unavailable")
    elif "cli_path" in result:
        raise ServiceError("service_config_invalid")
    if result["mode"] in ("comfy", "codex"):
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
        if result["mode"] == "codex" and (
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
    try:
        config = settings(value)
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
            mode="comfy",
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
            mode="comfy",
            connected=False,
            models={"image": [], "mesh": []},
            capabilities={kind: dict(ready=False, code=error.code, message=str(error)) for kind in KINDS},
            backend_revision="",
            message=str(error),
            code=error.code,
        ), {}


def check_service(value):
    return _probe_service(value)[0]


def _probe_codex(config):
    from codex_provider import check_cli

    cli = check_cli(config["cli_path"])
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
        connected=image_ready,
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
        else image["message"],
    )
    return report, info


def check_inputs(model):
    for node in model["nodes"]:
        kind = node.get("type", "copy")
        if kind not in (*KINDS, "copy"):
            raise ServiceError("node_unsupported")
        incoming = [edge for edge in model["edges"] if edge["to"] == node["id"]]
        source = node.get("source", "")
        if kind.startswith("image_") and not incoming and not source and not node.get("source_snapshot"):
            raise ServiceError("source_missing")
        for field in ("source", "image_context"):
            if node.get(field) and not Path(node[field]).is_file():
                raise ServiceError("source_missing")
        if source and kind.startswith("image_") and Path(source).suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ServiceError("source_invalid")
        if kind in KINDS and kind != "image_to_mesh":
            prompt = str(node.get("parameters", {}).get("prompt", "")) + str(node.get("text", ""))
            if not prompt.strip():
                raise ServiceError("prompt_missing")


def prepare_provider(config, model, database, run_id):
    from comfy_provider import ComfyProvider, register
    from editor_demo import factory

    registry, providers = factory()
    generated = [node for node in model["nodes"] if node.get("type", "copy") in KINDS]
    if not generated:
        return registry, providers, {"mode": "offline"}
    if config["mode"] == "codex":
        from codex_provider import CodexProvider

        report, info = _probe_codex(config)
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
        register(registry)
        providers["codex"] = CodexProvider(provider_config)
        for node in generated:
            node["provider"] = "codex"
        return registry, providers, dict(mode="codex", provider=provider_config)
    if config["mode"] != "comfy":
        raise ServiceError("service_not_configured")
    report, info = _probe_service(config)
    if not report["connected"]:
        raise ServiceError(report.get("code", "service_unreachable"))
    for node in generated:
        kind = node["type"]
        prompt = str(node.get("parameters", {}).get("prompt", "")) + str(node.get("text", ""))
        uses_image_edit = kind != "image_to_mesh" or bool(prompt.strip())
        has_reference = bool(node.get("image_context") or node.get("image_context_snapshot"))
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
    register(registry)
    providers["comfy"] = ComfyProvider(provider_config)
    return registry, providers, dict(mode="comfy", provider=provider_config)


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
    from comfy_provider import ComfyProvider, register
    from editor_demo import factory

    registry, providers = factory()
    if snapshot["mode"] == "comfy":
        register(registry)
        providers["comfy"] = ComfyProvider(snapshot["provider"])
    elif snapshot["mode"] == "codex":
        from codex_provider import CodexProvider

        register(registry)
        providers["codex"] = CodexProvider(snapshot["provider"])
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
        code = known.get(str(error), code)
    return dict(
        ok=False,
        error=code,
        message=str(error) if isinstance(error, ServiceError) else MESSAGES[code],
        diagnostic=dict(code=code, exception_type=type(error).__name__),
    )
