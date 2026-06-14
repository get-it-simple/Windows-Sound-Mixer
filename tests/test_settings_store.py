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
