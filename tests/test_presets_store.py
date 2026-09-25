from copy import deepcopy

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
