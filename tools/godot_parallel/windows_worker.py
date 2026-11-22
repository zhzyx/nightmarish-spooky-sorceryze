"""Own one editor worker Job until its process tree and I/O close.

stdout carries control messages to our parent runner. The workload inherits only
stdin and the transcript pipe. The runner's enclosing Job also covers this guard.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor_provenance_process import WindowsJob


def notify(**fields):
    print(json.dumps(fields), flush=True)


def main(execution, marker, cancel, *command):
    closing, canceling = Path(marker), Path(cancel)
    with WindowsJob(execution.replace("-", "")) as job:
        # Python startup is asynchronous with the native dock close.
        if closing.exists() or canceling.exists():
            return 143
        child = job.spawn(command, stdin=sys.stdin, stdout=sys.stderr, stderr=sys.stderr, hide_window=True)
        notify(execution=execution, pid=child.pid)
        while child.poll() is None and not closing.exists() and not canceling.exists():
            time.sleep(0.04)
        if canceling.exists() or closing.exists():
            action = "cancel" if canceling.exists() else "editor_close"
            job.cancel()
            code = child.wait(timeout=5)
            notify(execution=execution, pid=child.pid, exit_code=code, active_processes=0, action=action)
            return 143
        # The parent may leave descendants with inherited transcript handles.
        job.quiesce()
        return child.returncode


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
