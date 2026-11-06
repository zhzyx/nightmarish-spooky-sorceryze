"""Small stdlib durable-job primitives. No ML imports or shell commands."""
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import tempfile
import time


def write_new(path, value):
    path = Path(path)
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode('utf-8')
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


@contextmanager
def exclusive(path, blocking=True):
    stream = open(path, 'a+b')
    if stream.tell()==0:
        stream.write(b'0'); stream.flush()
    acquired = False
    try:
        while True:
            stream.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                acquired = True
                break
            except (BlockingIOError,OSError):
                if not blocking: raise BlockingIOError('Job lock held')
                time.sleep(.05)
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        stream.close()


def process_identity(pid):
    """PID plus OS creation identity prevents mistaking a reused PID for a job."""
    if os.name=='nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000,False,pid)
        if not handle: return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259: return None
            if not kernel.GetProcessTimes(handle,*[ctypes.byref(v) for v in times]): return None
            return {'pid':pid,'created':(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime}
        finally: kernel.CloseHandle(handle)
    try:
        fields = Path('/proc',str(pid),'stat').read_text().split()
        return None if fields[2]=='Z' else {'pid':pid,'created':fields[21]}
    except OSError: return None


def alive(identity):
    return bool(identity and process_identity(identity['pid'])==identity)
