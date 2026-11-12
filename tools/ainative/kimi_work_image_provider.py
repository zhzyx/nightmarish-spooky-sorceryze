"""Durable Kimi Work image jobs for the Maliang editor.

The configured Kimi Work scripts own SDK authentication and image generation.
This adapter never reads credentials. Local intents are committed before any
reference upload or generation; an unknown result is never automatically retried.
"""

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from codex_provider import (
    MAX_BYTES,
    CodexProvider,
    _creationflags,
    validate_jpeg,
    validate_png,
)
from comfy_provider import DEFAULTS, digest, register
from extensions import NodeRegistry, canonical, require, validate_invocation

VERSION = "1"
GENERATION_VERSION = "v2"
UPLOAD_TIMEOUT = 480
IMAGE_TIMEOUT = 1500
MIN_PIXELS = 655360
MAX_PIXELS = 8294400
MAX_LOG_BYTES = 1024 * 1024
MESSAGES = {
    "image_not_configured": "尚未配置 Kimi Work 图像工具。请在 AI 设置中选择 image_generation_tool.py 和已验证的 pythonw。",
    "image_tool_missing": "Kimi Work 图像工具或其 launcher/watcher 不完整，请检查本机安装。",
    "image_runtime_missing": "Kimi Work 图像运行环境无效。Windows 必须选择已验证的 pythonw.exe，不能使用控制台 Python。",
    "image_tool_invalid": "Kimi Work 图像工具配置无效，请重新检测本机工具。",
    "image_dependency_missing": "Kimi Work 图像依赖缺失或版本过旧；请先使用图像插件的依赖修复入口，不会自动安装。",
    "image_upload_failed": "参考图上传失败；本次生成未提交，不会自动重复上传。",
    "image_launch_failed": "图像任务未能启动；请检查私有诊断，系统不会自动重复提交。",
    "image_generation_failed": "Kimi Work 图像服务未返回成功结果；私有诊断已保留，未自动重发。",
    "image_timeout": "图像任务等待超时；已停止本地监视，远程回执可能不明，不会自动重发。",
    "image_output_invalid": "图像服务未返回可核验的本次新图像，未采用旧图或无效文件。",
    "image_result_unknown": "图像任务回执不明；已保留原意图，不会自动重复生成。",
    "prompt_required": "请填写文字生图或图生图提示词。",
    "invalid_input": "输入图像、提示词或图像尺寸无效；宽高需为 16 的倍数，并符合图像服务范围。",
    "node_unsupported": "Kimi Work 图像 Provider 仅支持文字生图和图生图，不支持 Mesh 节点。",
    "unsupported_multiple_image_constraints": "当前图像服务只支持一张输入或参考图，不能静默忽略其他图像。",
    "unsupported_context_semantics": "当前图像服务支持节点级文字说明和一张参考图。",
    "worker_failed": "图像工作进程失败；私有回执已保留，未自动重复生成。",
}
_WORKERS: list[subprocess.Popen[bytes]] = []


def _resolved_file(value, suffix, code):
    require(isinstance(value, str) and value.strip() and Path(value).is_absolute(), code)
    path = Path(value).expanduser().resolve()
    require(path.is_file() and path.suffix.lower() == suffix, code)
    return path


def _tool_fingerprint(tool_path):
    tool = _resolved_file(tool_path, ".py", "image_tool_missing")
    require(tool.name == "image_generation_tool.py", "image_tool_missing")
    scripts = {
        name: tool.with_name(name)
        for name in ("image_generation_tool.py", "image_generation_launch.py", "image_generation_watch.py")
    }
    require(all(path.is_file() for path in scripts.values()), "image_tool_missing")
    fingerprints = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in scripts.items()}
    return digest(fingerprints)


