import logging

from sound_mixer.app_key import normalize_app_key
from sound_mixer.settings.schema import (
    CURRENT_VERSION,
    DEFAULT_SETTINGS,
    LAYOUT_HORIZONTAL,
    LAYOUT_VERTICAL,
)

logger = logging.getLogger(__name__)


def _migrate_0_to_1(data: dict) -> dict:
    data = dict(data)
    if "volumes" in data and "app_volumes" not in data:
        data["app_volumes"] = data.pop("volumes")
    data.setdefault("master_muted", False)
    data.setdefault("volume_step", {"arrow": 0.05, "scroll": 0.02})
    data["version"] = 1
    return data


def _migrate_1_to_2(data: dict) -> dict:
    data = dict(data)
    data.setdefault("ignored_apps", [])
    data["version"] = 2
    return data


def _migrate_2_to_3(data: dict) -> dict:
    data = dict(data)
    data.setdefault("language", "system")
    data["version"] = 3
    return data


def _migrate_3_to_4(data: dict) -> dict:
    data = dict(data)
    data.setdefault("process_monitor", {"interval_seconds": 5, "apps": []})
    data["version"] = 4
    return data


def _migrate_4_to_5(data: dict) -> dict:
    data = dict(data)
    old = data.pop("process_monitor", None)
    data.setdefault("subprocess_management", old or {"interval_seconds": 5, "apps": []})
    data["version"] = 5
    return data


def _migrate_5_to_6(data: dict) -> dict:
    data = dict(data)
    volumes = data.get("app_volumes")
    if isinstance(volumes, dict):
        data["app_volumes"] = {normalize_app_key(key): value for key, value in volumes.items()}
    ignored = data.get("ignored_apps")
    if isinstance(ignored, list):
        data["ignored_apps"] = [normalize_app_key(key) for key in ignored]
    data["version"] = 6
    return data


def _migrate_6_to_7(data: dict) -> dict:
    data = dict(data)
    overlay = dict(data.get("overlay") or {})
    defaults = DEFAULT_SETTINGS["overlay"]
    geometry = {key: overlay.pop(key, defaults[LAYOUT_HORIZONTAL][key]) for key in ("x", "y", "width", "height")}
    overlay.setdefault(LAYOUT_HORIZONTAL, geometry)
    overlay.setdefault(LAYOUT_VERTICAL, dict(defaults[LAYOUT_VERTICAL]))
    overlay.setdefault("layout_mode", LAYOUT_HORIZONTAL)
    overlay.setdefault("visible_on_start", defaults["visible_on_start"])
    data["overlay"] = overlay
    data["version"] = 7
    return data


def _migrate_7_to_8(data: dict) -> dict:
    data = dict(data)
    data.setdefault("whitelist", {"enabled": False, "apps": []})
    data.setdefault("mini_widget", {"enabled": False, "x": 100, "y": 40})
    hotkeys = list(data.get("hotkeys") or DEFAULT_SETTINGS["hotkeys"])
    if not any(hotkey.get("action") == "toggle_mini_widget" for hotkey in hotkeys):
        hotkeys.insert(1, {"action": "toggle_mini_widget", "combo": "", "enabled": False})
    data["hotkeys"] = hotkeys
    data["version"] = 8
    return data


MIGRATIONS = {
    0: _migrate_0_to_1,
    1: _migrate_1_to_2,
    2: _migrate_2_to_3,
    3: _migrate_3_to_4,
    4: _migrate_4_to_5,
    5: _migrate_5_to_6,
    6: _migrate_6_to_7,
    7: _migrate_7_to_8,
}


def migrate(data: dict) -> dict:
    version = data.get("version", 0)

    if version > CURRENT_VERSION:
        logger.warning(
            "Settings file version %s is newer than supported version %s; loading without changes",
            version,
            CURRENT_VERSION,
        )
        return data

    while version < CURRENT_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            break
        data = migration(data)
        version = data.get("version", version + 1)

    return data
