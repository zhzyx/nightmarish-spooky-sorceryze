"""Private JSON/stdin bridge for installed JavaScript hosts; never load project code."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github_runtime import GitHubCommandError, resolve_gh, run_gh


def main():
    try:
        request = json.load(sys.stdin)
        if request["operation"] == "resolve":
            value = resolve_gh()
        elif request["operation"] == "request":
            value = run_gh(*request["args"], input_value=request.get("input"), timeout=request["timeout_ms"] / 1000)
        else:
            raise ValueError("Unsupported operation")
        result = {"ok": True, "value": value}
    except GitHubCommandError as error:
        result = {"ok": False, "error": str(error), "http_status": error.http_status}
    except Exception:
        result = {"ok": False, "error": "GITHUB_RUNTIME: invalid host bridge request"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
