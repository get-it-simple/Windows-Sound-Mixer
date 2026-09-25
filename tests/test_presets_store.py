from copy import deepcopy

import pytest

from sound_mixer.settings.migrations import migrate
from sound_mixer.settings.store import SettingsStore


def test_migration_preserves_normal_settings():
    old = {"version": 13, "app_volumes": {"a.exe": {"volume": .4, "muted": True}},
           "hotkeys": [{"action": "toggle_overlay", "combo": "f8", "enabled": True}]}
    before = deepcopy(old)
    result = migrate(old)
    assert old == before
    assert result["version"] == 14
    assert result["app_volumes"] == old["app_volumes"]
    assert result["hotkeys"][0] == old["hotkeys"][0]
    assert result["presets"] == [] and result["active_preset_id"] is None
    assert result["isolation_restore"] == {}
    assert migrate(result) == result


def test_profile_roundtrip_and_independent_normal_state(settings):
    settings.set_app_volume("A.exe", .7)
    preset = settings.create_preset("Game", .5)
    settings.set_active_preset_id(preset["id"])
    settings.set_profile_app_state("A.exe", .2, True)
    settings.set_profile_master_state(.3, True)
    loaded = SettingsStore(settings.path)
    loaded.load()
    assert loaded.get_active_preset_id() == preset["id"]
    assert loaded.get_profile_app_state("a.exe") == (.2, True)
    assert loaded.get_profile_master_state() == (.3, True)
    assert loaded.get_app_volume("a.exe") == .7
    loaded.set_active_preset_id(None)
    assert loaded.get_profile_app_state("a.exe") == (.7, False)
    assert loaded.get_master_volume() == .8


def test_preset_copy_delete_and_normalization(settings):
    preset = settings.create_preset("Game", .5)
    preset["apps"] = {"C:\\Apps\\A.exe": {"volume": 2, "muted": False}}
    preset["isolated_app"] = "C:\\Apps\\A.exe"
    settings.set_presets([preset])
    stored = settings.get_preset(preset["id"])
    assert stored["apps"] == {"c:/apps/a.exe": {"volume": 1, "muted": False}}
    assert stored["isolated_app"] == "c:/apps/a.exe"
    stored["apps"].clear()
    assert settings.get_preset(preset["id"])["apps"]
    settings.set_active_preset_id(preset["id"])
    settings.delete_preset(preset["id"])
    assert settings.get_active_preset_id() is None


def test_whitelist_prevents_auto_add(settings):
    preset = settings.create_preset("Game", .5)
    settings.set_active_preset_id(preset["id"])
    settings.set_whitelist_enabled(True)
    settings.set_profile_app_state("a.exe", .3, False)
    assert settings.get_preset(preset["id"])["apps"] == {}
    assert settings.get_app_volume("a.exe") == .3


def test_preset_limit_rejects_creation_and_bulk_updates_atomically(settings):
    for index in range(9):
        settings.create_preset(f"Preset {index + 1}", .5)
    settings.set_active_preset_id(settings.get_presets()[-1]["id"])
    before = deepcopy(settings.data)
    saved = settings.path.read_bytes()
    with pytest.raises(ValueError, match="9 presets"):
        settings.create_preset("Extra", .5)
    with pytest.raises(ValueError, match="9 presets"):
        settings.set_presets([*settings.get_presets(), {"id": "extra"}])
    assert settings.data == before
    assert settings.path.read_bytes() == saved
    settings.delete_preset(settings.get_presets()[0]["id"])
    assert settings.create_preset("Replacement", .5) in settings.get_presets()
    assert len(settings.get_presets()) == 9


@pytest.mark.parametrize("active_id, expected_id", [("10", None), ("9", "9")])
def test_load_limits_legacy_presets_and_validates_active_id(settings, active_id, expected_id):
    settings.data["presets"] = [{"id": str(index), "name": f"Profile {index}"} for index in range(1, 12)]
    settings.data["active_preset_id"] = active_id
    settings.save()
    settings.load()
    assert [preset["id"] for preset in settings.get_presets()] == [str(index) for index in range(1, 10)]
    assert settings.get_active_preset_id() == expected_id
    settings.save()
    loaded = SettingsStore(settings.path)
    loaded.load()
    assert loaded.get_presets() == settings.get_presets()
    assert loaded.get_active_preset_id() == expected_id
