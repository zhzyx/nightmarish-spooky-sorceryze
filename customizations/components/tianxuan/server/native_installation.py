"""Fail-closed validation of operator-owned ordinary-entry installation manifests.

Paths are absolute host paths. The manifest digest is supplied by the operator,
never by an API request. Validation is repeated before each privileged operation.
This module does not enable an installation until a concrete factory is wired.

Trusted-host boundary: installation provisioning must finish before admission,
with no pre-existing writable mappings. Local NTFS sources are held open without
write/delete sharing until close(); updates require closing and new admission.
Kernel/admin compromise and mutation of this process are outside this boundary.
Linux reuses digests only while both retained and newly opened descriptors are
on a read-only mount (fstatvfs ST_RDONLY). Provisioning must exclude writable
aliases and pre-existing writable mappings; mount administrators are trusted.
This is a host provision contract, not a defense against a privileged remount.
Other filesystems/platforms stream-hash on every verification. No authorization,
manifest, command dictionary or permission decision is cached. These checks do
not make a later path-based subprocess launch atomic with verification.
"""

import asyncio
import hashlib
import json
import os
import stat
import sys
import tempfile
import threading
from pathlib import Path

from native_store import NativeStoreError


def require(ok, message):
    if not ok:
        raise NativeStoreError(message)


