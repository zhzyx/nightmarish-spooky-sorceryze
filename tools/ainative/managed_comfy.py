"""Private local ComfyUI lifecycle, independent of the generation provider.

Only a detached supervisor holds Popen handles. Clients never kill a recorded
PID. Each editor renews its returned lease_path (mtime) every two seconds and
removes it on exit, or calls release/stop. Leases expire after 15 seconds.
Last release waits for an empty, verifiable queue; it never calls /interrupt.
All paths, control credentials and logs in this module are machine-local data.
"""

import argparse
import contextlib
import ctypes
import hashlib
import hmac
import http.client
import io
import ipaddress
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LEASE_SECONDS = 15
MAX_JSON = 16 * 1024 * 1024
TERMINAL = {"stopped", "failed"}
_DETACHED_SUPERVISORS: list[subprocess.Popen[bytes]] = []


class ManagedError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _read(path):
    with open(path, "r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def _write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    with open(temporary, "x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("operation deadline exceeded")
    return value


class _DeadlineReader(io.RawIOBase):
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline
        self.stream = sock.makefile("rb", buffering=0)

    def readable(self):
        return True

    def readinto(self, buffer):
        self.sock.settimeout(_remaining(self.deadline))
        return self.stream.readinto(buffer)

    def close(self):
        self.stream.close()
        super().close()


class _DeadlineSocket:
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline

    def __getattr__(self, name):
        return getattr(self.sock, name)

    def makefile(self, *args, **kwargs):
        # Enforce the same deadline on every low-level read, including slowly
        # streamed HTTP headers. An idle socket timeout alone is insufficient.
        return io.BufferedReader(_DeadlineReader(self.sock, self.deadline))


def _http(url, payload=None, timeout=0.7, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    parsed = urllib.parse.urlsplit(url)
    deadline = time.monotonic() + max(0.001, timeout)

    class Connection(http.client.HTTPConnection):
        def connect(self):
            raw_socket = socket.create_connection((self.host, self.port), timeout=_remaining(deadline))
            self.sock = _DeadlineSocket(raw_socket, deadline)

    connection = Connection(parsed.hostname, parsed.port, timeout=_remaining(deadline))
    try:
        connection.request("GET" if payload is None else "POST", parsed.path or "/", body=data, headers=headers or {})
        with connection.getresponse() as response:
            if response.status != 200:
                raise ValueError("HTTP status or redirect refused")
            raw = response.read(MAX_JSON + 1)
    finally:
        connection.close()
    if len(raw) > MAX_JSON:
        raise ValueError("oversized response")
    return json.loads(raw)


def _endpoint(value):
    try:
        url = urllib.parse.urlsplit(value)
        host = url.hostname
        valid_host = host == "localhost" or (host and ipaddress.ip_address(host).is_loopback)
        if (
            url.scheme != "http"
            or not valid_host
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or not url.port
            or not 1 <= url.port <= 65535
        ):
            raise ValueError()
        # Use one canonical binding; localhost must resolve locally, never DNS.
        if host in ("localhost", "127.0.0.1"):
            host = "127.0.0.1"
        else:
            host = str(ipaddress.ip_address(host))
        return "http://" + ("[" + host + "]" if ":" in host else host) + ":" + str(url.port)
    except (ValueError, TypeError):
        raise ManagedError("address_invalid", "本机模型只允许带明确端口的回环 http 地址；请修正本机配置。") from None


def _model(value):
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise ManagedError("model_invalid", "配置未声明有效的现有模型；请检查 checkpoints 中的模型名称。")
    if any(ord(c) < 32 for c in value) or ":" in value or ".." in value.replace("\\", "/").split("/"):
        raise ManagedError("model_invalid", "模型名称不能包含绝对路径或上级目录。")
    return value


def _inspect(request):
    root_value = request.get("runtime_root", "")
    if not isinstance(root_value, str) or not root_value:
        raise ManagedError("runtime_missing", "请选择已安装的本机 ComfyUI 运行库目录。")
    root = Path(root_value).expanduser().resolve()
    python = next((p for p in (root / "venv/Scripts/python.exe", root / "venv/bin/python") if p.is_file()), None)
    main = root / "ComfyUI-src/main.py"
    if python is None or not main.is_file():
        raise ManagedError("runtime_invalid", "运行库缺少 venv Python 或 ComfyUI-src/main.py；请选择完整的已有运行库。")
    config = Path(request.get("config_path") or root / "config.json").expanduser().resolve()
    try:
        body = _read(config)
        if not isinstance(body, dict) or not isinstance(body.get("checkpoints"), dict):
            raise ValueError("invalid configuration")
        endpoint = _endpoint(body.get("endpoint", ""))
        checkpoints = body["checkpoints"]
        mesh = _model(checkpoints["mesh"]["name"])
        image = _model(checkpoints["image"]["name"]) if checkpoints.get("image", {}).get("name") else ""
        for name in (mesh, image):
            if name and not any(
                (folder / name).is_file()
                for folder in (root / "models/checkpoints", root / "ComfyUI-src/models/checkpoints")
            ):
                raise ManagedError(
                    "model_missing", "配置声明的模型文件不存在；请恢复已有模型，管理器不会下载或更换模型。"
                )
        revision = body.get("backend_revision", "unreported")
        if not isinstance(revision, str) or len(revision) > 200 or any(ord(c) < 32 for c in revision):
            revision = "unreported"
    except ManagedError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ManagedError("config_invalid", "无法读取运行库 config.json；请检查现有本机配置和读取权限。") from None
    return dict(
        valid=True,
        runtime_root=str(root),
        python=str(python),
        main=str(main),
        config_path=str(config),
        endpoint=endpoint,
        image_model=image,
        mesh_model=mesh,
        backend_revision=revision,
    )


def _probe(config, timeout=0.7):
    deadline = time.monotonic() + timeout
    try:
        info = _http(config["endpoint"] + "/object_info", timeout=_remaining(deadline))
        names = info["ImageOnlyCheckpointLoader"]["input"]["required"]["ckpt_name"][0]
        if not isinstance(names, list) or config["mesh_model"] not in names:
            return dict(
                connected=False,
                code="service_model_missing",
                message="端口服务未提供配置中的 Mesh 模型；请检查服务与运行库是否对应。",
            )
        stats = _http(config["endpoint"] + "/system_stats", timeout=_remaining(deadline))
        queue = _http(config["endpoint"] + "/queue", timeout=_remaining(deadline))
        if not isinstance(stats, dict) or not isinstance(queue, dict) or not isinstance(stats.get("system"), dict):
            raise ValueError("invalid service status")
        running, pending = queue["queue_running"], queue["queue_pending"]
        if not isinstance(running, list) or not isinstance(pending, list):
            raise ValueError("invalid queue")
        revision = stats.get("system", {}).get("comfyui_version", "unreported")
        if not isinstance(revision, str) or len(revision) > 200 or any(ord(c) < 32 for c in revision):
            revision = "unreported"
        return dict(
            connected=True,
            queue_busy=bool(running or pending),
            backend_revision=revision,
            devices=stats.get("devices", []) if isinstance(stats.get("devices", []), list) else [],
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, http.client.HTTPException):
        return dict(
            connected=False,
            code="service_unreachable",
            message="未收到兼容的本机 Mesh 服务、设备与任务队列响应；请查看本机启动日志。",
        )


def _port_open(endpoint, timeout=0.2):
    url = urllib.parse.urlsplit(endpoint)
    try:
        with socket.create_connection((url.hostname, url.port), timeout=max(0.001, timeout)):
            return True
    except OSError:
        return False


def _process_identity(pid):
    """Creation identity, only for diagnosis and stale supervisor detection."""
    try:
        if os.name == "nt":
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return ""
            try:
                times = [wintypes.FILETIME() for _ in range(4)]
                if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                    return ""
                return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
            finally:
                kernel.CloseHandle(handle)
        stat = Path("/proc") / str(pid) / "stat"
        return stat.read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, ValueError, IndexError):
        return ""


def _listener_pid(endpoint):
    """Never infer ownership from a live PID: inspect the actual TCP listener."""
    url = urllib.parse.urlsplit(endpoint)
    if os.name == "nt":
        from ctypes import wintypes

        api = ctypes.WinDLL("iphlpapi")
        family = socket.AF_INET6 if ":" in url.hostname else socket.AF_INET
        size = wintypes.DWORD(0)
        api.GetExtendedTcpTable(None, ctypes.byref(size), False, family, 3, 0)
        buffer = ctypes.create_string_buffer(size.value)
        if api.GetExtendedTcpTable(buffer, ctypes.byref(size), False, family, 3, 0):
            return None
        count = struct.unpack_from("I", buffer.raw)[0]
        row_size = 56 if family == socket.AF_INET6 else 24
        for index in range(count):
            row = buffer.raw[4 + row_size * index : 4 + row_size * (index + 1)]
            port_offset, state_offset, pid_offset = (20, 48, 52) if family == socket.AF_INET6 else (8, 0, 20)
            address = socket.inet_ntop(family, row[:16] if family == socket.AF_INET6 else row[4:8])
            if (
                address in (url.hostname, "::" if family == socket.AF_INET6 else "0.0.0.0")
                and struct.unpack_from("I", row, state_offset)[0] == 2
                and struct.unpack_from("!H", row, port_offset)[0] == url.port
            ):
                return struct.unpack_from("I", row, pid_offset)[0]
        return None
    if sys.platform.startswith("linux"):
        inodes = set()
        for table in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                for line in Path(table).read_text().splitlines()[1:]:
                    fields = line.split()
                    address_hex, port_hex = fields[1].split(":")
                    raw_address = bytes.fromhex(address_hex)
                    is_v6 = len(raw_address) == 16
                    address = socket.inet_ntop(
                        socket.AF_INET6 if is_v6 else socket.AF_INET,
                        b"".join(raw_address[i : i + 4][::-1] for i in range(0, len(raw_address), 4)),
                    )
                    if (
                        fields[3] == "0A"
                        and int(port_hex, 16) == url.port
                        and address in (url.hostname, "::" if is_v6 else "0.0.0.0")
                    ):
                        inodes.add(fields[9])
            except OSError:
                pass
        for process in Path("/proc").iterdir():
            if process.name.isdigit():
                try:
                    for fd in (process / "fd").iterdir():
                        if os.readlink(fd) in {"socket:[" + inode + "]" for inode in inodes}:
                            return int(process.name)
                except OSError:
                    pass
        return None
    try:
        address = "[" + url.hostname + "]" if ":" in url.hostname else url.hostname
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP@" + address + ":" + str(url.port), "-sTCP:LISTEN", "-t"],
            capture_output=True,
            timeout=2,
            check=False,
        )
        pids = {int(value) for value in result.stdout.split()}
        return pids.pop() if len(pids) == 1 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


