import ctypes
import ctypes.wintypes
import struct
import sys

if sys.platform == "win32":
    _ver = ctypes.WinDLL("version.dll")

    _GetFileVersionInfoSizeW = _ver.GetFileVersionInfoSizeW
    _GetFileVersionInfoSizeW.restype = ctypes.wintypes.DWORD
    _GetFileVersionInfoSizeW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]

    _GetFileVersionInfoW = _ver.GetFileVersionInfoW
    _GetFileVersionInfoW.restype = ctypes.wintypes.BOOL
    _GetFileVersionInfoW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.c_void_p,
    ]

    _VerQueryValueW = _ver.VerQueryValueW
    _VerQueryValueW.restype = ctypes.wintypes.BOOL
    _VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        ctypes.wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.wintypes.UINT),
    ]

    _user32 = ctypes.windll.user32
    _WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
else:
    _GetFileVersionInfoSizeW = _GetFileVersionInfoW = _VerQueryValueW = None
    _user32 = None
    _WNDENUMPROC = None


def get_exe_friendly_name(exe_path: str) -> str:
    """Read FileDescription then ProductName from the exe file's version
    resources via version.dll.  Reads from disk only — no process handle."""
    if _GetFileVersionInfoSizeW is None or not exe_path:
        return ""
    try:
        size = _GetFileVersionInfoSizeW(exe_path, None)
        if not size:
            return ""
        data = ctypes.create_string_buffer(size)
        if not _GetFileVersionInfoW(exe_path, 0, size, data):
            return ""
        p_trans = ctypes.c_void_p()
        n_trans = ctypes.wintypes.UINT()
        if (
            not _VerQueryValueW(
                data,
                "\\VarFileInfo\\Translation",
                ctypes.byref(p_trans),
                ctypes.byref(n_trans),
            )
            or not p_trans.value
            or n_trans.value < 4
        ):
            return ""
        for i in range(n_trans.value // 4):
            lang, codepage = struct.unpack_from(
                "<HH", ctypes.string_at(p_trans.value + i * 4, 4)
            )
            for field in ("FileDescription", "ProductName"):
                sub_block = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\{field}"
                p_val = ctypes.c_void_p()
                n_val = ctypes.wintypes.UINT()
                if (
                    _VerQueryValueW(
                        data, sub_block, ctypes.byref(p_val), ctypes.byref(n_val)
                    )
                    and p_val.value
                    and n_val.value > 1
                ):
                    name = ctypes.wstring_at(p_val.value, n_val.value - 1).strip()
                    if name:
                        return name
    except Exception:
        pass
    return ""


def get_process_window_title(pid: int) -> str:
    """Return the title of the longest visible top-level window belonging to
    the given process.  Uses EnumWindows and GetWindowText — the same calls
    the taskbar makes, safe with all anti-cheat systems."""
    if _user32 is None or not pid:
        return ""
    try:
        titles: list[str] = []

        def _callback(hwnd: int, _: int) -> bool:
            try:
                if not _user32.IsWindowVisible(hwnd):
                    return True
                if _user32.GetParent(hwnd):
                    return True
                win_pid = ctypes.wintypes.DWORD()
                _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                if win_pid.value != pid:
                    return True
                length = _user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title:
                    titles.append(title)
            except Exception:
                pass
            return True

        _user32.EnumWindows(_WNDENUMPROC(_callback), 0)
        return max(titles, key=len) if titles else ""
    except Exception:
        pass
    return ""
