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
    assert data["overlay"]["horizontal"]["x"] == 10
    assert data["overlay"]["horizontal"]["y"] == 20
    hotkey = next(h for h in data["hotkeys"] if h["action"] == "toggle_overlay")
    assert hotkey["combo"] == "ctrl+alt+num1"


def read_settings_file(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def test_setters_save_immediately_without_scheduler(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.set_app_volume("game.exe", 0.3)

    assert read_settings_file(path)["app_volumes"]["game.exe"]["volume"] == 0.3


def test_deferred_setter_does_not_write_until_flush(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()
    store.set_app_volume("game.exe", 0.3)

    scheduled = []
    store.set_save_scheduler(lambda: scheduled.append(True))

    store.set_app_volume("game.exe", 0.9)

    assert read_settings_file(path)["app_volumes"]["game.exe"]["volume"] == 0.3
    assert store.get_app_volume("game.exe") == 0.9
    assert scheduled == [True]

    store.flush()

    assert read_settings_file(path)["app_volumes"]["game.exe"]["volume"] == 0.9


def test_multiple_deferred_changes_coalesce_into_one_flush(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()
    store.set_save_scheduler(lambda: None)

    store.set_app_volume("game.exe", 0.1)
    store.set_app_volume("game.exe", 0.2)
    store.set_master_volume(0.6)
    store.set_app_muted("game.exe", True)

    store.flush()

    data = read_settings_file(path)
    assert data["app_volumes"]["game.exe"]["volume"] == 0.2
    assert data["app_volumes"]["game.exe"]["muted"] is True
    assert data["master_volume"] == 0.6


def test_immediate_setter_persists_pending_deferred_changes(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()
    store.set_save_scheduler(lambda: None)

    store.set_app_volume("game.exe", 0.4)
    store.set_language("en")

    data = read_settings_file(path)
    assert data["app_volumes"]["game.exe"]["volume"] == 0.4
    assert data["language"] == "en"

    mtime_before = path.stat().st_mtime_ns
    store.flush()
    assert path.stat().st_mtime_ns == mtime_before


def test_flush_without_changes_does_not_write(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    mtime_before = path.stat().st_mtime_ns
    store.flush()

    assert path.stat().st_mtime_ns == mtime_before


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
    assert store.is_app_ignored("nimbus.exe") is False


def test_add_ignored_app_persists(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.add_ignored_app("nimbus.exe")

    assert store.is_app_ignored("nimbus.exe") is True

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.is_app_ignored("nimbus.exe") is True


def test_add_ignored_app_normalises_case(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.add_ignored_app("Nimbus.EXE")

    assert store.is_app_ignored("nimbus.exe") is True
    assert "nimbus.exe" in store.get_ignored_apps()


def test_add_ignored_app_idempotent(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.add_ignored_app("nimbus.exe")
    store.add_ignored_app("nimbus.exe")

    assert store.get_ignored_apps().count("nimbus.exe") == 1


def test_remove_ignored_app(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.add_ignored_app("nimbus.exe")
    store.remove_ignored_app("nimbus.exe")

    assert store.is_app_ignored("nimbus.exe") is False

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.is_app_ignored("nimbus.exe") is False


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


def test_subprocess_management_interval_default_and_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    assert store.get_subprocess_management_interval_seconds() == 5

    store.set_subprocess_management_interval_seconds(30)
    assert store.get_subprocess_management_interval_seconds() == 30

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.get_subprocess_management_interval_seconds() == 30


def test_subprocess_management_interval_clamps_to_minimum(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_subprocess_management_interval_seconds(0)
    assert store.get_subprocess_management_interval_seconds() == 1

    store.set_subprocess_management_interval_seconds(-5)
    assert store.get_subprocess_management_interval_seconds() == 1


def test_managed_apps_default_empty(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_managed_apps() == []


def test_set_managed_apps_persists_and_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    executable = tmp_path / "Sandbox.exe"
    executable.write_bytes(b"MZ")
    canonical = str(executable.resolve())
    store = SettingsStore(path)
    store.load()

    store.set_managed_apps([{"path": str(executable), "enabled": True}])

    assert store.get_managed_apps() == [{"path": canonical, "enabled": True}]

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.get_managed_apps() == [{"path": canonical, "enabled": True}]


def test_set_managed_apps_dedupes_case_insensitively(tmp_path):
    executable = tmp_path / "Sandbox.exe"
    executable.write_bytes(b"MZ")
    canonical = str(executable.resolve())
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_managed_apps(
        [
            {"path": str(executable), "enabled": True},
            {"path": str(executable).replace("\\", "/"), "enabled": False},
        ]
    )

    assert store.get_managed_apps() == [{"path": canonical, "enabled": True}]


def test_get_managed_apps_returns_a_copy(tmp_path):
    executable = tmp_path / "game.exe"
    executable.write_bytes(b"MZ")
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_managed_apps([{"path": str(executable), "enabled": True}])

    apps = store.get_managed_apps()
    apps[0]["enabled"] = False

    assert store.get_managed_apps()[0]["enabled"] is True


def test_app_volume_stored_under_full_path_key(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_app_volume("D:/Games/MyGame/Game.exe", 0.35)

    assert store.data["app_volumes"]["d:/games/mygame/game.exe"]["volume"] == pytest.approx(0.35)
    assert store.get_app_volume("d:/games/mygame/game.exe") == pytest.approx(0.35)


def test_same_file_name_in_different_folders_keeps_separate_volumes(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_app_volume("G:/Games/VOIDRUNNER/Game.exe", 0.2)
    store.set_app_volume("D:/Downloads/Starfall Demo/game.exe", 0.9)

    assert store.get_app_volume("G:/Games/VOIDRUNNER/Game.exe") == pytest.approx(0.2)
    assert store.get_app_volume("D:/Downloads/Starfall Demo/game.exe") == pytest.approx(0.9)


def test_legacy_file_name_key_still_applies_to_a_path_key(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["app_volumes"]["nimbus.exe"] = {"volume": 0.42, "muted": True}

    assert store.get_app_volume("C:/Users/me/AppData/Local/Nimbus/Nimbus.exe") == pytest.approx(0.42)
    assert store.get_app_muted("C:/Users/me/AppData/Local/Nimbus/Nimbus.exe") is True


def test_path_key_takes_precedence_over_legacy_file_name_key(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["app_volumes"]["game.exe"] = {"volume": 0.42, "muted": False}
    store.set_app_volume("D:/Games/MyGame/Game.exe", 0.75)

    assert store.get_app_volume("D:/Games/MyGame/Game.exe") == pytest.approx(0.75)
    assert store.get_app_volume("G:/Other/Game.exe") == pytest.approx(0.42)


def test_legacy_ignored_file_name_hides_a_path_key_app(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["ignored_apps"].append("nimbus.exe")

    assert store.is_app_ignored("C:/Programs/Nimbus/Nimbus.exe") is True


def test_unignoring_removes_the_legacy_file_name_entry(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["ignored_apps"].append("nimbus.exe")

    store.remove_ignored_app("C:/Programs/Nimbus/Nimbus.exe")

    assert store.is_app_ignored("C:/Programs/Nimbus/Nimbus.exe") is False
    assert store.get_ignored_apps() == []


def test_ignoring_one_install_does_not_ignore_another_with_the_same_name(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.add_ignored_app("G:/Games/VOIDRUNNER/Game.exe")

    assert store.is_app_ignored("G:/Games/VOIDRUNNER/Game.exe") is True
    assert store.is_app_ignored("D:/Downloads/Starfall Demo/game.exe") is False


def test_layout_mode_defaults_to_horizontal(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_layout_mode() == "horizontal"


def test_layout_mode_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.set_layout_mode("vertical")

    assert SettingsStore(path).load()["overlay"]["layout_mode"] == "vertical"


def test_unknown_layout_mode_falls_back_to_horizontal(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_layout_mode("diagonal")

    assert store.get_layout_mode() == "horizontal"


def test_hand_edited_unknown_layout_mode_is_read_as_horizontal(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["overlay"]["layout_mode"] = "diagonal"

    assert store.get_layout_mode() == "horizontal"


def test_overlay_geometry_is_stored_per_layout_mode(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_overlay_geometry(10, 20, 300, 400)
    store.set_layout_mode("vertical")
    store.set_overlay_geometry(50, 60, 500, 600)

    assert store.get_overlay_geometry() == {"x": 50, "y": 60, "width": 500, "height": 600}
    assert store.get_overlay_geometry("horizontal") == {"x": 10, "y": 20, "width": 300, "height": 400}


def test_visible_on_start_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    assert store.get_visible_on_start() is False
    store.set_visible_on_start(True)

    assert SettingsStore(path).load()["overlay"]["visible_on_start"] is True


def test_setting_geometry_keeps_visible_on_start(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_visible_on_start(True)

    store.set_overlay_geometry(1, 2, 300, 400)

    assert store.get_visible_on_start() is True


def test_whitelist_defaults_disabled_and_allows_every_app(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    assert store.get_whitelist_enabled() is False
    assert store.get_whitelist_apps() == []
    assert store.is_app_whitelisted("C:/Apps/Aurora.exe") is True


def test_whitelist_matches_normalized_path_and_bare_name_fallback(tmp_path):
    executable = tmp_path / "Aurora.exe"
    executable.write_bytes(b"MZ")
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_whitelist_apps([{"path": str(executable), "enabled": True}])
    store.set_whitelist_enabled(True)

    assert store.is_app_whitelisted(str(executable).lower()) is True
    assert store.is_app_whitelisted("AURORA.EXE") is True
    assert store.is_app_whitelisted("C:/Other/Aurora.exe") is False
    assert store.is_app_whitelisted("lumen.exe") is False


def test_whitelist_ignores_disabled_apps_and_dedupes_separators(tmp_path):
    executable = tmp_path / "Aurora.exe"
    executable.write_bytes(b"MZ")
    canonical = str(executable.resolve())
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_whitelist_apps(
        [
            {"path": str(executable), "enabled": False},
            {"path": str(executable).replace("\\", "/"), "enabled": True},
        ]
    )
    store.set_whitelist_enabled(True)

    assert store.get_whitelist_apps() == [{"path": canonical, "enabled": False}]
    assert store.is_app_whitelisted("aurora.exe") is False


def test_load_filters_invalid_managed_and_whitelist_paths_before_use(tmp_path):
    executable = tmp_path / "Valid.exe"
    executable.write_bytes(b"MZ")
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "version": DEFAULT_SETTINGS["version"],
                "subprocess_management": {
                    "interval_seconds": 5,
                    "apps": [
                        {"path": str(executable), "enabled": True},
                        {"path": r"\\server\share\Remote.exe", "enabled": True},
                    ],
                },
                "whitelist": {
                    "enabled": True,
                    "apps": [{"path": "relative.exe", "enabled": True}],
                },
            }
        ),
        encoding="utf-8",
    )

    store = SettingsStore(path)
    store.load()

    assert store.get_managed_apps() == [{"path": str(executable.resolve()), "enabled": True}]
    assert store.get_whitelist_apps() == []


def test_mini_widget_state_and_position_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    store.set_mini_widget_enabled(True)
    store.set_mini_widget_position(321, 123)
    store.flush()

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.get_mini_widget_enabled() is True
    assert reloaded.get_mini_widget_position() == {"x": 321, "y": 123}


def test_mini_widget_scale_default_and_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    assert store.get_mini_widget_scale() == DEFAULT_SETTINGS["mini_widget"]["scale"]
    store.set_mini_widget_scale(1.6)

    reloaded = SettingsStore(path)
    reloaded.load()
    assert reloaded.get_mini_widget_scale() == 1.6


def test_mini_widget_scale_clamps_to_valid_range(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    store.set_mini_widget_scale(10.0)
    assert store.get_mini_widget_scale() == 3.0

    store.set_mini_widget_scale(0.0)
    assert store.get_mini_widget_scale() == 0.5
