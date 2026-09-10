import ctypes
from ctypes import wintypes
import sys

from PySide6.QtWidgets import QWidget

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMWCP_ROUND = 2
DWMSBT_NONE = 1
DWMSBT_TRANSIENTWINDOW = 3

WM_DWMCOLORIZATIONCOLORCHANGED = 0x320

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

DEFAULT_ACCENT_COLOR = "#3a96dd"


def get_accent_color() -> str:
    if sys.platform != "win32":
        return DEFAULT_ACCENT_COLOR

    try:
        dwmapi = ctypes.windll.dwmapi
        color = ctypes.c_uint32()
        opaque_blend = ctypes.c_int()
        result = dwmapi.DwmGetColorizationColor(ctypes.byref(color), ctypes.byref(opaque_blend))
        if result != 0:
            return DEFAULT_ACCENT_COLOR

        argb = color.value
        red = (argb >> 16) & 0xFF
        green = (argb >> 8) & 0xFF
        blue = argb & 0xFF
        return f"#{red:02x}{green:02x}{blue:02x}"
    except OSError:
        return DEFAULT_ACCENT_COLOR


def apply_acrylic_effect(window: QWidget, enabled: bool = True) -> None:
    if sys.platform != "win32":
        return

    try:
        dwmapi = ctypes.windll.dwmapi
        hwnd = int(window.winId())
        backdrop = DWMSBT_TRANSIENTWINDOW if enabled else DWMSBT_NONE

        for attribute, value in (
            (DWMWA_USE_IMMERSIVE_DARK_MODE, 1),
            (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND),
            (DWMWA_SYSTEMBACKDROP_TYPE, backdrop),
        ):
            c_value = ctypes.c_int(value)
            dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(c_value), ctypes.sizeof(c_value))
    except OSError:
        pass


def raise_without_activating(window: QWidget) -> None:
    if sys.platform != "win32":
        return

    try:
        set_window_pos = ctypes.windll.user32.SetWindowPos
        set_window_pos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ]
        set_window_pos.restype = wintypes.BOOL
        set_window_pos(int(window.winId()), HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    except OSError:
        pass
