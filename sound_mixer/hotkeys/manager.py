import logging

from PySide6.QtCore import QObject, Signal

from sound_mixer.hotkeys.binding import to_keyboard_combo
from sound_mixer.settings.store import SettingsStore

try:
    import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)


class HotkeyManager(QObject):
    toggle_overlay = Signal()
    volume_up = Signal()
    volume_down = Signal()
    focus_next = Signal()
    focus_prev = Signal()
    mute_toggle = Signal()

    def __init__(self, settings: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._registered_combos: list[str] = []

    def start(self) -> None:
        if keyboard is None:
            logger.warning("keyboard module unavailable; global hotkeys disabled")
            return

        for hotkey in self._settings.get_hotkeys():
            if not hotkey["enabled"] or not hotkey["combo"]:
                continue

            signal = getattr(self, hotkey["action"], None)
            if signal is None:
                logger.warning("Unknown hotkey action: %s", hotkey["action"])
                continue

            try:
                combo = to_keyboard_combo(hotkey["combo"])
            except ValueError:
                logger.warning("Invalid hotkey combo for %s: %s", hotkey["action"], hotkey["combo"])
                continue

            keyboard.add_hotkey(combo, signal.emit)
            self._registered_combos.append(combo)

    def stop(self) -> None:
        if keyboard is None:
            return

        for combo in self._registered_combos:
            keyboard.remove_hotkey(combo)
        self._registered_combos.clear()

    def reload(self) -> None:
        self.stop()
        self.start()