@contextlib.contextmanager
def _lock(path, deadline):
    stream = open(path, "a+b")
    try:
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ManagedError(
                        "manager_busy", "另一个编辑器正在启动或释放本机服务；本次等待已超时，请稍后查询状态。"
                    ) from None
                time.sleep(0.05)
        yield
    finally:
        stream.close()  # OS releases the lock even after a crashed caller.


def _rpc(record, action, session, config, timeout=3):
    result = _http(
        "http://127.0.0.1:" + str(record["control_port"]) + "/manage",
        dict(action=action, session_id=session, instance_id=record["instance_id"], config=config),
        timeout=timeout,
        headers={"Authorization": "Bearer " + record["token"]},
    )
    if not isinstance(result, dict) or result.get("instance_id") != record["instance_id"]:
        raise ValueError("supervisor identity mismatch")
    return result


def _private_state(request, endpoint):
    value = request.get("state_dir")
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ManagedError("state_invalid", "本机管理状态目录必须是宿主提供的可信绝对路径。")
    state = Path(value).resolve()
    state.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(endpoint.encode()).hexdigest()[:24]
    folder = state / key
    folder.mkdir(exist_ok=True)
    os.chmod(folder, 0o700)
    return folder


def _hidden():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}


def _launch_command(config):
    url = urllib.parse.urlsplit(config["endpoint"])
    command = [
        config["python"],
        config["main"],
        "--listen",
        url.hostname,
        "--port",
        str(url.port),
        "--base-directory",
        config["runtime_root"],
        "--disable-auto-launch",
        "--disable-all-custom-nodes",
    ]
    # Read declared argparse options without importing Torch or starting Comfy.
    # Native Hunyuan nodes remain available with all custom nodes disabled.
    cli = Path(config["runtime_root"]) / "ComfyUI-src/comfy/cli_args.py"
    if cli.is_file():
        options = cli.read_text(encoding="utf-8")
        for flag in ("--offline", "--disable-partner-nodes", "--disable-api-nodes"):
            if flag in options:
                command.append(flag)
                break
    return command


