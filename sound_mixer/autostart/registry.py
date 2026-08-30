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
    def __init__(self, app_name: str = APP_NAME, key_path: str = KEY_PATH, registry=winreg) -> None:
        self._app_name = app_name
        self._key_path = key_path
        self._registry = registry

    def _command(self) -> str:
        portable = " --portable" if "--portable" in sys.argv else ""
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"{portable}'

        pythonw = Path(sys.executable).with_name("pythonw.exe")
        if not pythonw.exists():
            pythonw = Path(sys.executable)
        return f'"{pythonw}" -m sound_mixer{portable}'

    def _require_windows(self) -> None:
        if self._registry is None:
            raise AutostartUnavailableError("Autostart is only available on Windows")

    def is_enabled(self) -> bool:
        self._require_windows()
        registry = self._registry
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, self._key_path, 0, registry.KEY_READ) as key:
                value, _ = registry.QueryValueEx(key, self._app_name)
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise AutostartUnavailableError("Unable to read the autostart registry value") from exc
        return value == self._command()

    def enable(self) -> None:
        self._require_windows()
        registry = self._registry
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, self._key_path, 0, registry.KEY_SET_VALUE) as key:
                registry.SetValueEx(key, self._app_name, 0, registry.REG_SZ, self._command())
        except OSError as exc:
            raise AutostartUnavailableError("Unable to enable autostart") from exc

    def disable(self) -> None:
        self._require_windows()
        registry = self._registry
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, self._key_path, 0, registry.KEY_SET_VALUE) as key:
                registry.DeleteValue(key, self._app_name)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise AutostartUnavailableError("Unable to disable autostart") from exc

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self.is_enabled() == enabled:
            return
        if enabled:
            self.enable()
        else:
            self.disable()
