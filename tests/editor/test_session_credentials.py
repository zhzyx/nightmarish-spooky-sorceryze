"""Credential protocol tests: only mocked native stores, never the user's store."""

import contextlib
import ctypes as c
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

SOURCE = pathlib.Path(__file__).resolve().parents[2] / "customizations/components/godot-host/session_credentials.py"
SPEC = importlib.util.spec_from_file_location("session_credentials", SOURCE)
assert SPEC is not None and SPEC.loader is not None
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)
ACCOUNT = "a" * 64
OTHER_ACCOUNT = "b" * 64
SECRET = "private-test-key-雪"


class FakeFunction:
    def __init__(self, function):
        self.function = function

    def __call__(self, *arguments):
        return self.function(*arguments)


class FakeMac:
    def __init__(self):
        self.store = {}
        self.buffers = []
        self.key = None
        self.interaction_disabled = False
        self.frees = 0
        self.releases = 0
        self.SecKeychainSetUserInteractionAllowed = FakeFunction(self.interaction)
        self.SecKeychainFindGenericPassword = FakeFunction(self.find)
        self.SecKeychainAddGenericPassword = FakeFunction(self.add)
        self.SecKeychainItemModifyAttributesAndData = FakeFunction(self.update)
        self.SecKeychainItemDelete = FakeFunction(self.delete)
        self.SecKeychainItemFreeContent = FakeFunction(self.free)
        self.CFRelease = FakeFunction(self.release)

    def interaction(self, enabled):
        self.interaction_disabled = not enabled
        return 0

    def find(self, keychain, service_size, service, name_size, name, size, data, item):
        assert self.interaction_disabled
        assert service == credentials.SERVICE.encode()
        assert service_size == len(service) and name_size == len(name)
        self.key = service, name
        if self.key not in self.store:
            return credentials.MISSING_MAC
        value = self.store[self.key]
        buffer = c.create_string_buffer(value)
        self.buffers.append(buffer)
        size._obj.value = len(value)
        data._obj.value = c.addressof(buffer)
        item._obj.value = 123
        return 0

    def add(self, keychain, service_size, service, name_size, name, size, value, item):
        self.store[service, name] = value[:size]
        return 0

    def update(self, item, attributes, size, value):
        self.store[self.key] = value[:size]
        return 0

    def delete(self, item):
        del self.store[self.key]
        return 0

    def free(self, attributes, data):
        self.frees += 1
        return 0

    def release(self, item):
        self.releases += 1


class FakeWindows:
    def __init__(self):
        self.store = {}
        self.allocations = []
        self.error = 0
        self.frees = 0
        self.CredWriteW = FakeFunction(self.write)
        self.CredReadW = FakeFunction(self.read)
        self.CredDeleteW = FakeFunction(self.delete)
        self.CredFree = FakeFunction(self.free)

    def write(self, pointer, flags):
        credential = pointer._obj
        assert credential.type == 1 and credential.persist == 2
        assert credential.username == credentials.SERVICE
        self.store[credential.target] = c.string_at(credential.blob, credential.size)
        return 1

    def read(self, target, kind, flags, output):
        assert kind == 1 and flags == 0
        if target not in self.store:
            self.error = credentials.MISSING_WINDOWS
            return 0
        value = self.store[target]
        buffer = c.create_string_buffer(value)
        credential = output._obj._type_(size=len(value), blob=c.cast(buffer, c.c_void_p))
        self.allocations.append((buffer, credential))
        c.cast(output, c.POINTER(type(output._obj)))[0] = c.pointer(credential)
        return 1

    def delete(self, target, kind, flags):
        assert kind == 1 and flags == 0
        if target not in self.store:
            self.error = credentials.MISSING_WINDOWS
            return 0
        del self.store[target]
        return 1

    def free(self, pointer):
        self.frees += 1