def manage(request):
    """Inspect, start, status, stop/release. Return only private machine receipts.

    A caller must not publish this return value in a graph/run/provenance file.
    timeout is the complete operation deadline (1..300 seconds; default 90).
    status joins an existing owned instance when session_id is supplied.
    """
    action = request.get("action", "inspect") if isinstance(request, dict) else "inspect"
    result = dict(
        ok=False,
        action=action,
        state="invalid",
        valid=False,
        connected=False,
        owned=False,
        instance_id="",
        lease_path="",
        queue_busy=None,
        code="",
        message="",
        runtime_root="",
        python="",
        config_path="",
        endpoint="",
        image_model="",
        mesh_model="",
        backend_revision="",
    )
    try:
        if not isinstance(request, dict) or action not in ("inspect", "start", "status", "stop", "release"):
            raise ManagedError("action_invalid", "不支持的本机服务管理操作。")
        config = _inspect(request)
        result.update({k: v for k, v in config.items() if k != "main"})
        if action == "inspect":
            result.update(
                ok=True, state="stopped", message="已识别已有本机 Mesh 运行库与配置；启动后才会核验设备和服务健康。"
            )
            return result
        session = request.get("session_id", "")
        if not isinstance(session, str) or len(session) > 200 or any(ord(c) < 32 for c in session):
            raise ManagedError("session_invalid", "本机编辑器会话标识无效。")
        if action == "start" and not session:
            raise ManagedError("session_missing", "启动本机服务需要编辑器会话租约标识。")
        timeout = request.get("timeout", 90)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 300:
            raise ManagedError("timeout_invalid", "启动等待时间必须在 1 至 300 秒之间。")
        deadline = time.monotonic() + timeout
        folder = _private_state(request, config["endpoint"])
        state_path = folder / "instance.json"
        with _lock(folder / "operation.lock", deadline):
            try:
                record = _read(state_path)
            except (OSError, ValueError):
                record = {}
            if record.get("control_port"):
                try:
                    reply = _rpc(record, action, session, config, timeout=min(3, _remaining(deadline)))
                    if action != "start" or reply.get("state") not in TERMINAL:
                        result.update(reply)
                        return result
                    # Let the terminal controller release its lifetime lock
                    # before replacing it. Its terminal receipt remains on disk.
                    while record.get("supervisor_identity") and record["supervisor_identity"] == _process_identity(
                        record.get("supervisor_pid", 0)
                    ):
                        _remaining(deadline)
                        time.sleep(0.05)
                except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
                    identity = _process_identity(record.get("supervisor_pid", 0))
                    if record.get("state") not in TERMINAL and (
                        not record.get("supervisor_identity") or identity == record["supervisor_identity"]
                    ):
                        result.update(
                            state="unknown",
                            code="ownership_unknown",
                            message="管理进程未回应，无法确认所有权；不会按记录 PID 杀进程。请保留本机日志并重试状态查询。",
                        )
                        return result
            probe = _probe(config, timeout=min(0.7, _remaining(deadline)))
            if probe["connected"]:
                result.update(
                    probe,
                    ok=True,
                    state="external",
                    owned=False,
                    message="已复用正在运行的本机 Mesh 服务；该服务不归当前编辑器所有，停止或退出不会终止它。",
                )
                return result
            if _port_open(config["endpoint"], timeout=min(0.2, _remaining(deadline))):
                result.update(
                    state="failed",
                    code="port_occupied",
                    message="端口已被其他服务占用或模型不匹配；请选择独立回环端口，不会停止端口占用者。",
                )
                return result
            if action != "start":
                result.update(
                    ok=True,
                    state=record.get("state", "stopped") if record.get("state") in TERMINAL else "stopped",
                    message=record.get("message", "本机 Mesh 服务未运行。"),
                    code=record.get("code", ""),
                )
                return result
            instance = secrets.token_hex(24)
            launch = dict(
                config=config,
                session_id=session,
                instance_id=instance,
                token=secrets.token_hex(32),
                folder=str(folder),
                startup_timeout=max(0.1, deadline - time.monotonic()),
            )
            launch_path = folder / ("launch-" + instance + ".json")
            _write(launch_path, launch)
            with open(folder / "supervisor.log", "ab") as log:
                supervisor = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "--supervisor", str(launch_path)],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    **_hidden(),
                )
                _DETACHED_SUPERVISORS[:] = [child for child in _DETACHED_SUPERVISORS if child.poll() is None]
                _DETACHED_SUPERVISORS.append(supervisor)
            supervisor_exit_at = None
            owner_recovered = False
            while time.monotonic() < deadline:
                if supervisor.poll() is not None:
                    if supervisor_exit_at is None:
                        supervisor_exit_at = time.monotonic()
                try:
                    record = _read(state_path)
                    same = record.get("instance_id") == instance
                    recovered_owner = (
                        supervisor_exit_at is not None
                        and record.get("state") not in TERMINAL
                        and record.get("supervisor_identity")
                        and record["supervisor_identity"] == _process_identity(record.get("supervisor_pid", 0))
                    )
                    if same or recovered_owner:
                        reply = _rpc(
                            record, "status" if same else "start", session, config, timeout=min(3, _remaining(deadline))
                        )
                        if recovered_owner:
                            owner_recovered = True
                        if reply.get("state") != "starting":
                            result.update(reply)
                            return result
                except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
                    pass
                if supervisor_exit_at is not None and not owner_recovered and time.monotonic() - supervisor_exit_at > 2:
                    raise ManagedError(
                        "supervisor_failed", "本机管理进程异常退出；请检查本机 supervisor.log 与目录权限。"
                    )
                time.sleep(0.1)
            # Cancel only this exact session/instance. Supervisor owns cleanup.
            try:
                _rpc(record, "release", session, config, timeout=0.05)
            except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
                pass
            result.update(
                state="failed",
                code="startup_timeout",
                instance_id=instance,
                message="本机 Mesh 服务启动超时，已请求释放本次租约；请查看本机日志并查询状态，不会误报为已就绪。",
            )
            return result
    except ManagedError as error:
        result.update(code=error.code, message=str(error))
    except (OSError, ValueError, TypeError, http.client.HTTPException) as error:
        result.update(
            state="failed",
            code="manager_failed",
            diagnostic=type(error).__name__,
            message="本机服务管理未完成；请检查运行库、状态目录权限及本机日志后重试。",
        )
    return result


