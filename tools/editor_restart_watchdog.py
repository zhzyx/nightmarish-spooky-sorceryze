"""Hand the editor session over to a rebuilt executable, with rollback.

Godot's own restart-on-exit cannot supervise its successor: once the old process
is gone, nobody notices a new binary that starts but cannot build a working AI
dock. This watchdog is launched by that same restart path instead of the new
editor, so one process outlives the switch and can put the old editor back.

It never kills an editor. A new editor that is merely slow is reported as
unconfirmed and left alone, because launching the old binary as well would give
the user two editors on one project.
"""

import argparse
import base64
import binascii
import json
import os
import subprocess
import time
from pathlib import Path

ACK_POLL_SECONDS = 0.2
ACK_STABILITY_SECONDS = 5.0


def write_report(path, **data):
    """Publish the outcome for whichever editor ends up reading it."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def process_is_running(pid):
    """Report whether a process is alive, without ever signaling it."""
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:  # Alive, but owned by somebody else.
            return True
        return True
    # On Windows os.kill() terminates the target even for signal 0, so the
    # process must be probed through a query-only handle instead.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION.
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True  # Assume the owner lives rather than racing its exit.
        return code.value == 259  # STILL_ACTIVE.
    finally:
        kernel32.CloseHandle(handle)


def wait_for_exit(pid, timeout):
    """Wait for the outgoing editor, so only one process owns the project."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_is_running(pid):
            return True
        time.sleep(ACK_POLL_SECONDS)
    return not process_is_running(pid)


def acknowledged(ack, token, binary):
    """Accept only an acknowledgement written by this handoff's new editor."""
    try:
        value = json.loads(ack.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    if not isinstance(value, dict) or value.get("token") != token or value.get("dock_ready") is not True:
        return False
    try:
        return Path(value.get("executable", "")).resolve() == binary
    except OSError:
        return False


def launch(executable, arguments):
    # Detached from this watchdog so closing it never takes the editor down.
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen([str(executable), *arguments], close_fds=True, creationflags=flags)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--ack", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--ack-timeout", type=float, default=240.0)
    parser.add_argument("--exit-timeout", type=float, default=180.0)
    # Editor arguments look like options themselves, so they travel as one value
    # rather than as repeated values an option parser would misread. They are
    # base64-encoded JSON because Windows command-line quoting silently strips
    # the inner quotes of a bare JSON array, which would corrupt the handoff.
    parser.add_argument("--editor-args-b64", default="")
    args = parser.parse_args(argv)
    report = args.report.resolve()
    if not report.parent.is_dir():
        parser.error("The report directory must already exist")
    try:
        decoded = (
            base64.b64decode(args.editor_args_b64, validate=True).decode("utf-8") if args.editor_args_b64 else "[]"
        )
        editor_arguments = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        parser.error(f"Invalid editor arguments: {error}")
    if not isinstance(editor_arguments, list) or not all(isinstance(value, str) for value in editor_arguments):
        parser.error("Editor arguments must be a JSON array of strings")
    try:
        new = args.new.resolve(strict=True)
        old = args.old.resolve(strict=True)
    except OSError as error:
        write_report(report, status="failed", error=f"Handoff executable missing: {error}")
        return 1
    if new == old:
        write_report(report, status="failed", error="The handoff target matches the outgoing editor")
        return 1
    # A leftover acknowledgement from an earlier handoff must never be accepted.
    try:
        args.ack.unlink()
    except OSError:
        pass
    if not wait_for_exit(args.wait_pid, args.exit_timeout):
        write_report(
            report,
            status="failed",
            binary=str(new),
            previous=str(old),
            error="The outgoing editor is still running; no second editor was started",
        )
        return 1
    try:
        child = launch(new, editor_arguments)
    except OSError as error:
        write_report(report, status="failed", binary=str(new), previous=str(old), error=str(error))
        # The user still gets their editor back on the version that worked.
        try:
            launch(old, editor_arguments)
        except OSError:
            pass
        return 1
    deadline = time.monotonic() + args.ack_timeout
    acknowledged_at = None
    while time.monotonic() < deadline or acknowledged_at is not None:
        has_ack = args.ack.exists() and acknowledged(args.ack.resolve(), args.token, new)
        returncode = child.poll()
        if returncode is not None:
            if has_ack and returncode == 0:
                # A normal close after readiness is not a failed startup and
                # must not reopen a project the user just closed.
                write_report(report, status="started", binary=str(new), previous=str(old), closed_normally=True)
                return 0
            # Started and died, or never got far enough to acknowledge: the known
            # good executable is restored instead of leaving the user with none.
            phase = "after acknowledging" if has_ack or acknowledged_at is not None else "before acknowledging"
            exit_error = f"The rebuilt editor exited with code {returncode} {phase}"
            try:
                launch(old, editor_arguments)
            except OSError as failure:
                write_report(
                    report,
                    status="failed",
                    binary=str(new),
                    previous=str(old),
                    error=f"{exit_error}; rollback also failed: {failure}",
                )
                return 1
            write_report(report, status="rolled_back", binary=str(new), previous=str(old), error=exit_error)
            return 1
        now = time.monotonic()
        if has_ack:
            if acknowledged_at is None:
                acknowledged_at = now
            if now - acknowledged_at >= ACK_STABILITY_SECONDS:
                write_report(report, status="started", binary=str(new), previous=str(old))
                return 0
        else:
            acknowledged_at = None
        time.sleep(ACK_POLL_SECONDS)
    # Still alive but silent. It is not killed, and no competing editor is added.
    write_report(
        report,
        status="startup_unconfirmed",
        binary=str(new),
        previous=str(old),
        error="The rebuilt editor did not acknowledge a working AI dock in time",
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