def check_image_tool(tool_path, pythonw_path):
    """Check local entry points only; never read credentials or request generation."""
    try:
        if not tool_path or not pythonw_path:
            raise ValueError("image_not_configured")
        tool = _resolved_file(tool_path, ".py", "image_tool_missing")
        fingerprint = _tool_fingerprint(tool)
        runtime = _resolved_file(pythonw_path, ".exe" if os.name == "nt" else "", "image_runtime_missing")
        require(os.name != "nt" or runtime.name.lower() == "pythonw.exe", "image_runtime_missing")
        return dict(
            connected=True,
            code="",
            message="Kimi Work 图像工具与无窗口运行时已就绪；检测未上传或生成。凭据、额度与网络以实际任务回执为准。",
            provider="kimi_work_image",
            generation_version=GENERATION_VERSION,
            auth_mode="kimi_work_sdk_credentials",
            tool_path=str(tool),
            pythonw_path=str(runtime),
            tool_fingerprint=fingerprint,
        )
    except (ValueError, OSError) as error:
        code = str(error) if str(error) in MESSAGES else "image_tool_invalid"
        return dict(
            connected=False,
            code=code,
            message=MESSAGES[code],
            provider="kimi_work_image",
            generation_version=GENERATION_VERSION,
            auth_mode="kimi_work_sdk_credentials",
        )


def _public_url(value):
    try:
        url = urllib.parse.urlsplit(value)
        valid = (
            url.scheme == "https"
            and bool(url.hostname)
            and not url.username
            and not url.password
            and not any(ord(character) < 32 for character in value)
        )
        _ = url.port
    except (ValueError, AttributeError):
        valid = False
    require(valid, "image_upload_failed")
    return value


def _saved_path(log, prefix):
    require(len(log) <= MAX_LOG_BYTES, "image_output_invalid")
    matches = [line[len(prefix) :].strip() for line in log.splitlines() if line.startswith(prefix)]
    require(len(matches) == 1 and matches[0], "image_output_invalid")
    return matches[0]


