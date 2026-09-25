import logging
import sys
from functools import partial
from typing import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

from sound_mixer.hotkeys.binding import MOD_NOREPEAT, combo_to_hotkey
from sound_mixer.settings.store import SettingsStore

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312

if sys.platform == "win32":
    import ctypes

    user32 = ctypes.windll.user32
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
else:
    user32 = None


class HotkeyManager(QObject, QAbstractNativeEventFilter):
    preset_toggled = Signal(str)
    default_mode = Signal()
    toggle_overlay = Signal()
    toggle_mini_widget = Signal()
    mini_focus_next = Signal()
    mini_focus_prev = Signal()
    mini_volume_up = Signal()
    mini_volume_down = Signal()
    toggle_mini_master = Signal()
    volume_up = Signal()
    volume_down = Signal()
    focus_next = Signal()
    focus_prev = Signal()
    mute_toggle = Signal()

    def __init__(self, settings: SettingsStore, parent=None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._settings = settings
        self._hotkey_ids: dict[int, Callable] = {}
        self._next_id = 1
        self._filter_installed = False

    def start(self) -> None:
        if user32 is None:
            logger.warning("Global hotkeys require Windows; hotkeys disabled")
            return

        if self._hotkey_ids:
            self.stop()
        used = set()
        for hotkey in self._settings.get_all_hotkeys():
            if not hotkey["enabled"] or not hotkey["combo"]:
                continue

            action = hotkey["action"]
            is_preset = action.startswith("preset:")
            signal = getattr(self, action, None)
            if not is_preset and signal is None:
                logger.warning("Unknown hotkey action: %s", hotkey["action"])
                continue

            callback = partial(self.preset_toggled.emit, action.removeprefix("preset:")) if is_preset else signal.emit

            try:
                modifiers, vk = combo_to_hotkey(hotkey["combo"])
            except ValueError:
                logger.warning("Invalid hotkey combo for %s: %s", hotkey["action"], hotkey["combo"])
                continue

            if (modifiers, vk) in used:
                logger.warning("Conflicting hotkey for %s: %s", action, hotkey["combo"])
                continue
            used.add((modifiers, vk))
            if is_preset or action == "default_mode":
                modifiers |= MOD_NOREPEAT

            hotkey_id = self._next_id
            self._next_id += 1
            if user32.RegisterHotKey(None, hotkey_id, modifiers, vk):
                self._hotkey_ids[hotkey_id] = callback
            else:
                logger.warning("Failed to register hotkey for %s: %s", hotkey["action"], hotkey["combo"])

        if self._hotkey_ids and not self._filter_installed:
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self)
                self._filter_installed = True

    def stop(self) -> None:
        if user32 is None:
            return

        for hotkey_id in self._hotkey_ids:
            user32.UnregisterHotKey(None, hotkey_id)
        self._hotkey_ids.clear()

        if self._filter_installed:
            app = QApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self)
            self._filter_installed = False

    def reload(self) -> None:
        self.stop()
        self.start()

    def _handle_hotkey(self, hotkey_id: int) -> None:
        callback = self._hotkey_ids.get(hotkey_id)
        if callback is not None:
            callback()

    def nativeEventFilter(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self._handle_hotkey(msg.wParam)
            return True, 0

        return False, 0
