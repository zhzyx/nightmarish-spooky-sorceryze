"""Private JSON/stdin bridge for installed JavaScript hosts; never load project code."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github_runtime import BRIDGE_MAX_BUFFER, PAGINATION_TIMEOUT, GitHubCommandError, resolve_gh, run_gh


def main():
    try:
        request = json.load(sys.stdin)
        if request["operation"] == "resolve":
            value = resolve_gh()
        elif request["operation"] == "request":
            milliseconds = request.get("timeout_ms")
            timeout = None if milliseconds is None else milliseconds / 1000
            value = run_gh(*request["args"], input_value=request.get("input"), timeout=timeout)
        else:
            raise ValueError("Unsupported operation")
        result = {"ok": True, "value": value}
        if request["operation"] == "resolve":
            result["limits"] = {"max_timeout_ms": PAGINATION_TIMEOUT * 1000, "max_buffer": BRIDGE_MAX_BUFFER}
    except GitHubCommandError as error:
        result = {"ok": False, "error": str(error), "http_status": error.http_status}
    except Exception:
        result = {"ok": False, "error": "GITHUB_RUNTIME: invalid host bridge request"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
