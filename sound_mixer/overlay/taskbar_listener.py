import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_REORDER = 0x8004
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
WINEVENT_SKIPOWNPROCESS = 0x0002
TASKBAR_CHANGED_EVENT = QEvent.Type(QEvent.registerEventType())
_logger = logging.getLogger(__name__)


class TaskbarListener(QObject):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._hooks = []
        self._pending = False
        self._user32 = None
        self._callback = None
        if sys.platform == "win32":
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(
                None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD,
            )
            self._callback = callback_type(self._on_event)
            self._user32.SetWinEventHook.argtypes = [
                wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, callback_type,
                wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            ]
            self._user32.SetWinEventHook.restype = wintypes.HANDLE
            self._user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
            self._user32.UnhookWinEvent.restype = wintypes.BOOL
            self._user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            self._user32.GetClassNameW.restype = ctypes.c_int
        if parent is not None:
            parent.destroyed.connect(self.stop)

    def start(self) -> None:
        if self._user32 is None or self._hooks:
            return
        for event in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_SHOW, EVENT_OBJECT_REORDER, EVENT_OBJECT_LOCATIONCHANGE):
            hook = self._user32.SetWinEventHook(
                event, event, None, self._callback, 0, 0, WINEVENT_SKIPOWNPROCESS,
            )
            if not hook:
                _logger.warning("Cannot watch taskbar events: Windows error %s", ctypes.get_last_error())
                self.stop()
                return
            self._hooks.append(hook)

    def stop(self) -> None:
        for hook in self._hooks:
            self._user32.UnhookWinEvent(hook)
        self._hooks.clear()
        QCoreApplication.removePostedEvents(self, TASKBAR_CHANGED_EVENT)
        self._pending = False

    def _on_event(self, hook, event, hwnd, object_id, child_id, thread_id, timestamp) -> None:
        if not self._hooks or self._pending or not hwnd or object_id != 0 or child_id != 0:
            return
        if event != EVENT_SYSTEM_FOREGROUND:
            class_name = ctypes.create_unicode_buffer(256)
            self._user32.GetClassNameW(hwnd, class_name, len(class_name))
            if class_name.value not in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
                return
        self._pending = True
        QCoreApplication.postEvent(self, QEvent(TASKBAR_CHANGED_EVENT))

    def event(self, event) -> bool:
        if event.type() == TASKBAR_CHANGED_EVENT:
            self._pending = False
            if self._hooks:
                self.changed.emit()
            return True
        return super().event(event)
