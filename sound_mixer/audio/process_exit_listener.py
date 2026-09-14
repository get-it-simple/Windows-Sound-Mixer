import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer, Signal, Slot

if sys.platform == "win32":
    from PySide6.QtCore import QWinEventNotifier
    from shiboken6 import VoidPtr

_SYNCHRONIZE = 0x00100000
_ERROR_INVALID_PARAMETER = 87
_logger = logging.getLogger(__name__)


class ProcessExitListener(QObject):
    process_exited = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._watches = {}
        self._seen: set[int] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.process_exited.emit)
        self._kernel32 = None
        if sys.platform == "win32":
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self._kernel32.OpenProcess.restype = wintypes.HANDLE
            self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._kernel32.CloseHandle.restype = wintypes.BOOL
        if parent is not None:
            parent.destroyed.connect(self.stop)

    def sync(self, pids: set[int]) -> None:
        if self._kernel32 is None:
            return
        pids = {pid for pid in pids if pid > 0}
        for pid in self._watches.keys() - pids:
            self._remove(pid)
        self._seen.intersection_update(pids)
        for pid in pids - self._seen:
            self._seen.add(pid)
            handle = self._kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
            if not handle:
                error = ctypes.get_last_error()
                if error == _ERROR_INVALID_PARAMETER:
                    self._timer.start(0)
                else:
                    _logger.debug("Cannot watch process %s for exit: Windows error %s", pid, error)
                continue
            try:
                notifier = QWinEventNotifier(VoidPtr(handle), self)
                notifier.setProperty("pid", pid)
                notifier.activated.connect(self._on_exit)
            except Exception:
                self._kernel32.CloseHandle(handle)
                raise
            self._watches[pid] = (handle, notifier)

    @Slot()
    def _on_exit(self) -> None:
        self._remove(self.sender().property("pid"))
        self._timer.start(0)

    def _remove(self, pid: int) -> None:
        watch = self._watches.pop(pid, None)
        if watch is not None:
            handle, notifier = watch
            notifier.setEnabled(False)
            notifier.deleteLater()
            self._kernel32.CloseHandle(handle)

    def stop(self) -> None:
        self._timer.stop()
        for pid in list(self._watches):
            self._remove(pid)
        self._seen.clear()
