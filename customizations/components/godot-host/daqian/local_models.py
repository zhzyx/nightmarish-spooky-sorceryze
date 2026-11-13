"""Discover local CLI model IDs and invoke the editor's tool-disabled chat bridges."""

import hashlib
import importlib.util
import json
import os
import queue
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[4] / "tools"
BRIDGES = {name: TOOLS / (name + "_cli") / "godot_bridge.js" for name in ("codex", "codebuddy")}
CHATGPT = Path("/Applications/ChatGPT.app/Contents/Resources")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}")


def runtime_configuration():
    if not os.environ.get("GONGGONG_RUNTIME_CONFIG"):
        return None, None
    spec = importlib.util.spec_from_file_location("gonggong_runtime_config", TOOLS / "gonggong_runtime_config.py")
    if spec is None or spec.loader is None:
        raise ValueError("运行配置读取入口不可用")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.read_effective()


def installed(*candidates, executable=False):
    for value in candidates:
        if not value:
            continue
        path = Path(value)
        if path.is_absolute() and path.is_file() and (not executable or os.access(path, os.X_OK)):
            return str(path.resolve())
    return None


def codex_entry(candidates):
    for candidate in candidates:
        value = installed(candidate)
        if not value:
            continue
        path = Path(value)
        if path.suffix.lower() in {".cmd", ".ps1", ".bat"}:
            value = installed(path.parent / "node_modules/@openai/codex/bin/codex.js")
        if value and (value.endswith((".js", ".mjs")) or os.access(value, os.X_OK)):
            return value
    return None


def installations(settings, runtime_context=None):
    # An app launched from Finder may have neither npm nor the desktop Codex on PATH.
    mac = sys.platform == "darwin"
    windows = os.name == "nt"
    desktop = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI/Codex/bin"
    desktop_entries = (
        sorted(desktop.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True) if windows else []
    )
    bundled_node = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    node = installed(
        settings.get("cli_node"),
        shutil.which("node"),
        mac and "/opt/homebrew/bin/node",
        mac and "/usr/local/bin/node",
        mac and CHATGPT / "cua_node/bin/node",
        windows and bundled_node,
        executable=True,
    )
    codex = codex_entry([
        settings.get("codex_entry"),
        shutil.which("codex"),
        mac and "/Applications/Codex.app/Contents/Resources/codex",
        mac and CHATGPT / "codex-cli/CodexCLI.app/Contents/MacOS/codex",
        *desktop_entries,
    ])
    buddy_package = Path("node_modules/@tencent-ai/codebuddy-code/bin/codebuddy")
    npm_bin = Path(os.environ.get("APPDATA", "")) / "npm"
    buddy = installed(
        settings.get("cli_entry"),
        TOOLS / "codebuddy_cli" / buddy_package,
        npm_bin / buddy_package if os.name == "nt" else shutil.which("codebuddy"),
    )
    runtime, snapshot = runtime_configuration() if runtime_context is None else runtime_context
    if snapshot is not None:
        node = installed(runtime.runtime_path(snapshot, "node"), executable=True)
        codex = installed(runtime.runtime_path(snapshot, "codex"), executable=True)
    return node, {"codex": codex, "codebuddy": buddy}


