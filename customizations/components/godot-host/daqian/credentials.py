"""Private model credentials in the current user's native credential store."""
import ctypes as c
import sys

SERVICE = "Godot.Daqian.ModelAPI"


def mac_secret(account, new_value):
    security = c.CDLL("/System/Library/Frameworks/Security.framework/Security")
    core = c.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer = c.c_void_p
    uint = c.c_uint32
    service = SERVICE.encode()
    name = account.encode()
    size, data, item = uint(), pointer(), pointer()
    search = security.SecKeychainFindGenericPassword
    search.argtypes = [pointer, uint, c.c_char_p, uint, c.c_char_p, c.POINTER(uint), c.POINTER(pointer), c.POINTER(pointer)]
    status = search(None, len(service), service, len(name), name, c.byref(size), c.byref(data), c.byref(item))
    try:
        if status == -25300 and new_value is not None:
            put = security.SecKeychainAddGenericPassword
            put.argtypes = [pointer,uint,c.c_char_p,uint,c.c_char_p,uint,c.c_char_p,pointer]
            status = put(None,len(service),service,len(name),name,len(new_value),new_value,None)
        elif status == 0 and new_value is not None:
            update = security.SecKeychainItemModifyAttributesAndData
            update.argtypes = [pointer,pointer,uint,c.c_char_p]
            status = update(item,None,len(new_value),new_value)
        if status:
            raise ValueError(f"macOS 钥匙串返回 {status}")
        if new_value is None:
            return c.string_at(data,size.value).decode("utf-8")
    finally:
        if data:
            free = security.SecKeychainItemFreeContent
            free.argtypes = [pointer,pointer]
            free(None,data)
        if item:
            core.CFRelease.argtypes = [pointer]
            core.CFRelease(item)


def windows_secret(account, new_value):
    from ctypes import wintypes as w

    class Credential(c.Structure):
        _fields_ = [("flags",w.DWORD),("type",w.DWORD),("target",w.LPWSTR),("comment",w.LPWSTR),
                    ("last_write",w.FILETIME),("size",w.DWORD),("blob",c.c_void_p),("persist",w.DWORD),
                    ("count",w.DWORD),("attrs",c.c_void_p),("alias",w.LPWSTR),("username",w.LPWSTR)]
    api = c.WinDLL("Advapi32",use_last_error=True)
    target = SERVICE + "/" + account
    if new_value is not None:
        value = c.create_string_buffer(new_value)
        cred = Credential(type=1,target=target,size=len(new_value),blob=c.cast(value,c.c_void_p),persist=2,username=SERVICE)
        api.CredWriteW.argtypes = [c.POINTER(Credential),w.DWORD]
        if not api.CredWriteW(c.byref(cred),0):
            raise ValueError(f"Windows 凭据管理器返回 {c.get_last_error()}")
        return
    found = c.POINTER(Credential)()
    api.CredReadW.argtypes = [w.LPCWSTR,w.DWORD,w.DWORD,c.POINTER(c.POINTER(Credential))]
    if not api.CredReadW(target,1,0,c.byref(found)):
        raise ValueError(f"Windows 凭据管理器返回 {c.get_last_error()}")
    try:
        return c.string_at(found.contents.blob,found.contents.size).decode("utf-8")
    finally:
        api.CredFree.argtypes = [c.c_void_p]
        api.CredFree(found)


def secret(account, new_value=None):
    value = None if new_value is None else new_value.encode("utf-8")
    if value is not None and (not value or len(value) > 2400 or any(b < 32 for b in value)):
        raise ValueError("密钥为空、过长或含控制字符")
    if sys.platform == "darwin":
        return mac_secret(account, value)
    if sys.platform == "win32":
        return windows_secret(account, value)
    raise ValueError("此平台尚未绑定系统凭据存储")