class KimiWorkImageProvider(CodexProvider):
    CONFIG_KEYS = frozenset(("tool_path", "pythonw_path", "storage"))
    DATABASE_NAME = "kimi-work-image-jobs.sqlite"
    MESSAGES = MESSAGES

    def __init__(self, config):
        require(isinstance(config, dict) and set(config) == self.CONFIG_KEYS, "image_tool_invalid")
        require(all(isinstance(value, str) for value in config.values()), "image_tool_invalid")
        self.config = json.loads(canonical(config))
        self.storage = Path(config["storage"]).expanduser().resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.database = self.storage / self.DATABASE_NAME
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.fingerprint = digest([self.config, hashlib.sha256(Path(__file__).read_bytes()).hexdigest()])

    def describe(self):
        return dict(
            id="kimi_work_image",
            version=VERSION,
            model="Kimi Work agent-gw generate_image v2; independent from K3.1 Pro mesh planning",
            model_version=self.fingerprint,
            capabilities=["text_to_image", "image_to_image"],
            context_types=["text", "image"],
            available=True,
        )

    def finish(self, key, state, code=None, result=None):
        outputs = {"result": {k: result["artifacts"][-1][k] for k in ("id", "revision")}} if result else None
        message = self.MESSAGES.get(code, self.MESSAGES["image_result_unknown"]) if code else None
        values = dict(terminal=self.snapshot(key, state, outputs, message))
        if result:
            values["result"] = result
        return self.write(key, **values)["terminal"]

    def plan(self, request, manifest):
        kind = request["node"]
        require(kind in ("text_to_image", "image_to_image"), "node_unsupported")
        parameters = dict(DEFAULTS, **request["parameters"])
        for key, value in (("width", 1024), ("height", 1024)):
            if key not in request["parameters"]:
                parameters[key] = value
        width, height = parameters["width"], parameters["height"]
        require(
            type(width) is int
            and type(height) is int
            and width % 16 == height % 16 == 0
            and 0 < width <= 3840
            and 0 < height <= 3840
            and max(width, height) <= 3 * min(width, height)
            and MIN_PIXELS <= width * height <= MAX_PIXELS,
            "invalid_input",
        )
        refs = list(request["inputs"].values()) + [
            context["artifact"] for context in request["context"] if "artifact" in context
        ]
        require(len(refs) <= 8, "invalid_input")
        for context in request["context"]:
            reference = context["role"] in ("reference", "instruction") and context["strength"] == "reference"
            instruction = "text" in context and context["role"] == "instruction" and context["strength"] == "constraint"
            require(context["scope"] == "node" and (reference or instruction), "unsupported_context_semantics")
        prompt = "\n".join(
            [str(parameters["prompt"])] + [context["text"] for context in request["context"] if "text" in context]
        ).strip()
        require(prompt and len(prompt.encode("utf-8")) <= 32768, "prompt_required" if not prompt else "invalid_input")
        sources = []
        for ref in refs:
            source = next(
                (
                    artifact
                    for artifact in manifest["artifacts"]
                    if artifact["id"] == ref["id"] and artifact["revision"] == ref["revision"]
                ),
                None,
            )
            require(source is not None, "invalid_input")
            payload = source["payload"]
            data = base64.b64decode(payload["content_base64"], validate=True)
            require(
                0 < len(data) <= MAX_BYTES
                and hashlib.sha256(data).hexdigest() == payload["content_sha256"]
                and payload["extension"].lower() in (".png", ".jpg", ".jpeg"),
                "invalid_input",
            )
            if payload["extension"].lower() == ".png":
                validate_png(data)
            else:
                validate_jpeg(data)
            sources.append(source)
        require(kind != "image_to_image" or sources, "invalid_input")
        return dict(
            prompt=prompt,
            context=json.loads(canonical(request["context"])),
            source=sources[0] if sources else None,
            sources=sources,
            parameters=parameters,
        )

    def submit(self, request, manifest, idempotency_key):
        registry = NodeRegistry()
        register(registry)
        validate_invocation(registry, request, manifest, self.describe())
        key = idempotency_key
        require(isinstance(key, str) and re.fullmatch(r"[a-f0-9]{64}", key), "invalid idempotency key")
        record = dict(
            request=request,
            manifest=manifest,
            fingerprint=self.fingerprint,
            created=time.time(),
            heartbeat=time.time(),
            stage="intent",
        )
        with self.db() as db:
            inserted = db.execute("INSERT OR IGNORE INTO jobs VALUES (?,?)", (key, canonical(record))).rowcount
        if not inserted:
            previous = self.read(key)
            require(
                previous["request"] == request
                and previous["manifest"] == manifest
                and previous["fingerprint"] == self.fingerprint,
                "idempotency conflict",
            )
            return self.poll(key)
        try:
            plan = self.plan(request, manifest)
            report = check_image_tool(self.config["tool_path"], self.config["pythonw_path"])
            require(report["connected"], report["code"])
            directory = self.storage / key
            directory.mkdir(exist_ok=False)
            (directory / "config.json").write_text(canonical(self.config), encoding="utf-8")
            (directory / "runtime").mkdir()
            self.write(key, plan=plan, image_report=report, stage="queued")
            with (directory / "worker.log").open("xb") as log:
                worker = subprocess.Popen(
                    [
                        sys.executable,
                        "-X",
                        "utf8",
                        str(Path(__file__).resolve()),
                        "--worker",
                        str(directory / "config.json"),
                        key,
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    env=self._environment(directory),
                    creationflags=_creationflags(),
                    start_new_session=os.name != "nt",
                )
            # Retain owned handles for reaping; never persist or adopt a PID.
            _WORKERS[:] = [process for process in _WORKERS if process.poll() is None]
            _WORKERS.append(worker)
            return self.poll(key)
        except (ValueError, OSError, KeyError, TypeError) as error:
            code = str(error) if str(error) in self.MESSAGES else "worker_failed"
            return self.finish(key, "failed", code)

    def _environment(self, directory):
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        if directory is not None:
            # The plugin launcher creates its job directory beneath this private root.
            env["TEMP"] = env["TMP"] = str(directory / "runtime")
        return env

    def _run_owned(self, key, arguments, log_name, stage, timeout, directory):
        with (directory / log_name).open("xb") as log:
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=self._environment(directory),
                creationflags=_creationflags(),
                start_new_session=os.name != "nt",
            )
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if not self._active(key, stage):
                    process.terminate()
                    return None
                if time.monotonic() > deadline:
                    self.finish(key, "failed", "image_timeout")
                    process.terminate()
                    return None
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            process.wait()
        return process.returncode

    def _reference_urls(self, key, plan, directory):
        urls = []
        for index, source_asset in enumerate(plan["sources"]):
            payload = source_asset["payload"]
            source = directory / ("input-" + str(index) + payload["extension"].lower())
            with source.open("xb") as output:
                output.write(base64.b64decode(payload["content_base64"], validate=True))
            tool = Path(self.config["tool_path"]).resolve()
            log_name = "upload-" + str(index) + ".log"
            code = self._run_owned(
                key,
                [self.config["pythonw_path"], "-u", str(tool), "image-to-url", "--image-path", str(source)],
                log_name,
                "reference_upload",
                UPLOAD_TIMEOUT,
                directory,
            )
            if code is None:
                return None
            log = (directory / log_name).read_text(encoding="utf-8", errors="replace")
            if "Missing dependency:" in log or "agent-gw" in log and "required; found" in log:
                raise ValueError("image_dependency_missing")
            require(code == 0, "image_upload_failed")
            lines = [line.strip() for line in log.splitlines() if line.strip()]
            require(len(lines) == 1, "image_upload_failed")
            url = _public_url(lines[0])
            self.write(key, reference_url_sha256=digest(url), stage="reference_uploaded")
            urls.append(url)
        return urls

    def _cli(self, key, plan, directory):
        record = self.read(key)
        # The parent already validated the windowless interpreter. The worker
        # verifies the immutable scripts, without executing another discovery.
        require(
            _tool_fingerprint(self.config["tool_path"]) == record["image_report"]["tool_fingerprint"],
            "image_tool_invalid",
        )
        if not self._active(key, "prepare"):
            return None
        reference_urls = self._reference_urls(key, plan, directory)
        if reference_urls is None:
            return None
        root = Path(self.config["tool_path"]).resolve().parent
        requested = directory / "generated.png"
        arguments = [
            self.config["pythonw_path"],
            "-u",
            str(root / "image_generation_launch.py"),
            "generate",
            "--description",
            plan["prompt"],
            "--size",
            str(plan["parameters"]["width"]) + "x" + str(plan["parameters"]["height"]),
            "--background",
            "opaque",
            "--output",
            str(requested),
        ]
        for reference_url in reference_urls:
            arguments.extend(["--reference-image", reference_url])
        started_ns = time.time_ns()
        code = self._run_owned(key, arguments, "launch.log", "image_launch", 45, directory)
        if code is None:
            return None
        launch_log = (directory / "launch.log").read_text(encoding="utf-8", errors="replace")
        require(code == 0, "image_launch_failed")
        log_path = Path(_saved_path(launch_log, "Job log: ")).resolve()
        pid_path = Path(_saved_path(launch_log, "Job PID file: ")).resolve()
        require(log_path.is_file() and pid_path.is_file(), "image_launch_failed")
        require(log_path.is_relative_to(directory) and pid_path.is_relative_to(directory), "image_launch_failed")
        code = self._run_owned(
            key,
            [
                self.config["pythonw_path"],
                "-u",
                str(root / "image_generation_watch.py"),
                "--log-file",
                str(log_path),
                "--pid-file",
                str(pid_path),
                "--interval-seconds",
                "5",
            ],
            "watch.log",
            "image_generation",
            IMAGE_TIMEOUT,
            directory,
        )
        if code is None:
            return None
        watch_log = (directory / "watch.log").read_text(encoding="utf-8", errors="replace")
        if "Missing dependency:" in watch_log or "agent-gw" in watch_log and "required; found" in watch_log:
            raise ValueError("image_dependency_missing")
        if code != 0:
            generation_log = log_path.read_text(encoding="utf-8", errors="replace")
            known_failure = any(
                marker in generation_log
                for marker in ("Error generating image:", "Error: ", "failed to download generated image from")
            )
            raise ValueError("image_generation_failed" if known_failure else "image_result_unknown")
        reported = Path(_saved_path(watch_log, "done: "))
        require(reported.is_absolute() and not reported.is_symlink(), "image_output_invalid")
        output = reported.resolve()
        require(
            output.parent == directory and output.suffix.lower() in (".png", ".jpg", ".jpeg"), "image_output_invalid"
        )
        stat = output.stat()
        require(
            output.is_file()
            and stat.st_nlink == 1
            and 0 < stat.st_size <= MAX_BYTES
            and stat.st_mtime_ns >= started_ns
            and getattr(stat, "st_birthtime_ns", stat.st_ctime_ns) >= started_ns,
            "image_output_invalid",
        )
        data = output.read_bytes()
        if data.startswith(b"\x89PNG"):
            dimensions = validate_png(data)
            extension = ".png"
        else:
            dimensions = validate_jpeg(data)
            extension = ".jpg"
        sha = hashlib.sha256(data).hexdigest()
        source_shas = [source["payload"]["content_sha256"] for source in plan["sources"]]
        source_sha = source_shas[0] if source_shas else None
        require(sha not in source_shas, "image_output_invalid")
        require(
            dimensions == {"width": plan["parameters"]["width"], "height": plan["parameters"]["height"]},
            "image_output_invalid",
        )
        reference_url_shas = [digest(url) for url in reference_urls]
        receipt = dict(
            output_path=str(output),
            output_sha256=sha,
            source_sha256=source_sha,
            source_sha256_ordered=source_shas,
            dimensions=dimensions,
            bytes=len(data),
            reference_url_sha256=reference_url_shas[0] if reference_url_shas else None,
            reference_url_sha256_ordered=reference_url_shas,
            tool_fingerprint=record["image_report"]["tool_fingerprint"],
            generation_version=GENERATION_VERSION,
        )
        self.write(key, image_receipt=receipt)
        provenance = dict(
            provider="kimi_work_image",
            service="Kimi Work agent-gw generate_image",
            generation_version=GENERATION_VERSION,
            distinct_from_mesh_model=True,
            mesh_model_not_used_for_image="k3.1-pro",
            auth_mode="kimi_work_sdk_credentials",
            origin="new_file_from_completed_plugin_worker",
            source_sha256=source_sha,
            source_sha256_ordered=source_shas,
            output_sha256=sha,
            dimensions=dimensions,
            requested_dimensions={k: plan["parameters"][k] for k in ("width", "height")},
            receipt_sha256=digest(receipt),
            tool_fingerprint=record["image_report"]["tool_fingerprint"],
            reference_url_sha256=receipt["reference_url_sha256"],
            reference_url_sha256_ordered=reference_url_shas,
            reference_input_mode="ordered_native_multi_reference",
            effective_prompt_sha256=digest(plan["prompt"]),
            context_semantics=[{k: c[k] for k in ("role", "scope", "strength")} for c in plan["context"]],
            constraint_interpretation="natural_language_visual_requirements_not_pixel_guarantees",
            unsupported_image_controls=["seed", "steps", "denoise"],
            image_controls_not_applied={k: plan["parameters"][k] for k in ("seed", "steps", "denoise")},
            background="opaque",
            image_cost=None,
        )
        return dict(
            id="kimi-work-image-" + key,
            revision=sha,
            type="image",
            payload=dict(
                content_base64=base64.b64encode(data).decode(),
                content_sha256=sha,
                extension=extension,
                bytes=len(data),
                provenance=provenance,
            ),
        )

    def work(self, key):
        record = self.read(key)
        if "terminal" in record:
            return
        require(record["fingerprint"] == self.fingerprint, "image_result_unknown")
        image = self._cli(key, record["plan"], self.storage / key)
        if image is None or not self._active(key):
            return
        self.write(key, image_stage=image, stages=[dict(stage="kimi_work_image", artifact_sha256=image["revision"])])
        self.finish(key, "succeeded", result=dict(schema_version=1, artifacts=[image]))


if __name__ == "__main__":
    require(len(sys.argv) == 4 and sys.argv[1] == "--worker", "worker invocation required")
    provider = KimiWorkImageProvider(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    try:
        provider.work(sys.argv[3])
    except Exception as error:
        import traceback

        traceback.print_exc()
        code = str(error) if str(error) in MESSAGES else "image_result_unknown"
        provider.finish(sys.argv[3], "failed", code)
