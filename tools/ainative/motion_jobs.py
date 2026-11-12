"""Small stdlib durable-job primitives. No ML imports or shell commands."""

import ctypes
import json
import os
import struct
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def write_new(path, value):
    path = Path(path)
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


@contextmanager
def exclusive(path, blocking=True):
    stream = open(path, "a+b")
    if stream.tell() == 0:
        stream.write(b"0")
        stream.flush()
    acquired = False
    try:
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (BlockingIOError, OSError):
                if not blocking:
                    raise BlockingIOError("Job lock held")
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def process_identity(pid):
    """PID plus OS creation identity prevents mistaking a reused PID for a job."""
    if type(pid) is not int or not 0 < pid <= 0x7FFFFFFF:
        return None
    if os.name == "nt":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return None
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(v) for v in times]):
                return None
            return {"pid": pid, "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime}
        finally:
            kernel.CloseHandle(handle)
    try:
        if sys.platform == "darwin":
            # Darwin proc_bsdinfo (PROC_PIDTBSDINFO): kernel creation timeval,
            # not a wall-clock estimate or executable name. SZOMB is 5.
            layout = struct.Struct("=12I48s6IQQ")
            buffer = ctypes.create_string_buffer(layout.size)
            query = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True).proc_pidinfo
            query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
            query.restype = ctypes.c_int
            if query(pid, 3, 0, buffer, len(buffer)) != len(buffer):
                return None
            fields = layout.unpack(buffer.raw)
            if fields[1] == 5 or fields[3] != pid:
                return None
            return {"pid": pid, "created": f"darwin:{fields[-2]}.{fields[-1]:06d}"}
        if sys.platform.startswith("linux"):
            # comm may contain spaces and parentheses; starttime is field 22.
            fields = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
            return None if fields[0] == "Z" else {"pid": pid, "created": fields[19]}
        return None
    except (OSError, ValueError, IndexError):
        return None


def alive(identity):
    return bool(isinstance(identity, dict) and process_identity(identity.get("pid")) == identity)


def process_state(identity):
    """Return running/dead/unknown; lack of inspection permission is not death."""
    if not isinstance(identity, dict) or type(identity.get("pid")) is not int or not identity.get("created"):
        return "unknown"
    pid = identity["pid"]
    if not 0 < pid <= 0x7FFFFFFF:
        return "unknown"
    current = process_identity(pid)
    if current is not None:
        return "running" if current == identity else "dead"
    if os.name == "nt":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return "dead" if ctypes.get_last_error() == 87 else "unknown"
        try:
            code = wintypes.DWORD()
            return "dead" if kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259 else "unknown"
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # existence query only; never terminate a persisted PID
    except ProcessLookupError:
        return "dead"
    except OSError:
        pass
    return "unknown"
