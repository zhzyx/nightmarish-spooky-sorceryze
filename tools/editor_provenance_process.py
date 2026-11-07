"""A private Windows Job owns the command before its first thread runs.

The primary thread is recovered through documented Tool Help APIs because
Popen closes its original thread handle. A suspended child is never resumed
after an assignment or ownership check fails. The Job handle is noninheritable
and keeps KILL_ON_JOB_CLOSE enabled until the guard finishes verification.
"""

import ctypes
import os
import re
import subprocess
import time

DWORD = ctypes.c_uint32
LONG = ctypes.c_int32
HANDLE = ctypes.c_void_p
BOOL = ctypes.c_int32
SIZE_T = ctypes.c_size_t
CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_QUERY = 0x0004
ERROR_NO_MORE_FILES = 18
ERROR_ALREADY_EXISTS = 183
NAME = re.compile(r"Local\\GongGongProvenance-[a-f0-9]{32}\Z")


class ProcessError(ValueError):
    pass


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ThreadID", DWORD),
        ("th32OwnerProcessID", DWORD),
        ("tpBasePri", LONG),
        ("tpDeltaPri", LONG),
        ("dwFlags", DWORD),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", DWORD),
        ("MinimumWorkingSetSize", SIZE_T),
        ("MaximumWorkingSetSize", SIZE_T),
        ("ActiveProcessLimit", DWORD),
        ("Affinity", SIZE_T),
        ("PriorityClass", DWORD),
        ("SchedulingClass", DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", SIZE_T),
        ("JobMemoryLimit", SIZE_T),
        ("PeakProcessMemoryUsed", SIZE_T),
        ("PeakJobMemoryUsed", SIZE_T),
    ]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_int64)
        for name in ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")
    ]
    _fields_ += [
        (name, DWORD)
        for name in ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")
    ]