class SessionCredentialsTests(unittest.TestCase):
    def setUp(self):
        # No test may accidentally load a real credential library.
        self.block_native = mock.patch.object(credentials.c, "CDLL", side_effect=AssertionError("native access"))
        self.block_native.start()
        self.addCleanup(self.block_native.stop)
        self.block_windows = mock.patch.object(
            credentials.c, "WinDLL", side_effect=AssertionError("native access"), create=True
        )
        self.block_windows.start()
        self.addCleanup(self.block_windows.stop)

    @contextlib.contextmanager
    def native(self, platform):
        store = FakeMac() if platform == "darwin" else FakeWindows()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(credentials.sys, "platform", platform))
            if platform == "darwin":
                stack.enter_context(mock.patch.object(credentials.c, "CDLL", return_value=store))
            else:
                stack.enter_context(mock.patch.object(credentials.c, "WinDLL", return_value=store, create=True))
                stack.enter_context(
                    mock.patch.object(credentials.c, "get_last_error", lambda: store.error, create=True)
                )
            yield store

    def request(self, action, account=ACCOUNT, secret=SECRET):
        request = {"action": action, "account": account}
        if action == "save":
            request["secret"] = secret
        return credentials.dispatch(request)

    def protocol(self, raw):
        output, errors = io.StringIO(), io.StringIO()
        stream = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
        with mock.patch.object(credentials.sys, "stdin", stream), contextlib.redirect_stdout(output):
            with contextlib.redirect_stderr(errors):
                credentials.main()
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        return json.loads(output.getvalue())

    def test_native_roundtrip_update_isolation_delete(self):
        for platform in ("darwin", "win32"):
            with self.subTest(platform=platform), self.native(platform) as store:
                self.assertEqual(self.request("load"), {"status": "missing"})
                self.assertEqual(self.request("save"), {"status": "saved"})
                self.assertEqual(self.request("load"), {"status": "loaded", "secret": SECRET})
                self.assertEqual(self.request("load", OTHER_ACCOUNT), {"status": "missing"})
                self.assertEqual(self.request("save", OTHER_ACCOUNT, "second-key"), {"status": "saved"})
                self.assertEqual(self.request("save", secret="replacement"), {"status": "saved"})
                self.assertEqual(self.request("load"), {"status": "loaded", "secret": "replacement"})
                self.assertEqual(self.request("delete"), {"status": "deleted"})
                self.assertEqual(self.request("delete"), {"status": "deleted"})
                self.assertEqual(self.request("load"), {"status": "missing"})
                self.assertEqual(self.request("load", OTHER_ACCOUNT), {"status": "loaded", "secret": "second-key"})
                self.assertEqual(len(store.store), 1)
                self.assertGreater(store.frees, 0)
                if platform == "darwin":
                    self.assertEqual(store.frees, store.releases)

    def test_invalid_requests_never_access_store(self):
        requests = [None, True, [], 1, "load", {}, {"action": "load", "account": ACCOUNT, "secret": SECRET}]
        requests += [{"action": action, "account": ACCOUNT} for action in (None, [], {}, "other", True)]
        requests += [
            {"action": "load", "account": account}
            for account in (None, 123, [], "a" * 63, "a" * 65, "A" * 64, "g" * 64, ACCOUNT + "\n")
        ]
        requests += [
            {"action": "save", "account": ACCOUNT, "secret": secret}
            for secret in (None, 123, [], {}, True, "", "x" * 2401, "雪" * 801, "x\n", "x\0", "x\x7f", "\ud800")
        ]
        with (
            mock.patch.object(credentials, "mac_operation") as mac,
            mock.patch.object(credentials, "windows_operation") as windows,
        ):
            for request in requests:
                self.assertEqual(credentials.dispatch(request), {"status": "invalid"})
            mac.assert_not_called()
            windows.assert_not_called()

    def test_secret_utf8_boundary(self):
        with self.native("darwin"):
            self.assertEqual(self.request("save", secret="雪" * 800), {"status": "saved"})

    def test_protocol_only_load_returns_secret(self):
        with self.native("darwin"):
            for action, expected in (
                ("save", {"status": "saved"}),
                ("load", {"status": "loaded", "secret": SECRET}),
                ("delete", {"status": "deleted"}),
                ("load", {"status": "missing"}),
            ):
                request = {"action": action, "account": ACCOUNT}
                if action == "save":
                    request["secret"] = SECRET
                self.assertEqual(self.protocol(json.dumps(request).encode() + b"\n"), expected)

    def test_macos_write_and_delete_errors_are_unavailable(self):
        for method, action in (
            ("SecKeychainAddGenericPassword", "save"),
            ("SecKeychainItemModifyAttributesAndData", "save"),
            ("SecKeychainItemDelete", "delete"),
        ):
            with self.subTest(method=method), self.native("darwin") as store:
                if method != "SecKeychainAddGenericPassword":
                    self.assertEqual(self.request("save"), {"status": "saved"})
                setattr(store, method, FakeFunction(lambda *args: -25308))
                self.assertEqual(self.request(action), {"status": "unavailable"})

    def test_malformed_and_oversized_protocol(self):
        for raw in (
            b"",
            b"{",
            b"\xff",
            b"{} {}",
            b"[]",
            b" " * (credentials.MAX_REQUEST_BYTES + 1),
            b'{"action":"load","action":"save","account":"' + ACCOUNT.encode() + b'"}',
            b"[" * 2000,
        ):
            self.assertEqual(self.protocol(raw), {"status": "invalid"})

    def test_failure_never_discloses_secret(self):
        for platform, method in (("darwin", "mac_operation"), ("win32", "windows_operation")):
            with (
                mock.patch.object(credentials.sys, "platform", platform),
                mock.patch.object(credentials, method, side_effect=RuntimeError(SECRET)),
            ):
                for action in ("load", "save", "delete"):
                    raw = {"action": action, "account": ACCOUNT}
                    if action == "save":
                        raw["secret"] = SECRET
                    self.assertEqual(self.protocol(json.dumps(raw).encode()), {"status": "unavailable"})

    def test_native_read_rejects_invalid_stored_data_and_frees(self):
        for platform in ("darwin", "win32"):
            with self.native(platform) as store:
                key = (
                    (credentials.SERVICE.encode(), ACCOUNT.encode())
                    if platform == "darwin"
                    else (credentials.SERVICE + "/" + ACCOUNT)
                )
                for value in (b"", b"\xff", b"private\nkey", b"x" * 2401):
                    store.store[key] = value
                    before = store.frees
                    self.assertEqual(self.request("load"), {"status": "unavailable"})
                    self.assertEqual(store.frees, before + 1)

    def test_macos_interaction_disable_failure_prevents_access(self):
        with self.native("darwin") as store:
            store.SecKeychainSetUserInteractionAllowed = FakeFunction(lambda allowed: -1)
            store.SecKeychainFindGenericPassword = mock.Mock()
            self.assertEqual(self.request("load"), {"status": "unavailable"})
            store.SecKeychainFindGenericPassword.assert_not_called()

    def test_native_permission_errors_are_not_missing(self):
        with self.native("darwin") as store:
            store.SecKeychainFindGenericPassword = FakeFunction(lambda *args: -25308)
            self.assertEqual(self.request("load"), {"status": "unavailable"})
            self.assertEqual(self.request("delete"), {"status": "unavailable"})
        with self.native("win32") as store:
            store.error = 5
            store.CredReadW = FakeFunction(lambda *args: 0)
            store.CredDeleteW = FakeFunction(lambda *args: 0)
            store.CredWriteW = FakeFunction(lambda *args: 0)
            for action in ("load", "save", "delete"):
                self.assertEqual(self.request(action), {"status": "unavailable"})

    def test_unsupported_platform_and_embedded_source(self):
        with mock.patch.object(credentials.sys, "platform", "linux"):
            self.assertEqual(self.request("load"), {"status": "unavailable"})
        # Invalid input exercises the actual embedded entrypoint without native access.
        result = subprocess.run(
            [sys.executable, "-c", SOURCE.read_text()], input=b"{}", capture_output=True, timeout=10, check=True
        )
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout), {"status": "invalid"})

    def test_newline_protocol_does_not_wait_for_stdin_eof(self):
        source = "import sys\nsys.platform = 'unsupported-test-platform'\n" + SOURCE.read_text()
        with subprocess.Popen(
            [sys.executable, "-c", source], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as process:
            process.stdin.write(json.dumps({"action": "load", "account": ACCOUNT}).encode() + b"\n")
            process.stdin.flush()
            try:
                self.assertEqual(process.wait(timeout=3), 0)
                self.assertFalse(process.stdin.closed)
                self.assertEqual(json.loads(process.stdout.read()), {"status": "unavailable"})
                self.assertEqual(process.stderr.read(), b"")
            finally:
                if process.poll() is None:
                    process.kill()


if __name__ == "__main__":
    unittest.main()
