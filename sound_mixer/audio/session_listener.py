import ctypes
import ctypes.wintypes
import threading

from comtypes import COMObject
from comtypes.hresult import S_OK
from pycaw.pycaw import AudioUtilities, IAudioSessionManager2, IAudioSessionNotification
from PySide6.QtCore import QObject, Signal

_PM_REMOVE = 0x0001
_WM_QUIT = 0x0012
_COINIT_APARTMENTTHREADED = 0x2


class _Notifier(QObject):
    session_created = Signal()


class _NotificationHandler(COMObject):
    _com_interfaces_ = [IAudioSessionNotification]

    def __init__(self, notifier: _Notifier) -> None:
        super().__init__()
        self._notifier = notifier

    def OnSessionCreated(self, new_session) -> int:
        self._notifier.session_created.emit()
        return S_OK


class AudioSessionListener:
    def __init__(self, on_session_created) -> None:
        self._notifier = _Notifier()
        self._notifier.session_created.connect(on_session_created)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="AudioSessionListener")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        ctypes.windll.ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
        try:
            mgr = AudioUtilities.GetAudioSessionManager()
            if mgr is None:
                return
            mgr2 = mgr.QueryInterface(IAudioSessionManager2)
            handler = _NotificationHandler(self._notifier)
            mgr2.RegisterSessionNotification(handler)
            try:
                self._pump(mgr2, handler)
            finally:
                mgr2.UnregisterSessionNotification(handler)
        except Exception:
            pass
        finally:
            ctypes.windll.ole32.CoUninitialize()

    def _pump(self, mgr2, handler) -> None:
        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, _PM_REMOVE) != 0:
                if msg.message == _WM_QUIT:
                    return
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            self._stop_event.wait(timeout=0.1)
