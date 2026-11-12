"""One bounded newline-delimited JSON request on stdin; native credentials only.

This module is self-contained so the editor can embed its source with ``python -c``.
The parent writes a newline and enforces its own timeout; stdin may remain open.
Never print exceptions: native errors and malformed requests can contain secrets.
"""

import ctypes as c
import json
import re
import sys
import unicodedata

SERVICE = "Godot.ProjectAI.Connection"
MAX_REQUEST_BYTES = 16384
MAX_SECRET_BYTES = 2400
MISSING_MAC = -25300
MISSING_WINDOWS = 1168


def valid_secret(value):
    return (
        isinstance(value, str)
        and 0 < len(value.encode("utf-8")) <= MAX_SECRET_BYTES
        and not any(unicodedata.category(char).startswith("C") for char in value)
    )


def mac_operation(action, account, value):
    security = c.CDLL("/System/Library/Frameworks/Security.framework/Security")
    core = c.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer, uint = c.c_void_p, c.c_uint32

    def bind(library, name, arguments, result=c.c_int32):
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
        return function

    # This helper is a separate process: disable all Keychain UI before access.
    interaction = bind(security, "SecKeychainSetUserInteractionAllowed", [c.c_ubyte])
    if interaction(False) != 0:
        raise RuntimeError("unavailable")
    find = bind(
        security,
        "SecKeychainFindGenericPassword",
        [pointer, uint, c.c_char_p, uint, c.c_char_p, c.POINTER(uint), c.POINTER(pointer), c.POINTER(pointer)],
    )
    release = bind(core, "CFRelease", [pointer], None)
    free = bind(security, "SecKeychainItemFreeContent", [pointer, pointer])
    service, name = SERVICE.encode("utf-8"), account.encode("ascii")
    size, data, item = uint(), pointer(), pointer()
    status = find(None, len(service), service, len(name), name, c.byref(size), c.byref(data), c.byref(item))
    try:
        if status == MISSING_MAC:
            if action != "save":
                return None
            add = bind(
                security,
                "SecKeychainAddGenericPassword",
                [pointer, uint, c.c_char_p, uint, c.c_char_p, uint, c.c_char_p, pointer],
            )
            if add(None, len(service), service, len(name), name, len(value), value, None) != 0:
                raise RuntimeError("unavailable")
            return None
        if status != 0:
            raise RuntimeError("unavailable")
        if action == "load":
            if not data or not 0 < size.value <= MAX_SECRET_BYTES:
                raise RuntimeError("unavailable")
            return c.string_at(data, size.value)
        if not item:
            raise RuntimeError("unavailable")
        if action == "save":
            update = bind(security, "SecKeychainItemModifyAttributesAndData", [pointer, pointer, uint, c.c_char_p])
            status = update(item, None, len(value), value)
        else:
            delete = bind(security, "SecKeychainItemDelete", [pointer])
            status = delete(item)
        if status != 0 and not (action == "delete" and status == MISSING_MAC):
            raise RuntimeError("unavailable")
        return None
    finally:
        if data:
            free(None, data)
        if item:
            release(item)


def windows_operation(action, account, value):
    from ctypes import wintypes as w

    class Credential(c.Structure):
        _fields_ = [
            ("flags", w.DWORD),
            ("type", w.DWORD),
            ("target", w.LPWSTR),
            ("comment", w.LPWSTR),
            ("last_write", w.FILETIME),
            ("size", w.DWORD),
            ("blob", c.c_void_p),
            ("persist", w.DWORD),
            ("count", w.DWORD),
            ("attrs", c.c_void_p),
            ("alias", w.LPWSTR),
            ("username", w.LPWSTR),
        ]

    api = c.WinDLL("Advapi32", use_last_error=True)
    target = SERVICE + "/" + account
    if action == "delete":
        api.CredDeleteW.argtypes, api.CredDeleteW.restype = [w.LPCWSTR, w.DWORD, w.DWORD], w.BOOL
        if not api.CredDeleteW(target, 1, 0) and c.get_last_error() != MISSING_WINDOWS:
            raise RuntimeError("unavailable")
        return None
    if action == "save":
        buffer = c.create_string_buffer(value)
        credential = Credential(
            type=1, target=target, size=len(value), blob=c.cast(buffer, c.c_void_p), persist=2, username=SERVICE
        )
        api.CredWriteW.argtypes, api.CredWriteW.restype = [c.POINTER(Credential), w.DWORD], w.BOOL
        if not api.CredWriteW(c.byref(credential), 0):
            raise RuntimeError("unavailable")
        return None
    found = c.POINTER(Credential)()
    api.CredReadW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(c.POINTER(Credential))]
    api.CredReadW.restype = w.BOOL
    if not api.CredReadW(target, 1, 0, c.byref(found)):
        if c.get_last_error() == MISSING_WINDOWS:
            return None
        raise RuntimeError("unavailable")
    try:
        if not found or not found.contents.blob or not 0 < found.contents.size <= MAX_SECRET_BYTES:
            raise RuntimeError("unavailable")
        return c.string_at(found.contents.blob, found.contents.size)
    finally:
        if found:
            api.CredFree.argtypes, api.CredFree.restype = [c.c_void_p], None
            api.CredFree(found)


def dispatch(request):
    try:
        if not isinstance(request, dict):
            return {"status": "invalid"}
        action, account = request.get("action"), request.get("account")
        if (
            action not in ("load", "save", "delete")
            or not isinstance(account, str)
            or re.fullmatch("[0-9a-f]{64}", account) is None
            or set(request) != ({"action", "account", "secret"} if action == "save" else {"action", "account"})
        ):
            return {"status": "invalid"}
        if action == "save" and not valid_secret(request["secret"]):
            return {"status": "invalid"}
        value = request["secret"].encode("utf-8") if action == "save" else None
    except (TypeError, ValueError, UnicodeError):
        return {"status": "invalid"}
    try:
        if sys.platform == "darwin":
            result = mac_operation(action, account, value)
        elif sys.platform == "win32":
            result = windows_operation(action, account, value)
        else:
            return {"status": "unavailable"}
        if action == "load":
            if result is None:
                return {"status": "missing"}
            secret = result.decode("utf-8")
            if not valid_secret(secret):
                return {"status": "unavailable"}
            return {"status": "loaded", "secret": secret}
        return {"status": "saved" if action == "save" else "deleted"}
    except Exception:
        return {"status": "unavailable"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid")
        result[key] = value
    return result


def main():
    try:
        raw = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            response = {"status": "invalid"}
        else:
            request = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
            response = dispatch(request)
    except Exception:
        response = {"status": "invalid"}
    sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