def run_json(args, timeout, runtime_environment=None):
    """One owned process boundary; a terminal JSON line precedes tree cleanup."""
    env = dict(os.environ if runtime_environment is None else runtime_environment)
    if os.name == "nt" and not any(name.lower().endswith("_proxy") for name in env if name.lower() != "no_proxy"):
        for scheme, proxy in urllib.request.getproxies().items():
            if scheme in {"http", "https", "no"}:
                env.setdefault(scheme.upper() + "_PROXY", proxy)
    arguments = [*args, "--host-process-group"]
    job = None
    proc = None
    reader = None
    output = bytearray()
    chunks = queue.Queue(maxsize=130)
    stopped = threading.Event()
    packet = None

    def read_output():
        try:
            while not stopped.is_set():
                chunk = os.read(proc.stdout.fileno(), 65536)
                # The queue is bounded even if the caller is interrupted.
                while not stopped.is_set():
                    try:
                        chunks.put(chunk, timeout=0.05)
                        break
                    except queue.Full:
                        pass
                if not chunk:
                    return
        except (OSError, ValueError):
            stopped.set()

    try:
        if os.name == "nt":
            spec = importlib.util.spec_from_file_location(
                "daqian_process_boundary", TOOLS / "editor_provenance_process.py"
            )
            if spec is None or spec.loader is None:
                raise ValueError("本机进程边界入口不可用")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            job = module.WindowsJob(secrets.token_hex(16))
            proc = job.spawn(
                arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
            )
        else:
            proc = subprocess.Popen(
                arguments,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("本地 CLI 超时，已停止本次进程，请检查连接后重试")
            try:
                chunk = chunks.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                if stopped.is_set():
                    raise ValueError("CLI 回执读取失败")
                continue
            output.extend(chunk)
            if len(output) > 8_000_000:
                raise ValueError("CLI 回执超过大小上限")
            if b"\n" in output:
                packet = json.loads(output)
                break
            if not chunk:
                raise ValueError("CLI 未返回终态回执，请检查桥接安装后重试")
    except (OSError, json.JSONDecodeError):
        raise ValueError("CLI 未返回有效回执，请检查安装和登录状态") from None
    finally:
        stopped.set()
        try:
            if proc is not None:
                # Do not poll/reap the POSIX leader before closing its group:
                # retaining that child PID prevents a reused PID being signaled.
                if job is not None:
                    job.cancel()
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.wait(timeout=5)
        finally:
            if job is not None:
                job.close()
            if proc is not None:
                if proc.stdin:
                    proc.stdin.close()
                if reader is not None:
                    reader.join(timeout=5)
                if proc.stdout:
                    proc.stdout.close()
    if isinstance(packet, dict) and packet:
        error = packet.get("error")
        if error is None:
            return packet
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, str) and re.fullmatch("[A-Z_]{2,40}", code):
            raise ValueError("本地 CLI 验证失败 · " + code)
    raise ValueError("CLI 未返回有效回执，请检查安装和登录状态")


def model_ids(packet, backend):
    rows = packet.get("models") if isinstance(packet, dict) else None
    if not isinstance(rows, list):
        return []
    field = "id"
    return [
        row[field]
        for row in rows[:500]
        if isinstance(row, dict)
        and isinstance(row.get(field), str)
        and MODEL_ID.fullmatch(row[field])
        and (backend != "codex" or row.get("visibility", "list") == "list")
    ]


def codex_config(home):
    try:
        with (home / "config.toml").open("rb") as stream:
            import tomllib

            config = tomllib.load(stream)
    except FileNotFoundError:
        return {}
    except ImportError:
        raise ValueError("读取 Codex 配置需要 Python 3.11 或更高版本") from None
    except (OSError, ValueError):
        raise ValueError("无法读取 Codex 配置，请检查 config.toml") from None
    # The existing bridge deliberately starts with --ignore-user-config.
    if (
        config.get("model_provider", "openai") != "openai"
        or config.get("profile")
        or config.get("openai_base_url")
        or config.get("model_catalog_json")
    ):
        raise ValueError("Codex 使用自定义配置，请在下方按实际供应商接口接入")
    return config


def codex_ids(node, entry, home, runtime_environment=None):
    # Use the same live bridge as the editor. A CLI-owned cache is not proof of
    # this connection and must never suppress an explicit discovery request.
    arguments = [node, BRIDGES["codex"], "models", entry]
    packet = (
        run_json(arguments, 35, runtime_environment) if runtime_environment is not None else run_json(arguments, 35)
    )
    return model_ids(packet, "codex")


