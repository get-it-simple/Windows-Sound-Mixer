import os
from typing import Callable, Iterable, Optional

import psutil
from PySide6.QtCore import QObject, QTimer

from sound_mixer.settings.store import SettingsStore

MIN_INTERVAL_MS = 1000


def _basename_key(path: str) -> str:
    return os.path.normcase(os.path.basename(path.strip()))


def is_any_managed_app_running(paths: Iterable[str], process_iter: Callable = psutil.process_iter) -> bool:
    targets = {_basename_key(path) for path in paths if path}
    if not targets:
        return False

    for process in process_iter(["name"]):
        try:
            name = process.info["name"]
        except (KeyError, TypeError):
            try:
                name = process.name()
            except psutil.Error:
                continue
        except psutil.Error:
            continue
        if name and os.path.normcase(name) in targets:
            return True
    return False


class SubprocessManager(QObject):
    def __init__(self, settings: SettingsStore, on_tick: Callable[[], None], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._on_tick = on_tick
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)

    def has_enabled_apps(self) -> bool:
        return bool(self._enabled_paths())

    def is_active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        self._active = active
        self.sync()

    def sync(self) -> None:
        if not self._active or not self.has_enabled_apps():
            self._timer.stop()
            return
        interval_ms = max(MIN_INTERVAL_MS, self._settings.get_subprocess_management_interval_seconds() * 1000)
        self._timer.start(interval_ms)

    def stop(self) -> None:
        self._timer.stop()

    def _enabled_paths(self) -> list[str]:
        return [app["path"] for app in self._settings.get_managed_apps() if app.get("enabled")]

    def _check(self) -> None:
        if is_any_managed_app_running(self._enabled_paths()):
            self._on_tick()
