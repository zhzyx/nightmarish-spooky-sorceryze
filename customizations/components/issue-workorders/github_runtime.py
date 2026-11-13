"""GitHub CLI discovery and transport for the installed Python host adapters.

The installation root comes from this file, never from a selected data project.
Discovery is uncached so installation/repair is visible to an already running host.
No import, discovery or request changes the caller's environment or account.
"""

import math
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

INSTALLATION = Path(__file__).resolve().parents[3]
WINDOWS = os.name == "nt"
DEFAULT_TIMEOUT = 120
PAGINATION_TIMEOUT = 600
BRIDGE_MAX_BUFFER = 64 * 1024 * 1024


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


def command_on_path(name, env):
    search_path = env.get("PATH", "")
    if not WINDOWS:
        return shutil.which(name, path=search_path)
    # Windows shutil.which may prepend cwd and reads ambient PATHEXT. Only
    # directories/extensions explicitly belonging to this child environment count.
    extensions = [ext for ext in env.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if ext]
    names = [name] if any(name.lower().endswith(ext.lower()) for ext in extensions) else []
    names += [name + ext.lower() for ext in extensions]
    for folder in search_path.split(os.pathsep) if search_path else []:
        for candidate_name in names:
            candidate = Path(folder) / candidate_name
            if executable(candidate):
                return str(candidate)
    return None


def resolve_gh(env=None):
    """Resolve explicit selection, installed project runtime, PATH, then fixed locations.

    GONGGONG_GH denotes a file or an exact command name on the supplied PATH.
    Relative file paths use the caller's working directory.
    An explicitly present but invalid/empty selection fails closed; it never selects
    another CLI, credentials directory, account or target project's executable.
    """
    env = os.environ if env is None else env
    if "GONGGONG_GH" in env:
        configured = env["GONGGONG_GH"]
        if configured and not Path(configured).is_absolute() and not any(c in configured for c in ("/", "\\")):
            configured = command_on_path(configured, env)
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
    found = command_on_path("gh", env)
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


def read_only_pagination(args):
    """Recognize the supported REST GET shape, without rewriting gh arguments.

    Unknown flags, payloads and GraphQL keep the ordinary budget. gh continues to
    own pagination, Link/host/auth handling, jq and array/object page semantics.
    """
    if not args or args[0] != "api":
        return False
    flags = {"--paginate", "--slurp", "--include", "-i", "--silent", "--verbose"}
    values = {"--jq", "-q", "--template", "-t", "--hostname", "--header", "-H", "--preview", "-p", "--cache"}
    endpoint, methods, paginated = [], [], False
    iterator = iter(args[1:])
    for arg in iterator:
        if not isinstance(arg, str):
            return False
        key, separator, value = arg.partition("=")
        if key in values or key in {"--method", "-X"}:
            value = value if separator else next(iterator, None)
            if not isinstance(value, str) or not value:
                return False
            if key in {"--method", "-X"}:
                methods.append(value)
        elif arg in flags:
            paginated |= arg == "--paginate"
        elif arg.startswith("-"):
            return False
        else:
            endpoint.append(arg)
    if not paginated or len(endpoint) != 1 or any(method != "GET" for method in methods):
        return False
    try:
        path = urlsplit(endpoint[0]).path.rstrip("/")
    except ValueError:
        return False
    return bool(path) and path.rsplit("/", 1)[-1] != "graphql"


def request_timeout(args, timeout=None, input_value=None):
    # An explicit timeout is always the entire operation's deadline, never per page.
    if timeout is None:
        return PAGINATION_TIMEOUT if input_value is None and read_only_pagination(args) else DEFAULT_TIMEOUT
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise GitHubCommandError(reason="GITHUB_RUNTIME: invalid request timeout")
    return timeout


def run_gh(*args, env=None, input_value=None, cwd=None, timeout=None):
    timeout = request_timeout(args, timeout, input_value)
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
