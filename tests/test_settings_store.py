import json

import pytest

from sound_mixer.settings.schema import DEFAULT_SETTINGS
from sound_mixer.settings.store import SettingsStore


def test_load_missing_file_creates_defaults(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)

    data = store.load()

    assert data["version"] == DEFAULT_SETTINGS["version"]
    assert path.exists()
    with path.open(encoding="utf-8") as f:
        assert json.load(f) == data


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.set_app_volume("game.exe", 0.3)
    store.set_hotkey("toggle_overlay", "ctrl+alt+num1")
    store.set_overlay_geometry(10, 20, 300, 400)

    reloaded = SettingsStore(path)
    data = reloaded.load()

    assert data["app_volumes"]["game.exe"]["volume"] == 0.3
    assert data["overlay"]["x"] == 10
    assert data["overlay"]["y"] == 20
    hotkey = next(h for h in data["hotkeys"] if h["action"] == "toggle_overlay")
    assert hotkey["combo"] == "ctrl+alt+num1"


def test_corrupt_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not valid json", encoding="utf-8")

    store = SettingsStore(path)
    data = store.load()

    assert data["version"] == DEFAULT_SETTINGS["version"]

    backup = path.with_suffix(".json.bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "{not valid json"


def test_partial_file_fills_in_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "master_volume": 0.4}), encoding="utf-8")

    store = SettingsStore(path)
    data = store.load()

    assert data["master_volume"] == 0.4
    assert data["tooltip_delay_ms"] == DEFAULT_SETTINGS["tooltip_delay_ms"]
    assert data["hotkeys"] == DEFAULT_SETTINGS["hotkeys"]


def test_unknown_app_volume_defaults(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_app_volume("unknown.exe") == 1.0
    assert store.get_app_muted("unknown.exe") is False


def test_master_volume_clamps(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_master_volume(1.5)
    assert store.get_master_volume() == 1.0

    store.set_master_volume(-0.5)
    assert store.get_master_volume() == 0.0


def test_unknown_hotkey_action_raises(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    with pytest.raises(ValueError):
        store.set_hotkey("does_not_exist", "ctrl+x")


def test_ui_scale_default_and_round_trip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_ui_scale() == DEFAULT_SETTINGS["ui_scale"]

    store.set_ui_scale(1.5)
    assert store.get_ui_scale() == 1.5

    reloaded = SettingsStore(tmp_path / "settings.json")
    reloaded.load()
    assert reloaded.get_ui_scale() == 1.5


def test_ui_scale_clamps_to_valid_range(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_ui_scale(10.0)
    assert store.get_ui_scale() == 3.0

    store.set_ui_scale(0.0)
    assert store.get_ui_scale() == 0.5


def test_partial_file_fills_in_ui_scale(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "master_volume": 0.4}), encoding="utf-8")

    store = SettingsStore(path)
    data = store.load()

    assert data["ui_scale"] == DEFAULT_SETTINGS["ui_scale"]


def test_default_app_volume_default_and_round_trip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_default_app_volume() == DEFAULT_SETTINGS["default_app_volume"]

    store.set_default_app_volume(0.3)
    assert store.get_default_app_volume() == 0.3

    reloaded = SettingsStore(tmp_path / "settings.json")
    reloaded.load()
    assert reloaded.get_default_app_volume() == 0.3


def test_default_app_volume_clamps_to_valid_range(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_default_app_volume(2.0)
    assert store.get_default_app_volume() == 1.0

    store.set_default_app_volume(-1.0)
    assert store.get_default_app_volume() == 0.0


def test_app_volume_falls_back_to_default_app_volume(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_default_app_volume(0.4)

    assert store.get_app_volume("newapp.exe") == 0.4


def test_transparency_enabled_defaults_to_true_and_persists(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_transparency_enabled() is True

    store.set_transparency_enabled(False)

    reloaded = SettingsStore(tmp_path / "settings.json")
    reloaded.load()
    assert reloaded.get_transparency_enabled() is False


def test_ignored_apps_default_empty(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_ignored_apps() == []
    assert store.is_app_ignored("discord.exe") is False


def test_add_ignored_app_persists(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.add_ignored_app("discord.exe")

    assert store.is_app_ignored("discord.exe") is True

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.is_app_ignored("discord.exe") is True


def test_add_ignored_app_normalises_case(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.add_ignored_app("Discord.EXE")

    assert store.is_app_ignored("discord.exe") is True
    assert "discord.exe" in store.get_ignored_apps()


def test_add_ignored_app_idempotent(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.add_ignored_app("discord.exe")
    store.add_ignored_app("discord.exe")

    assert store.get_ignored_apps().count("discord.exe") == 1


def test_remove_ignored_app(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.add_ignored_app("discord.exe")
    store.remove_ignored_app("discord.exe")

    assert store.is_app_ignored("discord.exe") is False

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.is_app_ignored("discord.exe") is False


def test_remove_ignored_app_not_present_is_noop(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.remove_ignored_app("notpresent.exe")

    assert store.get_ignored_apps() == []


def test_language_default_is_system(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_language() == DEFAULT_SETTINGS["language"]
    assert store.get_language() == "system"


def test_language_set_and_get(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.set_language("uk")

    assert store.get_language() == "uk"

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.get_language() == "uk"


def test_language_round_trip_to_system(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.set_language("en")
    store.set_language("system")

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.get_language() == "system"
