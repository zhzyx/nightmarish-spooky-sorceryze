#!/usr/bin/env python3
"""Isolated Windows Raw Input / USER-handle regression probe (no clicks or keys).

Each case runs in its own process, temporarily registers a mouse receiver and
sends balanced one-pixel mouse movements. It restores the cursor and foreground
window on exit. No raw input contents are recorded.
"""

import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def worker(mode, count, dll=None, rate=8000):
    user = c.WinDLL("user32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    pointer = c.c_size_t
    result_type = c.c_ssize_t
    callback_type = c.WINFUNCTYPE(result_type, w.HWND, w.UINT, pointer, result_type)

    class WindowClass(c.Structure):
        _fields_ = [("style", w.UINT), ("proc", callback_type), ("extra_class", c.c_int),
                    ("extra_window", c.c_int), ("instance", w.HINSTANCE), ("icon", w.HICON),
                    ("cursor", w.HANDLE), ("background", w.HBRUSH), ("menu", w.LPCWSTR),
                    ("name", w.LPCWSTR)]

    class Device(c.Structure):
        _fields_ = [("page", w.USHORT), ("usage", w.USHORT), ("flags", w.DWORD), ("target", w.HWND)]

    class Header(c.Structure):
        _fields_ = [("kind", w.DWORD), ("size", w.DWORD), ("device", w.HANDLE), ("code", pointer)]

    class MouseInput(c.Structure):
        _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("data", w.DWORD), ("flags", w.DWORD),
                    ("time", w.DWORD), ("extra", pointer)]

    class InputUnion(c.Union):
        _fields_ = [("mouse", MouseInput), ("padding", c.c_byte * 32)]

    class Input(c.Structure):
        _fields_ = [("kind", w.DWORD), ("data", InputUnion)]

    user.DefWindowProcW.argtypes = [w.HWND, w.UINT, pointer, result_type]
    user.DefWindowProcW.restype = result_type
    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int,
                                    c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
    user.CreateWindowExW.restype = w.HWND
    user.RegisterClassW.argtypes = [c.POINTER(WindowClass)]
    user.RegisterRawInputDevices.argtypes = [c.POINTER(Device), w.UINT, w.UINT]
    user.GetRawInputBuffer.argtypes = [c.c_void_p, c.POINTER(w.UINT), w.UINT]
    user.GetRawInputBuffer.restype = w.UINT
    reader = user.GetRawInputBuffer
    native_library = None
    if "safe" in mode:
        if not dll:
            raise RuntimeError("Safe-buffered cases require --native / --dll.")
        native_library = c.WinDLL(dll, use_last_error=True)
        reader = native_library.godot_read_cleaned_buffer
        reader.argtypes = user.GetRawInputBuffer.argtypes
        reader.restype = w.UINT
    user.GetRawInputData.argtypes = [w.HANDLE, w.UINT, c.c_void_p, c.POINTER(w.UINT), w.UINT]
    user.GetRawInputData.restype = w.UINT
    user.PeekMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
    user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
    user.DispatchMessageW.restype = result_type
    user.GetGuiResources.argtypes = [w.HANDLE, w.DWORD]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
    kernel.GetModuleHandleW.restype = w.HMODULE
    user.GetForegroundWindow.restype = w.HWND
    user.SetForegroundWindow.argtypes = [w.HWND]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    user.AttachThreadInput.argtypes = [w.DWORD, w.DWORD, w.BOOL]
    user.SetFocus.argtypes = [w.HWND]
    kernel.GetCurrentThreadId.restype = w.DWORD
    user.DestroyWindow.argtypes = [w.HWND]
    user.ShowWindow.argtypes = [w.HWND, c.c_int]
    user.SendInput.argtypes = [w.UINT, c.POINTER(Input), c.c_int]
    user.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
    user.MsgWaitForMultipleObjectsEx.argtypes = [w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.DWORD]
    user.DefRawInputProc.argtypes = [c.c_void_p, c.c_int, w.UINT]
    user.DefRawInputProc.restype = result_type
    stats = {"mode": mode, "packets": 0, "messages": 0, "invalid_handles": 0, "buffer_errors": 0}
    buf = c.create_string_buffer(65536)
    header_size = c.sizeof(Header)

    @callback_type
    def proc(hwnd, message, code, handle):
        if message == 0xFF:
            stats["messages"] += 1
            size = w.UINT(len(buf))
            read = user.GetRawInputData(w.HANDLE(handle), 0x10000003, buf, c.byref(size), header_size)
            if read == 0xFFFFFFFF:
                stats["invalid_handles"] += 1
            if "hybrid" in mode:
                drain()
        return user.DefWindowProcW(hwnd, message, code, handle)

    wc = WindowClass()
    wc.proc = proc
    wc.instance = kernel.GetModuleHandleW(None)
    wc.name = "GodotRawInputRegression"
    if not user.RegisterClassW(c.byref(wc)):
        raise c.WinError(c.get_last_error())
    previous_foreground = user.GetForegroundWindow()
    previous_cursor = w.POINT()
    user.GetCursorPos(c.byref(previous_cursor))
    hwnd = user.CreateWindowExW(0, wc.name, "Raw Input regression probe", 0x00CF0000,
                                80, 80, 360, 180, None, None, wc.instance, None)
    if not hwnd:
        raise c.WinError(c.get_last_error())
    sink = mode.startswith("sink")
    nolegacy = "nolegacy" in mode
    device = Device(1, 2, 0x100 if sink else (0x30 if nolegacy else 0), hwnd)
    if not user.RegisterRawInputDevices(c.byref(device), 1, c.sizeof(Device)):
        raise c.WinError(c.get_last_error())
    if not sink:
        foreground_thread = user.GetWindowThreadProcessId(previous_foreground, None)
        this_thread = kernel.GetCurrentThreadId()
        attached = user.AttachThreadInput(this_thread, foreground_thread, True)
        try:
            user.ShowWindow(hwnd, 5)
            user.SetForegroundWindow(hwnd)
            user.SetFocus(hwnd)
        finally:
            if attached:
                user.AttachThreadInput(this_thread, foreground_thread, False)
    stats["foreground_acquired"] = user.GetForegroundWindow() == hwnd
    msg = w.MSG()
    process = kernel.GetCurrentProcess()

    def drain():
        for _ in range(128):
            # Match the engine's usual 48-packet batch capacity, including
            # NEXTRAWINPUTBLOCK alignment in the native adapter under test.
            if "tiny" in mode and not stats.get("short_buffer_preserved"):
                probe = w.UINT(1)
                result = reader(buf, c.byref(probe), header_size)
                if result == 0xFFFFFFFF:
                    if c.get_last_error() != 122 or probe.value < header_size:
                        raise RuntimeError("Short-buffer call returned an unexpected error.")
                    needed = w.UINT()
                    if reader(None, c.byref(needed), header_size) != 0 or needed.value != probe.value:
                        raise RuntimeError("Short-buffer call lost the pending packet.")
                    stats["short_buffer_preserved"] = True
            size = w.UINT(48 if "tiny" in mode else 2304)
            started = time.perf_counter_ns()
            read = reader(buf, c.byref(size), header_size)
            stats["max_read_us"] = max(stats.get("max_read_us", 0), (time.perf_counter_ns() - started) // 1000)
            if read == 0xFFFFFFFF:
                stats["buffer_errors"] += 1
                errors = stats.setdefault("buffer_error_codes", {})
                error = str(c.get_last_error())
                errors[error] = errors.get(error, 0) + 1
                break
            if not read:
                break
            stats["packets"] += read
            offset = 0
            for _ in range(read):
                header = Header.from_buffer(buf, offset)
                if header.size < header_size or offset + header.size > size.value:
                    raise RuntimeError("Invalid packed RAWINPUT layout.")
                offset += (header.size + c.sizeof(c.c_void_p) - 1) & ~(c.sizeof(c.c_void_p) - 1)
            if "defraw" in mode:
                user.DefRawInputProc(None, read, header_size)

    def pump():
        if "hybrid" in mode:
            if user.PeekMessageW(c.byref(msg), None, 0xFF, 0xFF, 1):
                user.DispatchMessageW(c.byref(msg))
        elif "standard" not in mode:
            drain()
        if "nopump" in mode:
            return
        if "full" in mode or "standard" in mode:
            for _ in range(4096):
                if not user.PeekMessageW(c.byref(msg), None, 0, 0, 1):
                    break
                user.DispatchMessageW(c.byref(msg))
        else:
            for _ in range(4096):
                found = (user.PeekMessageW(c.byref(msg), None, 0, 0xA0 - 1, 1)
                         or user.PeekMessageW(c.byref(msg), None, 0xA0 + 1, 0xFF - 1, 1)
                         or user.PeekMessageW(c.byref(msg), None, 0xFF + 1, 0x200 - 1, 1)
                         or user.PeekMessageW(c.byref(msg), None, 0x200 + 1, 0xFFFF, 1))
                if not found:
                    break
                user.DispatchMessageW(c.byref(msg))
            for motion in (0x200, 0xA0):
                if user.PeekMessageW(c.byref(msg), None, motion, motion, 1):
                    user.DispatchMessageW(c.byref(msg))

    try:
        pump()
        stats["user_before"] = user.GetGuiResources(process, 1)
        stats["user_peak"] = stats["user_before"]
        sent = 0
        events = (Input * 64)()
        for i, event in enumerate(events):
            event.kind = 0
            event.data.mouse = MouseInput(1 if i % 2 == 0 else -1, 0, 0, 1, 0, 0)
        for _ in range((count + 63) // 64):
            emitted = user.SendInput(64, events, c.sizeof(Input))
            if emitted != 64:
                raise RuntimeError("SendInput failed: %d, Win32 %d" % (emitted, c.get_last_error()))
            sent += emitted
            end = time.monotonic() + 64 / rate
            while time.monotonic() < end:
                pump()
                user.MsgWaitForMultipleObjectsEx(0, None, 1, 0x04FF, 4)
            stats["user_peak"] = max(stats["user_peak"], user.GetGuiResources(process, 1))
        end = time.monotonic() + 0.2
        while time.monotonic() < end:
            pump()
            user.MsgWaitForMultipleObjectsEx(0, None, 1, 0x04FF, 4)
        if "safe" in mode:
            user.PostQuitMessage(17)
            size = w.UINT(len(buf))
            if reader(buf, c.byref(size), header_size) != 0:
                raise RuntimeError("Unexpected input while testing WM_QUIT.")
            if not user.PeekMessageW(c.byref(msg), None, 0x12, 0x12, 1) or msg.message != 0x12 or msg.wParam != 17:
                raise RuntimeError("Buffered adapter swallowed WM_QUIT.")
            stats["quit_preserved"] = True
        stats["sent"] = sent
        stats["target_rate"] = rate
        stats["user_after"] = user.GetGuiResources(process, 1)
        stats["user_delta"] = stats["user_after"] - stats["user_before"]
        print(json.dumps(stats), flush=True)
        if "safe" in mode:
            if not sink and not stats["foreground_acquired"]:
                raise RuntimeError("Foreground case did not acquire focus; result is inconclusive.")
            if stats["packets"] < sent or stats["buffer_errors"] or stats["invalid_handles"]:
                raise RuntimeError("Safe reader lost input or returned errors.")
            if stats["user_delta"] > 4:
                raise RuntimeError("Safe reader retained USER handles.")
    finally:
        removal = Device(1, 2, 1, None)
        user.RegisterRawInputDevices(c.byref(removal), 1, c.sizeof(Device))
        user.DestroyWindow(hwnd)
        if previous_foreground:
            user.SetForegroundWindow(previous_foreground)
        user.SetCursorPos(previous_cursor.x, previous_cursor.y)


def compile_native_adapter(directory):
    # Compile the actual edited method, not a Python approximation. The
    # standalone DLL has no Godot dependency and never rebuilds the editor.
    root = Path(__file__).resolve().parents[1]
    source = (root / "platform/windows/os_windows.cpp").read_text(encoding="utf-8")
    start = source.index("UINT DisplayServerWindows::GetRawInputBuffer(")
    end = source.index("\n#if defined(TOOLS_ENABLED) && defined(DEV_ENABLED)\nUINT DisplayServerWindows::GetRawInputData", start)
    method = source[start:end]
    harness = "#include <windows.h>\nclass DisplayServerWindows { public: static UINT GetRawInputBuffer(PRAWINPUT, PUINT, UINT); };\n"
    harness += method
    harness += '\nextern "C" __declspec(dllexport) UINT godot_read_cleaned_buffer(PRAWINPUT data, PUINT size, UINT header) { return DisplayServerWindows::GetRawInputBuffer(data, size, header); }\n'
    cpp = Path(directory) / "raw_input_adapter.cpp"
    cpp.write_text(harness, encoding="utf-8")
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
                                           "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                                          text=True).strip()
    if not installation:
        raise RuntimeError("No MSVC C++ installation found.")
    environment = Path(installation) / "Common7/Tools/VsDevCmd.bat"
    command = 'call "%s" -no_logo -arch=x64 && cl /nologo /EHsc /std:c++17 /O2 /LD /W4 /WX raw_input_adapter.cpp user32.lib /Fe:raw_input_adapter.dll' % environment
    # cmd.exe parses quotes itself, unlike executables using CRT argv rules.
    build = subprocess.run('cmd.exe /d /s /c "' + command + '"', cwd=directory,
                           capture_output=True, text=True, timeout=60)
    if build.returncode:
        raise RuntimeError("Native probe compilation failed:\n" + build.stdout + build.stderr)
    print("Native adapter compiled successfully (MSVC /W4 /WX).", flush=True)
    return str(Path(directory) / "raw_input_adapter.dll")


def run_cases(args, dll):
    modes = ["sink_filtered", "sink_filtered_defraw", "sink_standard", "sink_hybrid"]
    if dll:
        modes += ["sink_safe", "foreground_safe", "sink_safe_tiny"]
    for mode in modes:
        command = [sys.executable, __file__, "--worker", mode, "--count", str(args.count), "--rate", str(args.rate)]
        if dll:
            command += ["--dll", dll]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        sys.stdout.write(completed.stdout)
        sys.stdout.flush()
        if completed.returncode:
            sys.stderr.write(completed.stderr)
            raise SystemExit(completed.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    parser.add_argument("--count", type=int, default=2048)
    parser.add_argument("--rate", type=int, default=8000)
    parser.add_argument("--native", action="store_true", help="Compile and test the actual C++ adapter")
    parser.add_argument("--dll")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This probe requires Windows.")
    if not 64 <= args.count <= 65536:
        parser.error("--count must be between 64 and 65536.")
    if not 100 <= args.rate <= 16000:
        parser.error("--rate must be between 100 and 16000.")
    if args.worker:
        worker(args.worker, args.count, args.dll, args.rate)
        return
    if args.native:
        with tempfile.TemporaryDirectory(prefix="godot_raw_input_test_") as directory:
            run_cases(args, compile_native_adapter(directory))
    else:
        run_cases(args, args.dll)


if __name__ == "__main__":
    main()
