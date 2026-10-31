import ctypes
from ctypes import wintypes
import sys


def application_identities(owners) -> dict[str, set[str]]:
    identities = {owner.key: set() for owner in owners}
    if sys.platform != "win32":
        return identities
    from comtypes import GUID

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetApplicationUserModelId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
    by_pid = {pid: owner.key for owner in owners for pid in owner.pids}
    for pid, key in by_pid.items():
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            continue
        try:
            size = wintypes.UINT()
            if kernel.GetApplicationUserModelId(handle, ctypes.byref(size), None) == 122:
                value = ctypes.create_unicode_buffer(size.value)
                if kernel.GetApplicationUserModelId(handle, ctypes.byref(size), value) == 0:
                    identities[key].add(value.value.casefold())
        finally:
            kernel.CloseHandle(handle)

    class PropertyKey(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

    class PropVariant(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3), ("data", ctypes.c_void_p * 2)]

    user = ctypes.WinDLL("user32")
    shell = ctypes.WinDLL("shell32")
    ole = ctypes.WinDLL("ole32")
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    shell.SHGetPropertyStoreForWindow.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetPropertyStoreForWindow.restype = ctypes.c_long
    ole.PropVariantClear.argtypes = [ctypes.POINTER(PropVariant)]
    iid = GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
    property_key = PropertyKey(GUID("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"), 5)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd, unused):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        key = by_pid.get(pid.value)
        if key is None:
            return True
        store = ctypes.c_void_p()
        if shell.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(iid), ctypes.byref(store)) != 0 or not store:
            return True
        table = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        value = PropVariant()
        try:
            get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PropertyKey), ctypes.POINTER(PropVariant))(table[5])
            if get_value(store, ctypes.byref(property_key), ctypes.byref(value)) == 0 and value.vt == 31 and value.data[0]:
                identities[key].add(ctypes.wstring_at(value.data[0]).casefold())
        finally:
            ole.PropVariantClear(ctypes.byref(value))
            ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(table[2])(store)
        return True

    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows(callback_type(visit), 0)
    return identities
