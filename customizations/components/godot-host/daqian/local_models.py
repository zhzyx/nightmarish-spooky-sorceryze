"""Discover local CLI model IDs and invoke the editor's tool-disabled chat bridges."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[4] / "tools"
BRIDGES = {name: TOOLS / (name + "_cli") / "godot_bridge.js" for name in ("codex", "codebuddy")}
CHATGPT = Path("/Applications/ChatGPT.app/Contents/Resources")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}")


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


def installations(settings):
    # An app launched from Finder may have neither npm nor the desktop Codex on PATH.
    mac = sys.platform == "darwin"
    node = installed(settings.get("cli_node"), shutil.which("node"), mac and "/opt/homebrew/bin/node",
                     mac and "/usr/local/bin/node", mac and CHATGPT / "cua_node/bin/node", executable=True)
    codex = codex_entry([settings.get("codex_entry"), shutil.which("codex"),
                      mac and "/Applications/Codex.app/Contents/Resources/codex",
                      mac and CHATGPT / "codex-cli/CodexCLI.app/Contents/MacOS/codex"])
    buddy_package = Path("node_modules/@tencent-ai/codebuddy-code/bin/codebuddy")
    npm_bin = Path(os.environ.get("APPDATA", "")) / "npm"
    buddy = installed(settings.get("cli_entry"), TOOLS / "codebuddy_cli" / buddy_package,
                      npm_bin / buddy_package if os.name == "nt" else shutil.which("codebuddy"))
    return node, {"codex": codex, "codebuddy": buddy}


def run_json(args, timeout):
    try:
        proc = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
        if proc.returncode == 0:
            packet = json.loads(proc.stdout)
            if isinstance(packet, dict):
                return packet
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    raise ValueError("CLI 未返回有效回执，请检查安装和登录状态")


def model_ids(packet, backend):
    rows = packet.get("models") if isinstance(packet, dict) else None
    if not isinstance(rows, list):
        return []
    field = "slug" if backend == "codex" else "id"
    return [row[field] for row in rows[:500] if isinstance(row, dict)
            and isinstance(row.get(field), str) and MODEL_ID.fullmatch(row[field])
            and (backend != "codex" or row.get("visibility", "list") == "list")]


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
    if (config.get("model_provider", "openai") != "openai" or config.get("profile")
            or config.get("openai_base_url") or config.get("model_catalog_json")):
        raise ValueError("Codex 使用自定义配置，请在下方按实际供应商接口接入")
    return config


def codex_ids(node, entry, home):
    cache = home / "models_cache.json"
    try:
        with cache.open("rb") as stream:
            raw = stream.read(8_000_001)
        if len(raw) <= 8_000_000:
            cached = model_ids(json.loads(raw), "codex")
            if cached:
                return cached
    except (OSError, ValueError):
        pass
    command = [node, entry] if entry.endswith((".js", ".mjs")) else [entry]
    return model_ids(run_json([*command, "debug", "models"], 25), "codex")


def discover_cli(settings):
    node, entries = installations(settings)
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
                home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
                config = codex_config(home)
                ids.extend(value for value in (configured, config.get("model"))
                           if isinstance(value, str) and MODEL_ID.fullmatch(value))
                ids.extend(codex_ids(node, entry, home))
            else:
                if MODEL_ID.fullmatch(configured):
                    ids.append(configured)
                packet = run_json([node, BRIDGES[backend], "models", entry], 40)
                ids.extend(model_ids(packet, backend))
        except ValueError as error:
            note = str(error)
        profiles = [{"name": label, "protocol": backend + "-cli", "model": model, "node": node, "entry": entry}
                    for model in dict.fromkeys(ids)]
        yield label, profiles, note or ("" if profiles else "未发现型号，请在 AI Chat 设置中选择模型")


def invoke_cli(profile, text, images):
    if images:
        raise ValueError("本地 CLI 文本桥接不支持图像")
    backend = profile["protocol"].removesuffix("-cli")
    payload = {"messages": [{"role": "user", "content": text}], "available_tools": [], "model": profile["model"]}
    with tempfile.TemporaryDirectory() as directory:
        request = Path(directory) / "request.json"
        request.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        packet = run_json([profile["node"], BRIDGES[backend], "chat", profile["entry"], request], 320)
    try:
        choice = packet["choices"][0]
        if choice["finish_reason"] == "stop" and not choice["message"].get("tool_calls"):
            content = choice["message"]["content"]
            if isinstance(content, str) and content.strip():
                return {"text": content, "observed_model": None, "provider_request_id": None}
    except (IndexError, KeyError, TypeError):
        pass
    raise ValueError("CLI 未返回完整文本")