class _Job:
    """Windows closes exactly this supervisor's children if it dies."""

    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes

        class BASIC(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("minimum", ctypes.c_size_t),
                ("maximum", ctypes.c_size_t),
                ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")
            ]

        class EXTENDED(ctypes.Structure):
            _fields_ = [
                ("basic", BASIC),
                ("io", IO),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = kernel.CreateJobObjectW(None, None)
        limits = EXTENDED()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise OSError("cannot create private child job")
        self.kernel = kernel

    def assign(self, child):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle, int(child._handle)):
            raise OSError("cannot assign private child job")

    def owns(self, pid):
        if not self.handle:
            return False
        from ctypes import wintypes

        handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            member = wintypes.BOOL()
            return bool(self.kernel.IsProcessInJob(handle, self.handle, ctypes.byref(member)) and member.value)
        finally:
            self.kernel.CloseHandle(handle)

    def resume(self, child):
        if self.handle:
            # Popen closes the primary thread handle. Resume this exact suspended
            # process handle after assignment, before its venv launcher can spawn.
            from ctypes import wintypes

            resume = ctypes.WinDLL("ntdll").NtResumeProcess
            resume.argtypes = [wintypes.HANDLE]
            resume.restype = ctypes.c_long
            if resume(int(child._handle)) != 0:
                raise OSError("cannot resume private child")

    def terminate(self):
        if self.handle and not self.kernel.TerminateJobObject(self.handle, 0):
            raise OSError("cannot terminate private child job")
        if self.handle:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                accounting = ctypes.create_string_buffer(48)
                if not self.kernel.QueryInformationJobObject(self.handle, 1, accounting, 48, None):
                    raise OSError("cannot verify private child job exit")
                if struct.unpack_from("I", accounting.raw, 40)[0] == 0:
                    return
                time.sleep(0.02)
            raise OSError("private child job exit timeout")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _parent_death():
    # Called before exec, before the supervisor starts any HTTP worker threads.
    if sys.platform.startswith("linux"):
        ctypes.CDLL(None).prctl(1, 15)
        if os.getppid() == 1:
            os._exit(1)


