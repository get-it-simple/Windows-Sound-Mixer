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

    _user32 = ctypes.WinDLL("user32")
    _WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )

    _user32.EnumWindows.restype = ctypes.wintypes.BOOL
    _user32.EnumWindows.argtypes = [_WNDENUMPROC, ctypes.wintypes.LPARAM]
    _user32.IsWindowVisible.restype = ctypes.wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
    _user32.GetAncestor.restype = ctypes.wintypes.HWND
    _user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]
    _user32.GetDesktopWindow.restype = ctypes.wintypes.HWND
    _user32.GetDesktopWindow.argtypes = []
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.LPWSTR,
        ctypes.c_int,
    ]
    _user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
    _user32.GetWindowThreadProcessId.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
else:
    _GetFileVersionInfoSizeW = _GetFileVersionInfoW = _VerQueryValueW = None
    _user32 = None
    _WNDENUMPROC = None

GA_PARENT = 1


def first_version_string(value: str) -> str:
    return value.split("\x00")[0].strip()


def get_exe_friendly_name(exe_path: str) -> str:
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
                    name = first_version_string(
                        ctypes.wstring_at(p_val.value, n_val.value - 1)
                    )
                    if name:
                        return name
    except Exception:
        pass
    return ""


def is_named_app_window(visible: bool, top_level: bool, length: int) -> bool:
    return bool(visible) and top_level and length > 0


def get_window_titles_by_pid() -> dict[int, str]:
    if _user32 is None:
        return {}
    try:
        titles: dict[int, str] = {}
        desktop = _user32.GetDesktopWindow()

        def _callback(hwnd: int, _: int) -> bool:
            try:
                ancestor = _user32.GetAncestor(hwnd, GA_PARENT)
                top_level = not ancestor or ancestor == desktop
                length = _user32.GetWindowTextLengthW(hwnd)
                if not is_named_app_window(_user32.IsWindowVisible(hwnd), top_level, length):
                    return True
                win_pid = ctypes.wintypes.DWORD()
                _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                pid = win_pid.value
                if not pid:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title and len(title) > len(titles.get(pid, "")):
                    titles[pid] = title
            except Exception:
                pass
            return True

        _user32.EnumWindows(_WNDENUMPROC(_callback), 0)
        return titles
    except Exception:
        pass
    return {}
