import copy
import json
import logging
import os
from pathlib import Path

from sound_mixer.settings.migrations import migrate
from sound_mixer.settings.schema import DEFAULT_SETTINGS, MAX_UI_SCALE, MIN_UI_SCALE
from sound_mixer.volume import clamp_volume

logger = logging.getLogger(__name__)


class SettingsStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = copy.deepcopy(DEFAULT_SETTINGS)

    def load(self) -> dict:
        if not self.path.exists():
            self.data = copy.deepcopy(DEFAULT_SETTINGS)
            self.save()
            return self.data

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read settings file %s, falling back to defaults", self.path)
            self._backup_corrupt_file()
            self.data = copy.deepcopy(DEFAULT_SETTINGS)
            self.save()
            return self.data

        data = migrate(data)
        self.data = _merge_defaults(data, DEFAULT_SETTINGS)
        self._clamp()
        return self.data

    def _backup_corrupt_file(self) -> None:
        try:
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            self.path.replace(backup_path)
        except OSError:
            pass

    def save(self) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp_path, self.path)

    def _clamp(self) -> None:
        self.data["master_volume"] = clamp_volume(self.data["master_volume"])
        self.data["default_app_volume"] = clamp_volume(self.data["default_app_volume"])
        for app in self.data["app_volumes"].values():
            app["volume"] = clamp_volume(app.get("volume", 1.0))

    def get_app_volume(self, exe: str) -> float:
        exe = exe.lower()
        return self.data["app_volumes"].get(exe, {}).get("volume", self.data["default_app_volume"])

    def set_app_volume(self, exe: str, level: float) -> None:
        exe = exe.lower()
        entry = self.data["app_volumes"].setdefault(exe, {"volume": 1.0, "muted": False})
        entry["volume"] = clamp_volume(level)
        self.save()

    def get_app_muted(self, exe: str) -> bool:
        exe = exe.lower()
        return self.data["app_volumes"].get(exe, {}).get("muted", False)

    def set_app_muted(self, exe: str, muted: bool) -> None:
        exe = exe.lower()
        entry = self.data["app_volumes"].setdefault(exe, {"volume": 1.0, "muted": False})
        entry["muted"] = bool(muted)
        self.save()

    def get_master_volume(self) -> float:
        return self.data["master_volume"]

    def set_master_volume(self, level: float) -> None:
        self.data["master_volume"] = clamp_volume(level)
        self.save()

    def get_master_muted(self) -> bool:
        return self.data["master_muted"]

    def set_master_muted(self, muted: bool) -> None:
        self.data["master_muted"] = bool(muted)
        self.save()

    def get_hotkeys(self) -> list[dict]:
        return self.data["hotkeys"]

    def set_hotkey(self, action: str, combo: str, enabled: bool = True) -> None:
        for hotkey in self.data["hotkeys"]:
            if hotkey["action"] == action:
                hotkey["combo"] = combo
                hotkey["enabled"] = enabled
                self.save()
                return
        raise ValueError(f"Unknown hotkey action: {action}")

    def get_autostart_enabled(self) -> bool:
        return self.data["autostart_enabled"]

    def set_autostart_enabled(self, enabled: bool) -> None:
        self.data["autostart_enabled"] = bool(enabled)
        self.save()

    def get_tooltip_delay_ms(self) -> int:
        return self.data["tooltip_delay_ms"]

    def set_tooltip_delay_ms(self, ms: int) -> None:
        self.data["tooltip_delay_ms"] = int(ms)
        self.save()

    def get_overlay_geometry(self) -> dict:
        return self.data["overlay"]

    def set_overlay_geometry(self, x: int, y: int, width: int, height: int) -> None:
        overlay = self.data["overlay"]
        overlay.update({"x": x, "y": y, "width": width, "height": height})
        self.save()

    def get_arrow_step(self) -> float:
        return self.data["volume_step"]["arrow"]

    def set_arrow_step(self, step: float) -> None:
        self.data["volume_step"]["arrow"] = clamp_volume(step)
        self.save()

    def get_scroll_step(self) -> float:
        return self.data["volume_step"]["scroll"]

    def set_scroll_step(self, step: float) -> None:
        self.data["volume_step"]["scroll"] = clamp_volume(step)
        self.save()

    def get_ui_scale(self) -> float:
        return self.data["ui_scale"]

    def set_ui_scale(self, scale: float) -> None:
        self.data["ui_scale"] = max(MIN_UI_SCALE, min(MAX_UI_SCALE, scale))
        self.save()

    def get_default_app_volume(self) -> float:
        return self.data["default_app_volume"]

    def set_default_app_volume(self, level: float) -> None:
        self.data["default_app_volume"] = clamp_volume(level)
        self.save()

    def get_transparency_enabled(self) -> bool:
        return self.data["transparency_enabled"]

    def set_transparency_enabled(self, enabled: bool) -> None:
        self.data["transparency_enabled"] = bool(enabled)
        self.save()

    def get_ignored_apps(self) -> list[str]:
        return self.data["ignored_apps"]

    def is_app_ignored(self, exe: str) -> bool:
        return exe.lower() in self.data["ignored_apps"]

    def add_ignored_app(self, exe: str) -> None:
        exe = exe.lower()
        if exe not in self.data["ignored_apps"]:
            self.data["ignored_apps"].append(exe)
            self.save()

    def remove_ignored_app(self, exe: str) -> None:
        exe = exe.lower()
        if exe in self.data["ignored_apps"]:
            self.data["ignored_apps"].remove(exe)
            self.save()

    def get_language(self) -> str:
        return self.data["language"]

    def set_language(self, language: str) -> None:
        self.data["language"] = language
        self.save()


def _merge_defaults(data: dict, defaults: dict) -> dict:
    result = copy.deepcopy(defaults)
    _deep_update(result, data)
    return result


def _deep_update(base: dict, overrides: dict) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