class _Supervisor:
    def __init__(self, launch):
        self.launch = launch
        self.config = launch["config"]
        self.folder = Path(launch["folder"])
        self.lock = threading.RLock()
        self.leases = {}
        self.child = None
        self.job = _Job()
        self.state = "starting"
        self.code = ""
        self.message = "正在启动本机 Mesh 服务，等待实际健康响应。"
        self.probe = dict(connected=False, queue_busy=None)
        self.started = time.monotonic()
        self.ready_once = False
        self.terminal_at = None
        self.control_port = 0
        self.add_lease(launch["session_id"])

    def add_lease(self, session):
        if not session:
            return ""
        path = self.leases.get(session)
        if not path:
            path = self.folder / ("lease-" + self.launch["instance_id"] + "-" + secrets.token_hex(12))
            self.leases[session] = path
        path.touch()
        return str(path)

    def reap_leases(self):
        for session, path in list(self.leases.items()):
            try:
                expired = time.time() - path.stat().st_mtime > LEASE_SECONDS
            except OSError:
                expired = True
            if expired:
                path.unlink(missing_ok=True)
                del self.leases[session]

    def persist(self):
        _write(
            self.folder / "instance.json",
            dict(
                instance_id=self.launch["instance_id"],
                token=self.launch["token"],
                control_port=self.control_port,
                supervisor_pid=os.getpid(),
                supervisor_identity=_process_identity(os.getpid()),
                child_pid=self.child.pid if self.child else None,
                state=self.state,
                code=self.code,
                message=self.message,
            ),
        )

    def reply(self, session=""):
        return dict(
            ok=self.state in ("running", "shared", "stopped", "waiting_idle"),
            state=self.state,
            code=self.code,
            message=self.message,
            connected=self.probe.get("connected", False),
            queue_busy=self.probe.get("queue_busy"),
            devices=self.probe.get("devices", []),
            owned=self.child is not None and self.child.poll() is None,
            backend_revision=self.probe.get("backend_revision", self.config["backend_revision"]),
            instance_id=self.launch["instance_id"],
            lease_path=str(self.leases.get(session, "")),
            lease_seconds=LEASE_SECONDS,
            lease_count=len(self.leases),
            log_path=str(self.folder / ("comfy-" + self.launch["instance_id"] + ".log")),
        )

    def terminate(self):
        # An exact Popen handle; never os.kill(recorded_pid) / taskkill /interrupt.
        if self.child and self.child.poll() is None:
            if self.job.handle:
                self.job.terminate()
            else:
                self.child.terminate()
            try:
                self.child.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=4)
        self.probe = dict(connected=False, queue_busy=False)

    def owns_listener(self, pid):
        return pid is not None and (self.job.owns(pid) if self.job.handle else pid == self.child.pid)

    def terminal(self, state, code, message):
        self.state, self.code, self.message = state, code, message
        self.probe = dict(connected=False, queue_busy=False if state == "stopped" else None)
        self.terminal_at = time.monotonic()
        for path in self.leases.values():
            path.unlink(missing_ok=True)
        self.leases.clear()
        self.persist()

    def tick(self):
        with self.lock:
            self.reap_leases()
            if self.state in TERMINAL:
                return
            exit_code = self.child.poll()
            if exit_code is not None:
                self.terminal(
                    "failed",
                    "child_exited",
                    f"本机 Mesh 进程已异常退出（退出码 {exit_code}）；请查看本机日志后重新启动。",
                )
                return
            listener = _listener_pid(self.config["endpoint"])
            if listener is not None and not self.owns_listener(listener):
                self.terminate()
                self.terminal(
                    "failed", "port_identity_changed", "监听端口属于其他进程；已停止本次自有子进程，未触碰端口占用者。"
                )
                return
            self.probe = _probe(self.config) if self.owns_listener(listener) else dict(connected=False, queue_busy=None)
            if self.probe.get("connected"):
                self.ready_once = True
                self.state, self.code = "running", ""
                self.message = "本机 Mesh 服务已就绪，设备、配置模型与任务队列已核验。"
            elif not self.ready_once and time.monotonic() - self.started > self.launch["startup_timeout"]:
                self.terminate()
                self.terminal(
                    "failed", "startup_timeout", "本机 Mesh 服务启动超时；请检查日志、设备及模型兼容性后重试。"
                )
                return
            elif self.ready_once:
                self.state = "unknown"
                self.code = self.probe.get("code", "service_unreachable")
                self.message = "本机 Mesh 服务已失去健康响应，不能继续判定为就绪；请检查本机日志与设备，恢复后再查询。"
            if not self.leases:
                if self.state == "starting" and listener is None:
                    self.terminate()
                    self.terminal("stopped", "", "编辑器已释放启动租约，本次自有启动进程已停止。")
                elif self.probe.get("connected") and self.probe.get("queue_busy") is False:
                    # Recheck identity + queue immediately before handle termination.
                    final = _probe(self.config)
                    if (
                        self.owns_listener(_listener_pid(self.config["endpoint"]))
                        and final.get("connected")
                        and final.get("queue_busy") is False
                    ):
                        self.terminate()
                        self.terminal("stopped", "", "最后一个编辑器已释放租约，空闲的自有本机 Mesh 服务已停止。")
                else:
                    self.state = "waiting_idle"
                    self.message = "已释放本会话租约；任务队列忙或状态尚无法核验，将等待空闲后停止自有服务。"
            self.persist()

    def action(self, request):
        with self.lock:
            if request.get("instance_id") != self.launch["instance_id"]:
                raise ValueError("instance mismatch")
            supplied = request.get("config", {})
            if any(
                supplied.get(key) != self.config.get(key)
                for key in ("runtime_root", "config_path", "endpoint", "mesh_model", "image_model")
            ):
                return dict(
                    self.reply(),
                    ok=False,
                    state="unknown",
                    code="instance_config_mismatch",
                    message="此端口已有不同运行库或配置的受管实例；请使用原配置或独立端口，不能覆盖他人实例。",
                )
            session, action = request.get("session_id", ""), request.get("action")
            self.reap_leases()
            if action in ("start", "status") and self.state not in TERMINAL:
                self.add_lease(session)
            elif action in ("stop", "release"):
                path = self.leases.pop(session, None)
                if path:
                    path.unlink(missing_ok=True)
                if self.leases:
                    return dict(
                        self.reply(session),
                        state="shared",
                        message="已释放本会话；其他编辑器仍在使用该服务，保留自有进程。",
                    )
                if self.state not in TERMINAL:
                    self.state = "waiting_idle"
                    self.message = "已释放本会话租约，等待核验队列空闲后停止自有服务。"
            self.persist()
            return self.reply(session)

    def run(self):
        supervisor = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path != "/manage" or not hmac.compare_digest(
                    self.headers.get("Authorization", ""), "Bearer " + supervisor.launch["token"]
                ):
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length < 128 * 1024:
                        raise ValueError("request size")
                    reply = supervisor.action(json.loads(self.rfile.read(length)))
                    payload = json.dumps(reply, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (ValueError, TypeError):
                    self.send_error(400)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server.timeout = 0.15
        self.control_port = server.server_port
        try:
            # Publish the exact controller before launching its child. A second
            # caller can discover ownership even if the original caller dies.
            self.persist()
            command = _launch_command(self.config)
            with open(self.folder / ("comfy-" + self.launch["instance_id"] + ".log"), "ab") as log:
                flags = _hidden()
                if os.name == "nt":
                    flags["creationflags"] |= 0x00000004  # CREATE_SUSPENDED: assign job before launcher children.
                if sys.platform.startswith("linux"):
                    flags["preexec_fn"] = _parent_death
                self.child = subprocess.Popen(
                    command,
                    cwd=str(Path(self.config["main"]).parent),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    **flags,
                )
            self.job.assign(self.child)
            self.job.resume(self.child)
            self.persist()
            last_tick = 0
            while self.terminal_at is None or time.monotonic() - self.terminal_at < 2:
                server.handle_request()
                if time.monotonic() - last_tick > 0.3:
                    self.tick()
                    last_tick = time.monotonic()
        except Exception:
            self.terminate()
            self.terminal(
                "failed", "supervisor_failed", "本机管理进程发生错误，已回收本次自有子进程；请查看本机管理日志。"
            )
            raise
        finally:
            server.server_close()
            self.job.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervisor")
    arguments = parser.parse_args()
    if arguments.supervisor:
        launch_path = Path(arguments.supervisor)
        launch = _read(launch_path)
        launch_path.unlink()
        try:
            # Caller locks may disappear at any instruction after Popen. This
            # separate OS lock lasts for the entire owning supervisor lifetime.
            with _lock(Path(launch["folder"]) / "supervisor.lock", time.monotonic() + 0.5):
                _Supervisor(launch).run()
        except ManagedError:
            pass  # A live winner owns this endpoint; do not spawn or overwrite it.
