"""Compare committed dataset checks on identical inputs; writes measured evidence only."""

import json
import runpy
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
relative = "customizations/platforms/data-collection/git-files/storage/diting_files.py"
old = {"__name__": "baseline", "__file__": str(root / relative)}
exec(compile(subprocess.check_output(["git", "-C", str(root), "show", "HEAD:" + relative]), relative, "exec"), old)
new = runpy.run_path(str(root / relative))
results: dict[str, object] = {}
for label, fn in [("baseline", old["git_check"]), ("optimized", new["git_check"])]:
    start = time.perf_counter()
    with patch("subprocess.run", wraps=subprocess.run) as calls:
        result = fn(root, True)
    results[label] = {"seconds": time.perf_counter() - start, "git_processes": calls.call_count, "result": result}
    print(json.dumps({label: results[label]}), flush=True)
results["scope"] = "One warm/cold-uncontrolled Windows run, identical committed datasets; not full gate or CI timing"
results["token_usage"] = None
results["cost"] = None
results["head"] = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
(root / "data-collection/verification-efficiency-benchmark-20261105.json").write_text(
    json.dumps(results, indent=2) + "\n", encoding="utf-8"
)