class WinAPI:
    def __init__(self):
        if os.name != "nt":
            raise ProcessError("provenance_windows_job_unavailable")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, ctypes.c_wchar_p], HANDLE),
            "OpenJobObjectW": ([DWORD, BOOL, ctypes.c_wchar_p], HANDLE),
            "SetInformationJobObject": ([HANDLE, ctypes.c_int32, ctypes.c_void_p, DWORD], BOOL),
            "QueryInformationJobObject": ([HANDLE, ctypes.c_int32, ctypes.c_void_p, DWORD, ctypes.c_void_p], BOOL),
            "AssignProcessToJobObject": ([HANDLE, HANDLE], BOOL),
            "TerminateJobObject": ([HANDLE, DWORD], BOOL),
            "SetHandleInformation": ([HANDLE, DWORD, DWORD], BOOL),
            "CloseHandle": ([HANDLE], BOOL),
            "CreateToolhelp32Snapshot": ([DWORD, DWORD], HANDLE),
            "Thread32First": ([HANDLE, ctypes.POINTER(THREADENTRY32)], BOOL),
            "Thread32Next": ([HANDLE, ctypes.POINTER(THREADENTRY32)], BOOL),
            "OpenThread": ([DWORD, BOOL, DWORD], HANDLE),
            "GetProcessIdOfThread": ([HANDLE], DWORD),
            "ResumeThread": ([HANDLE], DWORD),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes = arguments
            function.restype = result

    def close(self, handle):
        if handle and not self.kernel.CloseHandle(handle):
            raise ProcessError("provenance_windows_handle_close_failed")

    def create(self, name):
        ctypes.set_last_error(0)
        handle = self.kernel.CreateJobObjectW(None, name)
        error = ctypes.get_last_error()
        if not handle:
            raise ProcessError("provenance_windows_job_create_failed")
        try:
            if error == ERROR_ALREADY_EXISTS:
                raise ProcessError("provenance_windows_job_collision")
            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ProcessError("provenance_windows_job_limits_failed")
            if not self.kernel.SetHandleInformation(handle, 1, 0):
                raise ProcessError("provenance_windows_job_inheritance_failed")
            return handle
        except BaseException:
            self.close(handle)
            raise

    def assign(self, handle, child):
        if not self.kernel.AssignProcessToJobObject(handle, int(child._handle)):
            raise ProcessError("provenance_windows_job_assignment_failed")

    def threads(self, pid):
        snapshot = self.kernel.CreateToolhelp32Snapshot(0x00000004, 0)
        if snapshot in (None, ctypes.c_void_p(-1).value):
            raise ProcessError("provenance_windows_thread_snapshot_failed")
        found = []
        try:
            entry = THREADENTRY32()
            entry.dwSize = ctypes.sizeof(entry)
            first = self.kernel.Thread32First(snapshot, ctypes.byref(entry))
            if not first and ctypes.get_last_error() != ERROR_NO_MORE_FILES:
                raise ProcessError("provenance_windows_thread_snapshot_failed")
            count = 0
            while first:
                count += 1
                if count > 100000 or entry.dwSize < ctypes.sizeof(entry):
                    raise ProcessError("provenance_windows_thread_snapshot_failed")
                if entry.th32OwnerProcessID == pid:
                    found.append(entry.th32ThreadID)
                entry.dwSize = ctypes.sizeof(entry)
                first = self.kernel.Thread32Next(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != ERROR_NO_MORE_FILES:
                raise ProcessError("provenance_windows_thread_snapshot_failed")
            return found
        finally:
            self.close(snapshot)

    def resume(self, child):
        threads = self.threads(child.pid)
        if len(threads) != 1:
            raise ProcessError("provenance_windows_primary_thread_ambiguous")
        thread = self.kernel.OpenThread(0x0802, False, threads[0])
        if not thread:
            raise ProcessError("provenance_windows_primary_thread_unavailable")
        try:
            if self.kernel.GetProcessIdOfThread(thread) != child.pid:
                raise ProcessError("provenance_windows_primary_thread_owner_changed")
            if self.kernel.ResumeThread(thread) != 1:
                raise ProcessError("provenance_windows_primary_thread_not_suspended")
        finally:
            self.close(thread)

    def active(self, handle):
        accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not self.kernel.QueryInformationJobObject(
            handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None
        ):
            raise ProcessError("provenance_windows_job_query_failed")
        return accounting.ActiveProcesses

    def terminate(self, handle):
        if not self.kernel.TerminateJobObject(handle, 143):
            raise ProcessError("provenance_windows_job_terminate_failed")

    def open_query(self, name):
        handle = self.kernel.OpenJobObjectW(JOB_OBJECT_QUERY, False, name)
        if not handle and ctypes.get_last_error() != 2:
            raise ProcessError("provenance_windows_job_recovery_query_failed")
        return handle


def job_name(token):
    name = "Local\\GongGongProvenance-" + token
    if not NAME.fullmatch(name):
        raise ProcessError("provenance_windows_job_name_invalid")
    return name


class WindowsJob:
    def __init__(self, token, api=None):
        self.name = job_name(token)
        self.api = WinAPI() if api is None else api
        self.handle = self.api.create(self.name)
        self.child = None
        self.assigned = False
        self.cleanup_verified = False

    def spawn(self, argv, cwd=None, stdout=None, stderr=None):
        if self.child is not None or self.handle is None:
            raise ProcessError("provenance_windows_job_spawn_invalid")
        child = subprocess.Popen(
            argv, cwd=cwd, stdout=stdout, stderr=stderr, close_fds=True, creationflags=CREATE_SUSPENDED
        )
        self.child = child
        try:
            self.api.assign(self.handle, child)
            self.assigned = True
            self.api.resume(child)
            return child
        except BaseException:
            # Before assignment this child is suspended and cannot create
            # descendants. After assignment the whole Job is our boundary.
            try:
                if self.assigned:
                    self.api.terminate(self.handle)
                    self.wait_empty()
                elif child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired, ProcessError):
                raise ProcessError("provenance_windows_suspended_cleanup_unverified") from None
            self.cleanup_verified = True
            raise

    def wait_empty(self, timeout=5):
        deadline = time.monotonic() + timeout
        while self.api.active(self.handle):
            if time.monotonic() >= deadline:
                raise ProcessError("provenance_windows_job_termination_unverified")
            time.sleep(0.02)

    def cancel(self):
        self.api.terminate(self.handle)
        self.wait_empty()

    def quiesce(self):
        if self.api.active(self.handle) == 0:
            return False
        self.cancel()
        return True

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self.api.close(handle)

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        self.close()


def job_is_quiet(token, api=None):
    api = WinAPI() if api is None else api
    handle = api.open_query(job_name(token))
    if handle is None:
        # KILL_ON_JOB_CLOSE destroys a Job only after its associated processes
        # terminate; an absent private Job has no remaining workload.
        return True
    try:
        return api.active(handle) == 0
    finally:
        api.close(handle)
