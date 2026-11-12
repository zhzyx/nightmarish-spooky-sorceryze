"""GitHub CLI discovery and transport for the installed Python host adapters.

The installation root comes from this file, never from a selected data project.
Discovery is uncached so installation/repair is visible to an already running host.
No import, discovery or request changes the caller's environment or account.
"""

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

INSTALLATION = Path(__file__).resolve().parents[3]
WINDOWS = os.name == "nt"


class GitHubCommandError(ValueError):
    def __init__(self, status=None, reason=None):
        self.http_status = status
        super().__init__(
            reason
            or (
                "GITHUB_HTTP_" + str(status) + ": check repository access and API permissions"
                if status
                else "GITHUB_COMMAND: check local gh login and repository access"
            )
        )


def executable(path):
    return path.is_file() and os.access(path, os.X_OK)


def fixed_locations(env):
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    candidates = []
    if not WINDOWS:
        if home is not None:
            candidates.append(home / ".local/bin/gh")
        candidates += [Path("/opt/homebrew/bin/gh"), Path("/usr/local/bin/gh")]
    else:
        candidates.append(Path(env.get("ProgramFiles", "C:/Program Files")) / "GitHub CLI/gh.exe")
        if home is not None:
            candidates += sorted((home / "Documents/Codex/tools/github-cli").glob("*/bin/gh.exe"), reverse=True)
    return candidates


def resolve_gh(env=None):
    """Resolve explicit selection, installed project runtime, PATH, then fixed locations.

    GONGGONG_GH denotes a file (relative paths use the caller's working directory).
    An explicitly present but invalid/empty selection fails closed; it never selects
    another CLI, credentials directory, account or target project's executable.
    """
    env = os.environ if env is None else env
    if "GONGGONG_GH" in env:
        configured = env["GONGGONG_GH"]
        if not configured or not Path(configured).is_file():
            raise GitHubCommandError(reason="GITHUB_RUNTIME: configured GONGGONG_GH executable is missing")
        if not executable(Path(configured)):
            raise GitHubCommandError(reason="GITHUB_RUNTIME: configured GONGGONG_GH file is not executable")
        return str(Path(configured).absolute())
    for name in ("gh.exe", "gh") if WINDOWS else ("gh", "gh.exe"):
        local = INSTALLATION / "project/runtime/gh/bin" / name
        if executable(local):
            return str(local)
    # A missing PATH is empty, not the current process's/default search path.
    found = shutil.which("gh", path=env.get("PATH", ""))
    if found:
        return str(Path(found).absolute())
    for candidate in fixed_locations(env):
        if executable(candidate):
            return str(candidate.absolute())
    raise GitHubCommandError(
        reason="GITHUB_RUNTIME: gh executable missing; set GONGGONG_GH to the authenticated host CLI"
    )


def credential_helper(env=None):
    # Git executes ! helpers with its POSIX shell, including Git for Windows.
    # Embed the resolved file as one shell argument; no expansion of path contents.
    path = resolve_gh(env)
    if WINDOWS:
        path = path.replace("\\", "/")
    return "!" + shlex.quote(path) + " auth git-credential"


def run_gh(*args, env=None, input_value=None, cwd=None, timeout=120):
    selected_env = dict(os.environ if env is None else env)
    selected = resolve_gh(selected_env)
    try:
        result = subprocess.run(
            [selected, *args],
            input=input_value,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=selected_env,
        )
    except OSError:
        raise GitHubCommandError(
            reason="GITHUB_RUNTIME: selected gh could not be executed; check installation and permissions"
        ) from None
    except subprocess.TimeoutExpired:
        raise GitHubCommandError(
            reason=f"GITHUB_TIMEOUT: request exceeded {timeout} seconds; read remote state before retrying a write"
        ) from None
    if result.returncode:
        stderr = result.stderr or ""
        match = re.search(r"\bHTTP (\d{3})\b", stderr)
        dropped = re.search(r"\bEOF\s*$", stderr, re.I) or any(
            text in stderr.lower()
            for text in (
                "error connecting",
                "connection was reset",
                "could not resolve",
                "network is unreachable",
                "connection refused",
                "i/o timeout",
                "tls handshake timeout",
            )
        )
        if not match and dropped:
            raise GitHubCommandError(
                reason="GITHUB_NETWORK: connection unavailable; check host network permissions and connectivity; remote state is unknown"
            )
        raise GitHubCommandError(int(match[1]) if match else None)
    return result.stdout.strip()