def _open_source(path):
    """Open the final component without following links; own every returned handle."""
    require(isinstance(path, str) and Path(path).is_absolute(), "Absolute installation path required")
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        return os.fdopen(fd, "rb")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    # SHARE_READ only. A live cache entry owns this deny-write/delete handle.
    handle = create(path, 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close(handle)
        raise
    return os.fdopen(fd, "rb")


def _identity(stream):
    info = os.fstat(stream.fileno())
    require(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "Installed regular non-reparse file required",
    )
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _retainable(stream, path):
    # The trusted provisioner owns Linux mount topology, including writable
    # aliases. The kernel flag is queried on this fd, never inferred from a path.
    if sys.platform == "linux":
        return bool(os.fstatvfs(stream.fileno()).f_flag & os.ST_RDONLY)
    # Only local NTFS is admitted for persistent deny-write/delete handles.
    # Other hosts/filesystems hash again. No weak timestamp cache fallback.
    if os.name != "nt":
        return False
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    drive_type = kernel.GetDriveTypeW
    drive_type.argtypes = [wintypes.LPCWSTR]
    drive_type.restype = wintypes.UINT
    if drive_type(Path(path).anchor) != 3:
        return False
    volume = kernel.GetVolumeInformationByHandleW
    volume.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    volume.restype = wintypes.BOOL
    name = ctypes.create_unicode_buffer(32)
    return (
        bool(volume(msvcrt.get_osfhandle(stream.fileno()), None, 0, None, None, None, name, len(name)))
        and name.value == "NTFS"
    )


def _digest_stream(stream, *, collect=False):
    digest, chunks = hashlib.sha256(), []
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        if collect:
            chunks.append(chunk)
    return digest.hexdigest(), b"".join(chunks)


def _verified_source(path, digest, cache=None, *, collect=False):
    stream = None
    try:
        stream = _open_source(path)
        before = _identity(stream)
        require(not Path(path).is_symlink(), "Installed regular file required")
        cached = cache.get(path) if cache is not None else None
        if cached is not None:
            held, identity, admitted_digest = cached
            require(
                _retainable(held, path) and _retainable(stream, path), "Installed immutable source protection withdrawn"
            )
            require(before == identity == _identity(held) and digest == admitted_digest, "Installed source changed")
            return b""
        actual, data = _digest_stream(stream, collect=collect)
        require(before == _identity(stream), "Installed source changed during validation")
        # Reopen the name too: a rename of an ancestor must not validate a stale handle.
        with _open_source(path) as current:
            require(before == _identity(current), "Installed source replaced during validation")
        require(actual == digest, "Installed source changed")
        if cache is not None and before[1] and _retainable(stream, path):
            cache[path] = (stream, before, digest)
            stream = None
        return data
    except OSError as exc:
        raise NativeStoreError("Installed source unavailable or concurrently writable") from exc
    finally:
        if stream is not None:
            stream.close()


def pinned_file(path, digest):
    _verified_source(path, digest)
    return Path(path)


class InstallationManifest:
    def __init__(self, path, sha256):
        self.path, self.sha256 = str(path), sha256
        self._lock = threading.RLock()
        self._cache = {}
        self._closed = False
        try:
            self.spec = self.verify()
        except BaseException:
            self.close()
            raise

    def close(self):
        """End admission and release update locks; this instance cannot be reopened."""
        with self._lock:
            self._closed = True
            for stream, _, _ in self._cache.values():
                stream.close()
            self._cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        if hasattr(self, "_lock"):
            self.close()

    def verify(self):
        with self._lock:
            require(not self._closed, "Installation admission closed")
            return self._verify()

    def verify_manifest(self):
        """Validate installed policy identity for a read without admitting executable use."""
        with self._lock:
            require(not self._closed, "Installation admission closed")
            _verified_source(self.path, self.sha256)

    def _verify(self):
        # Parse the exact bytes hashed, and never expose cached trusted dictionaries.
        spec = json.loads(_verified_source(self.path, self.sha256, collect=True).decode("utf-8"))
        require(
            isinstance(spec, dict)
            and set(spec)
            == (
                {"version", "identity", "files", "commands", "principals", "scopes", "complexity", "catalog"}
                | ({"mode"} if spec.get("version") == 2 else set())
            ),
            "Closed installation manifest required",
        )
        require(
            spec["version"] in {1, 2} and isinstance(spec["identity"], str) and spec["identity"],
            "Installation identity required",
        )
        require(isinstance(spec["files"], dict) and spec["files"], "Pinned installation sources required")
        for path, digest in spec["files"].items():
            _verified_source(path, digest, self._cache)
        principals = spec["principals"]
        require(
            isinstance(principals, dict) and set(principals) == {"producer", "checker", "reviewer", "publisher"},
            "Explicit independent principals required",
        )
        require(
            all(isinstance(v, str) and v for v in principals.values()) and len(set(principals.values())) == 4,
            "Independent principal identities required",
        )
        commands = spec["commands"]
        require(
            isinstance(commands, dict)
            and set(commands) == {"planner", "producer", "checker", "reviewer", "dispatcher"},
            "Complete installed command set required",
        )
        for role, command in commands.items():
            expected = {"argv", "env"}
            # A replay guarantee is part of the signed local producer installation.
            # Network role clients cannot vouch for effects on the remote service.
            if role == "producer" and spec.get("mode") == "deterministic-test" and isinstance(command, dict):
                if command.get("restart_checkpoint") == "immutable-inputs":
                    expected.add("restart_checkpoint")
            require(isinstance(command, dict) and set(command) == expected, "Fixed command required")
            argv = command["argv"]
            require(
                isinstance(argv, list) and argv and all(isinstance(v, str) and v for v in argv), "Fixed argv required"
            )
            require(
                argv[0] in spec["files"] and Path(argv[0]).suffix.lower() not in {".bat", ".cmd"},
                "Pinned direct executable required",
            )
            for argument in argv[1:]:
                if Path(argument).is_absolute() and Path(argument).is_file():
                    require(argument in spec["files"], "Command source must be pinned")
            env = command["env"]
            require(
                isinstance(env, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()),
                "Fixed environment required",
            )
            require(
                not any("KEY" in k.upper() or "TOKEN" in k.upper() or "SECRET" in k.upper() for k in env),
                "Installation manifest cannot carry credentials",
            )
        require(isinstance(spec["scopes"], dict) and spec["scopes"], "Installed scopes required")
        for scope in spec["scopes"].values():
            require(isinstance(scope, dict) and set(scope) == {"outputs"}, "Finite installed outputs required")
            outputs = scope["outputs"]
            require(
                isinstance(outputs, list) and outputs and all(isinstance(v, str) for v in outputs),
                "Finite outputs required",
            )
            require(len(outputs) == len(set(outputs)), "Duplicate installed output")
            for output in outputs:
                parts = output.split("/")
                require(
                    len(parts) >= 2
                    and all(p and p not in {".", "..", ".duobao-source.json"} for p in parts)
                    and not parts[0].startswith("requirement-")
                    and not any(c in output for c in "\\:*?[]"),
                    "Portable finite module output required",
                )
        require(isinstance(spec["catalog"], list) and spec["catalog"], "Evaluated capability catalog required")
        require(isinstance(spec["complexity"], dict) and spec["complexity"], "Complexity mapping required")
        for capabilities in spec["complexity"].values():
            require(
                isinstance(capabilities, list) and capabilities and all(isinstance(c, str) and c for c in capabilities),
                "Complexity must map to capabilities",
            )
            require(
                any(set(capabilities) <= set(model.get("capabilities", [])) for model in spec["catalog"]),
                "No installed model covers complexity",
            )
        return spec

    def command(self, role):
        return self.verify()["commands"][role]


def capabilities(installation=None):
    # Manifest validation alone is not a working normal-product installation.
    return {
        "storage": "native",
        "automatic_execution": False,
        "reason": "unconfigured" if installation is None else "factory_not_connected",
    }


class InstalledPlannerRuntime:
    """Concrete subprocess port for native_entry_runtime, using owned-process IO.

    The caller already committed an entry intent. No retry occurs here, including
    timeout, lost stdout, configuration withdrawal or process-tree failure.
    """

    def __init__(self, installation, authorize, role="planner", observe=None):
        from native_check_runner import _process_helper

        self.installation, self.authorize, self.role = installation, authorize, role
        self.helper = _process_helper()
        self.observe = observe

    async def __call__(self, request):
        return await asyncio.to_thread(self.run, request)

    async def recover(self, request):
        return await asyncio.to_thread(self.run, request, recover=True)

    def run(self, request, *, recover=False):
        from native_store import _digest, _json

        require(self.authorize(request) is True, "Planning credential withdrawn")
        command = self.installation.command(self.role)
        argv = list(command["argv"])
        if recover:
            require(
                self.installation.spec.get("mode") in {"production", "local-signed-validation"},
                "Recovery requires admitted production broker",
            )
            argv.append("--recover")
        # JSON output and stderr are separately bounded and fully drained by the
        # same process-tree helper already used by native worker/check execution.
        failures = []
        encoded = _json(request).encode()
        require(len(encoded) <= 100000, "Planning request exceeds installed bound")
        with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            stdin.write(encoded)
            stdin.seek(0)
            code = self.helper.run_owned(
                argv,
                env=command["env"],
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                limit=900000,
                timeout=600,
                active=lambda: self.authorize(request) is True,
                fail=failures.append,
            )
            stdout.seek(0)
            output = stdout.read()
        require(code == 0 and not failures, "Planner process failed/unknown; no automatic replay")
        self.installation.verify()
        require(self.authorize(request) is True, "Planning credential withdrawn while waiting")
        receipt = json.loads(output)
        require(
            set(receipt) - {"model_calls"} == {"input_digest", "source", "proposal", "runtime_state"},
            "Closed runtime receipt required",
        )
        require(
            receipt["input_digest"] == _digest(encoded) and receipt["source"] == request["source"],
            "Planner receipt source/input mismatch",
        )
        if "model_calls" in receipt:
            from native_observations import model_observation, public_model_name

            calls = receipt["model_calls"]
            require(
                self.installation.spec.get("mode") in {"production", "local-signed-validation"}
                and isinstance(calls, list)
                and len(calls) <= 100,
                "Unexpected broker observations",
            )
            for call in calls:
                require(
                    isinstance(call, dict)
                    and set(call) == {"requested_model", "provider_model", "usage"}
                    and isinstance(call["requested_model"], str)
                    and model_observation(call["provider_model"], call["usage"])
                    == {k: call[k] for k in ("provider_model", "usage")},
                    "Invalid broker observation",
                )
            if self.observe is not None:
                self.observe(
                    request,
                    receipt["input_digest"],
                    [{**call, "requested_model": public_model_name(call["requested_model"])} for call in calls],
                )
        return receipt["proposal"]
