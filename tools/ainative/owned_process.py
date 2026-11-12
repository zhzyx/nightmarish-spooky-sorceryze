"""Bounded output and lifetime for trusted generation commands and their children.

POSIX commands get a private session. The leader is observed with WNOWAIT and
kept unreaped until cleanup, pinning its process-group identity even after exit.
Windows assigns the suspended command to a kill-on-close Job before resuming.
Launch/watch workflows retain the launch owner in a scope; persisted PIDs are
never adopted or signalled. This does not cancel remote service work, and POSIX
commands must not deliberately escape their session with setsid/setpgid.
"""

import array
import ctypes
import functools
import hashlib
import importlib.util
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


class OwnedProcessError(ValueError):
    pass


def _windows_helper_path():
    folder = Path(__file__).resolve().parent
    # Repository sources live in tools/ainative; embedded tools are flattened.
    if folder.name == "ainative" and folder.parent.name == "tools":
        folder = folder.parent
    return folder / "editor_provenance_process.py"


def implementation_fingerprint():
    paths = [Path(__file__)]
    if os.name == "nt":
        paths.append(_windows_helper_path())
    return [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]


def _windows_module():
    # Reuse the committed host implementation without changing sys.path or
    # depending on optional packages. The host helper ships beside ainative.
    path = _windows_helper_path()
    spec = importlib.util.spec_from_file_location("_generation_windows_job", path)
    if spec is None or spec.loader is None:
        raise OwnedProcessError("owned_process_job_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _windows_api():
    return _windows_module().WinAPI()


def _darwin_group_quiet(pgid):
    """Darwin killpg returns EPERM for zombie-only groups; libproc hides zombies.

    The absolute OS ps path queries only numeric group membership and state.
    The unreaped leader still pins this PGID; an all-zombie snapshot cannot
    create more children. Missing, malformed or truncated evidence is unknown.
    """
    result = subprocess.run(
        ["/bin/ps", "-g", str(pgid), "-o", "pid=,pgid=,stat="],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=2,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if result.returncode != 0 or not result.stdout or len(result.stdout) > 1024 * 1024:
        return False
    found_leader = False
    for line in result.stdout.splitlines():
        fields = line.split()
        if (
            len(fields) != 3
            or not fields[0].isdigit()
            or fields[1] != str(pgid).encode()
            or not fields[2].startswith(b"Z")
        ):
            return False
        found_leader |= int(fields[0]) == pgid
    return found_leader


def _pipe_pending(pipe):
    """Bytes available now, or None for EOF, without consuming or blocking."""
    if os.name == "nt":
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        peek = kernel.PeekNamedPipe
        peek.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        peek.restype = wintypes.BOOL
        available = wintypes.DWORD()
        if not peek(msvcrt.get_osfhandle(pipe.fileno()), None, 0, None, ctypes.byref(available), None):
            if ctypes.get_last_error() == 109:  # ERROR_BROKEN_PIPE: all writers closed
                return None
            raise OSError("owned_process_pipe_query_failed")
        return available.value
    import fcntl
    import select
    import termios

    if not select.select([pipe], [], [], 0)[0]:
        return 0
    available = array.array("i", [0])
    fcntl.ioctl(pipe.fileno(), termios.FIONREAD, available, True)
    return available[0] or None  # readable with zero bytes is EOF


class OwnedCommand:
    def __init__(self, arguments, *, stdout, stderr, env, limit, stdin=None, windows_api=None):
        self.process = None
        self.api = None
        self.job = None
        self.assigned = False
        self.readers = []
        self.overflow = threading.Event()
        self.read_error = threading.Event()
        self.closed = False
        self.channels = []
        self.outputs = []
        self.fail = None
        try:
            if os.name == "nt" or windows_api is not None:
                self.api = windows_api or _windows_api()
                self.job = self.api.create("Local\\GongGongProvenance-" + secrets.token_hex(16))
            self.process = subprocess.Popen(
                arguments,
                stdin=stdin if stdin is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT if stderr is None else subprocess.PIPE,
                env=env,
                close_fds=True,
                start_new_session=self.api is None,
                creationflags=0x08000004 if self.api is not None else 0,
            )
            if self.api is not None:
                self.api.assign(self.job, self.process)
                self.assigned = True
                self.api.resume(self.process)
            for pipe, output in ((self.process.stdout, stdout), (self.process.stderr, stderr)):
                if pipe is None:
                    continue
                output = os.fdopen(os.dup(output.fileno()), "wb")
                self.outputs.append(output)
                channel = dict(pipe=pipe, output=output, remaining=limit, lock=threading.Lock(), done=False)
                self.channels.append(channel)
                reader = threading.Thread(target=self._drain, args=(channel,), daemon=True)
                self.readers.append(reader)
                reader.start()
        except BaseException:
            self.close()
            raise

    def _pump(self, channel):
        # The thread and the launch-exit observer use this same lock. A reader
        # cannot have consumed bytes that are still waiting to be written when
        # observe_output returns. Never hold the lock across a blocking read.
        with channel["lock"]:
            try:
                while not channel["done"]:
                    pending = _pipe_pending(channel["pipe"])
                    if pending is None:
                        channel["done"] = True
                        return
                    if not pending:
                        return
                    data = os.read(channel["pipe"].fileno(), min(pending, 65536))
                    if not data:
                        channel["done"] = True
                        return
                    remaining = channel["remaining"]
                    if len(data) > remaining:
                        self.overflow.set()
                    if remaining:
                        written = data[:remaining]
                        channel["output"].write(written)
                        channel["output"].flush()
                        channel["remaining"] -= len(written)
                    if self.overflow.is_set():
                        # Stop draining after overflow; pipe backpressure bounds
                        # the writer until the controller terminates its owner.
                        channel["done"] = True
                        return
            except (OSError, ValueError):
                self.read_error.set()
                channel["done"] = True

    def _drain(self, channel):
        while not channel["done"]:
            self._pump(channel)
            if not channel["done"]:
                time.sleep(0.01)

    def observe_output(self):
        """Drain all bytes available after direct exit, without killing children.

        The exited launcher cannot write additional bytes. Descendants may keep
        a pipe open, so EOF is not required. Sharing the pumping lock also waits
        for an already-consumed chunk to be flushed, regardless of scheduling.
        """
        for channel in self.channels:
            self._pump(channel)

    def poll(self):
        if self.api is not None:
            return self.process.poll()
        result = os.waitid(os.P_PID, self.process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if result is None:
            return None
        return result.si_status if result.si_code == os.CLD_EXITED else -result.si_status

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.process is not None:
                if self.api is None:
                    # Never poll()/wait() before this signal: the unreaped
                    # direct child pins the group identifier against PID reuse.
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        if sys.platform != "darwin" or self.poll() is None or not _darwin_group_quiet(self.process.pid):
                            raise
                elif self.job is not None:
                    if self.assigned:
                        self.api.terminate(self.job)
                    # Assignment can fail while the child is still suspended.
                    elif self.process.poll() is None:
                        self.process.kill()
                self.process.wait(timeout=5)
                if self.api is not None and self.assigned:
                    deadline = time.monotonic() + 5
                    while self.api.active(self.job):
                        if time.monotonic() >= deadline:
                            raise OwnedProcessError("owned_process_cleanup_unverified")
                        time.sleep(0.02)
            for reader in self.readers:
                reader.join(timeout=5)
                if reader.is_alive():
                    raise OwnedProcessError("owned_process_output_cleanup_unverified")
            if self.process is not None:
                for pipe in (self.process.stdout, self.process.stderr):
                    if pipe is not None:
                        pipe.close()
            for output in self.outputs:
                output.close()
        finally:
            if self.job is not None:
                job, self.job = self.job, None
                self.api.close(job)


class OwnedScope:
    def __init__(self):
        self.commands = []

    def active(self):
        for command in self.commands:
            if command.overflow.is_set() or command.read_error.is_set():
                command.fail("output")
                return False
        return True

    def close(self):
        error = None
        for command in reversed(self.commands):
            try:
                command.close()
            except Exception as exc:
                error = exc
        if error is not None:
            raise error
        if not self.active():
            raise OwnedProcessError("owned_process_output_invalid")


def owned_scope(method):
    """Keep asynchronous launch descendants owned through watch and parsing."""

    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        if getattr(self, "_generation_scope", None) is not None:
            return method(self, *args, **kwargs)
        scope = self._generation_scope = OwnedScope()
        try:
            return method(self, *args, **kwargs)
        finally:
            try:
                scope.close()
            finally:
                self._generation_scope = None

    return wrapped


def run_owned(arguments, *, stdout, stderr=None, env=None, limit, timeout, active, fail, stdin=None, scope=None):
    """Return a direct exit code or None after durable cancellation/failure.

    Output is capped while draining, including a short-lived writer that exits
    between polls. A retained launch keeps its pipes open until scope cleanup.
    """
    if not active():
        return None
    command = OwnedCommand(arguments, stdout=stdout, stderr=stderr, env=env, limit=limit, stdin=stdin)
    command.fail = fail
    retained = False
    deadline = time.monotonic() + timeout
    try:
        while True:
            if not active():
                return None
            if command.overflow.is_set() or command.read_error.is_set():
                fail("output")
                return None
            code = command.poll()
            if code is not None:
                if scope is not None and code == 0:
                    command.observe_output()
                    scope.commands.append(command)
                    retained = True
                else:
                    command.close()
                # Both branches observe output before exposing success. The
                # retained launch remains owned through watch and parsing.
                if command.overflow.is_set() or command.read_error.is_set():
                    fail("output")
                    return None
                return code
            if time.monotonic() >= deadline:
                fail("timeout")
                return None
            time.sleep(0.02)
    finally:
        if not retained:
            command.close()
