import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "SoundMixer"
KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutostartUnavailableError(RuntimeError):
    pass


class AutostartManager:
    def __init__(self, app_name: str = APP_NAME, key_path: str = KEY_PATH) -> None:
        self._app_name = app_name
        self._key_path = key_path

    def _command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        pythonw = Path(sys.executable).with_name("pythonw.exe")
        if not pythonw.exists():
            pythonw = Path(sys.executable)
        return f'"{pythonw}" -m sound_mixer'

    def _require_windows(self) -> None:
        if winreg is None:
            raise AutostartUnavailableError("Autostart is only available on Windows")

    def is_enabled(self) -> bool:
        self._require_windows()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key_path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, self._app_name)
        except FileNotFoundError:
            return False
        return value == self._command()

    def enable(self) -> None:
        self._require_windows()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, self._app_name, 0, winreg.REG_SZ, self._command())

    def disable(self) -> None:
        self._require_windows()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self._app_name)
        except FileNotFoundError:
            pass