def file_revision(path, *, required=False):
    path = Path(path)
    try:
        stat = path.stat()
        if not path.is_file():
            raise OSError()
        return [str(path.resolve()), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    except OSError:
        if required:
            raise ValueError("本地运行文件已失效，请检查安装后重新连接并验证") from None
        return [str(path.absolute()), None]


def connection_source(profile, runtime_context=None, environment=None):
    """Opaque source revision; never read or persist authentication file contents."""
    backend = profile["protocol"].removesuffix("-cli")
    runtime, snapshot = runtime_configuration() if runtime_context is None else runtime_context
    env = (
        (runtime.child_environment(snapshot) if snapshot is not None else os.environ.copy())
        if environment is None
        else environment
    )
    node, entry = profile["node"], profile["entry"]
    if snapshot is not None:
        current_node = installed(runtime.runtime_path(snapshot, "node"), executable=True)
        current_entry = (
            installed(runtime.runtime_path(snapshot, "codex"), executable=True)
            if backend == "codex"
            else installed(entry)
        )
        if node != current_node or entry != current_entry:
            raise ValueError("运行路径已更新，请通过已有本地模型连接/验证入口重新验证")
    if not installed(node, executable=True) or not installed(entry):
        raise ValueError("本地运行文件已失效，请检查安装后重新连接并验证")
    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    codex_home = Path(env.get("CODEX_HOME") or home / ".codex")
    files = [file_revision(value, required=True) for value in (node, entry, BRIDGES[backend])]
    # Metadata detects official file-based login/config replacement without
    # parsing secrets. External vault-only changes still require a new probe.
    auth_paths = (
        [codex_home / "auth.json", codex_home / "config.toml"]
        if backend == "codex"
        else [home / ".codebuddy.json", home / ".codebuddy/settings.json"]
    )
    files.extend(file_revision(value) for value in auth_paths)
    names = {
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PATH",
        "CODEX_HOME",
        "NODE_EXTRA_CA_CERTS",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    }
    relevant = {
        key: value
        for key, value in env.items()
        if key in names
        or key.upper().endswith("_PROXY")
        or key.startswith(("OPENAI_", "CODEX_", "CODEBUDDY_", "ANTHROPIC_"))
    }
    payload = json.dumps([files, relevant], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def current_profile(profile):
    if profile.get("protocol") not in {"codex-cli", "codebuddy-cli"}:
        return True
    try:
        return profile.get("source_revision") == connection_source(profile)
    except (OSError, ValueError):
        return False


def discover_cli(settings):
    runtime, snapshot = runtime_configuration()
    node, entries = installations(settings, (runtime, snapshot)) if snapshot is not None else installations(settings)
    environment = runtime.child_environment(snapshot) if snapshot is not None else None
    for backend, label, field in (("codex", "Codex", "codex_model"), ("codebuddy", "CodeBuddy", "cli_model")):
        entry = entries[backend]
        if not entry or not node:
            yield label, [], "未找到 CLI" if not entry else "缺少 Node.js"
            continue
        configured = settings.get(field, "")
        ids = []
        note = ""
        try:
            if backend == "codex":
                source_environment = environment if environment is not None else os.environ
                user_home = Path(source_environment.get("HOME") or source_environment.get("USERPROFILE") or Path.home())
                home = Path(source_environment.get("CODEX_HOME") or user_home / ".codex")
                config = codex_config(home)
                ids.extend(
                    value
                    for value in (configured, config.get("model"))
                    if isinstance(value, str) and MODEL_ID.fullmatch(value)
                )
                ids.extend(codex_ids(node, entry, home, environment))
            else:
                if MODEL_ID.fullmatch(configured):
                    ids.append(configured)
                arguments = [node, BRIDGES[backend], "models", entry]
                packet = run_json(arguments, 40, environment) if environment is not None else run_json(arguments, 40)
                ids.extend(model_ids(packet, backend))
        except ValueError as error:
            note = str(error)
        profiles = [
            {"name": label, "protocol": backend + "-cli", "model": model, "node": node, "entry": entry}
            for model in dict.fromkeys(ids)
        ]
        try:
            for profile in profiles:
                profile["source_revision"] = connection_source(profile, (runtime, snapshot), environment)
        except (OSError, ValueError) as error:
            profiles = []
            note = str(error)
        yield label, profiles, note or ("" if profiles else "未发现型号，请在 AI Chat 设置中选择模型")


def invoke_cli(profile, text, images, *, timeout=320):
    if images:
        raise ValueError("本地 CLI 文本桥接不支持图像")
    backend = profile["protocol"].removesuffix("-cli")
    node, entry = profile["node"], profile["entry"]
    runtime, snapshot = runtime_configuration()
    environment = None
    if snapshot is not None:
        node = installed(runtime.runtime_path(snapshot, "node"), executable=True)
        if backend == "codex":
            entry = installed(runtime.runtime_path(snapshot, "codex"), executable=True)
        if not node or not entry or node != profile["node"] or entry != profile["entry"]:
            raise ValueError("运行路径已更新，请通过已有本地模型连接/验证入口重新验证")
        environment = runtime.child_environment(snapshot)
    if profile.get("source_revision") != connection_source(profile, (runtime, snapshot), environment):
        raise ValueError("本地连接来源已改变，请重新连接并验证")
    payload = {"messages": [{"role": "user", "content": text}], "available_tools": [], "model": profile["model"]}
    with tempfile.TemporaryDirectory() as directory:
        request = Path(directory) / "request.json"
        request.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        arguments = [node, BRIDGES[backend], "chat", entry, request]
        packet = run_json(arguments, timeout, environment) if environment is not None else run_json(arguments, timeout)
    if not current_profile(profile):
        raise ValueError("本地连接在调用期间已改变，回执不能作为当前连接的证明")
    try:
        choice = packet["choices"][0]
        if choice["finish_reason"] == "stop" and not choice["message"].get("tool_calls"):
            content = choice["message"]["content"]
            if isinstance(content, str) and content.strip():
                return {"text": content, "observed_model": None, "provider_request_id": None}
    except (IndexError, KeyError, TypeError):
        pass
    raise ValueError("CLI 未返回完整文本")
