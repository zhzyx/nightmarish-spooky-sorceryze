# Attach the waiting bridge to a kill-on-close job before it starts any CLI.
# Keep the sole long-lived job handle in that bridge, including on forced termination.
param([Parameter(Mandatory)][int]$BridgeProcess)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class CodexBridgeJob {
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimits {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr Minimum, Maximum;
        public uint ActiveProcesses;
        public UIntPtr Affinity;
        public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct Limits {
        public BasicLimits Basic;
        public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32", SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job, int kind, ref Limits info, int size);
    [DllImport("kernel32", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, int id);
    [DllImport("kernel32", SetLastError=true)] static extern bool DuplicateHandle(IntPtr source, IntPtr handle, IntPtr target, out IntPtr copy, uint access, bool inherit, uint options);
    [DllImport("kernel32", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32")] static extern bool CloseHandle(IntPtr handle);
    public static void Attach(int id) {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new Win32Exception();
        IntPtr bridge = OpenProcess(0x0100 | 0x0001 | 0x0040, false, id);
        try {
            Limits limits = new Limits();
            limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            IntPtr copy;
            if (bridge == IntPtr.Zero || !SetInformationJobObject(job, 9, ref limits, Marshal.SizeOf(limits))
                || !DuplicateHandle(new IntPtr(-1), job, bridge, out copy, 0, false, 2)
                || !AssignProcessToJobObject(job, bridge)) throw new Win32Exception();
        } finally {
            if (bridge != IntPtr.Zero) CloseHandle(bridge);
            CloseHandle(job);
        }
    }
}
"@
[CodexBridgeJob]::Attach($BridgeProcess)
