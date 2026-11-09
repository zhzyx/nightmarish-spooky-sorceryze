"""Return only audited app-server override names. Never open the Codex credential store."""

import json
import os
import re
from pathlib import Path

import tomllib


def profile(home):
    allowed = {
        "computer_use",
        "desktop",
        "marketplaces",
        "mcp_servers",
        "model",
        "model_reasoning_effort",
        "notify",
        "plugins",
        "projects",
        "service_tier",
        "windows",
    }
    path = home / "config.toml"
    if path.is_symlink() or (path.exists() and path.stat().st_size > 512 * 1024):
        return None
    data = tomllib.loads(path.read_text(encoding="utf8")) if path.exists() else {}
    if set(data) - allowed or (home / "hooks.json").exists():
        return None
    names = list(data.get("mcp_servers", {}))
    if not all(re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name) for name in names):
        return None
    return names


if __name__ == "__main__":
    try:
        result = profile(Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    except (OSError, ValueError, TypeError):
        result = None
    print(json.dumps(result))
