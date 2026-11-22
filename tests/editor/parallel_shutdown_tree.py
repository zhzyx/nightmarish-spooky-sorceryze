"""Process-group observations for the macOS native editor shutdown fixture."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def run_editor(command, env, project, *, text=True):
    with subprocess.Popen(["/bin/sleep", "300"], start_new_session=True) as control:
        try:
            env["MAC_TREE_PROJECT"] = str(project)
            env["MAC_TREE_HELPER"] = str(Path(__file__).resolve())
            env["MAC_TREE_PYTHON"] = sys.executable
            result = subprocess.run(command, env=env, capture_output=True, text=text, timeout=240)
            marker = project / "process-tree-ready"
            assert marker.is_file(), (result.returncode, result.stdout[-3000:], result.stderr[-3000:])
            record = json.loads(marker.read_text())
            survivors = []
            for pid in record["pids"]:
                try:
                    os.kill(pid, 0)
                    survivors.append(pid)
                except ProcessLookupError:
                    pass
            record.update(survivors=survivors, control_pid=control.pid, control_alive=control.poll() is None)
            return result, record
        finally:
            control.terminate()


if __name__ == "__main__":
    # Called only by the private runner. The finite lifetime also bounds a
    # regression run against an editor that leaves descendants running.
    project = Path(os.environ["MAC_TREE_PROJECT"])
    with subprocess.Popen(["/bin/sleep", "20"]) as grandchild:
        pids = list(dict.fromkeys([os.getpgrp(), os.getppid(), os.getpid(), grandchild.pid]))
        groups = [os.getpgid(pid) for pid in pids]
        assert groups == [pids[0]] * len(pids)
        record: dict[str, object] = {"pids": pids, "groups": groups}
        if "MAC_TREE_OUTPUT" in os.environ:
            assert "Issue" in sys.stdin.read()
            report = json.loads(Path(os.environ["MAC_TREE_OUTPUT"]).read_text())
            worker = next(w for w in report["workers"] if w.get("pid") == os.getpid())
            ref = worker["registration"]
            data = Path(ref["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == ref["sha256"]
            registration = json.loads(data)
            assert registration["execution_id"] == worker["execution_id"] and worker["state"] == "running"
            record["registration"] = {
                "id": worker["execution_id"],
                "pid": worker["pid"],
                "sha256": ref["sha256"],
                "issue": registration["issue_number"],
            }
        staging = project / "process-tree-starting"
        staging.write_text(json.dumps(record))
        staging.rename(project / "process-tree-ready")
