import logging

from sound_mixer.settings.migrations import migrate
from sound_mixer.settings.schema import CURRENT_VERSION, DEFAULT_SETTINGS


def test_migrates_legacy_v0_document():
    legacy = {
        "volumes": {"aurora.exe": {"volume": 0.5, "muted": False}},
        "master_volume": 0.7,
    }

    migrated = migrate(legacy)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["app_volumes"] == {"aurora.exe": {"volume": 0.5, "muted": False}}
    assert "volumes" not in migrated
    assert migrated["master_muted"] is False
    assert "volume_step" in migrated
    assert migrated["master_volume"] == 0.7


def test_future_version_passes_through_with_warning(caplog):
    future = {"version": CURRENT_VERSION + 1, "extra_field": "value"}

    with caplog.at_level(logging.WARNING):
        migrated = migrate(future)

    assert migrated["version"] == CURRENT_VERSION + 1
    assert migrated["extra_field"] == "value"
    assert any("version" in record.getMessage().lower() for record in caplog.records)


def test_current_version_unchanged():
    current = {"version": CURRENT_VERSION, "master_volume": 0.6}

    migrated = migrate(current)

    assert migrated == current


def test_migrates_v1_to_v2_adds_ignored_apps():
    v1 = {
        "version": 1,
        "master_volume": 0.5,
        "app_volumes": {"aurora.exe": {"volume": 0.8, "muted": False}},
    }

    migrated = migrate(v1)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["ignored_apps"] == []
    assert migrated["app_volumes"] == {"aurora.exe": {"volume": 0.8, "muted": False}}


def test_migrates_v1_preserves_existing_ignored_apps():
    v1 = {
        "version": 1,
        "ignored_apps": ["nimbus.exe"],
    }

    migrated = migrate(v1)

    assert migrated["ignored_apps"] == ["nimbus.exe"]


def test_migrates_v2_to_v3_adds_language():
    v2 = {
        "version": 2,
        "master_volume": 0.5,
        "ignored_apps": [],
    }

    migrated = migrate(v2)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["language"] == "system"


def test_migrates_v2_preserves_existing_language():
    v2 = {
        "version": 2,
        "language": "uk",
    }

    migrated = migrate(v2)

    assert migrated["language"] == "uk"


def test_migrates_v3_to_current_adds_subprocess_management():
    v3 = {
        "version": 3,
        "master_volume": 0.5,
    }

    migrated = migrate(v3)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["subprocess_management"] == {"interval_seconds": 5, "apps": []}
    assert "process_monitor" not in migrated


def test_migrates_v3_preserves_existing_process_monitor_data_through_rename():
    v3 = {
        "version": 3,
        "process_monitor": {"interval_seconds": 10, "apps": [{"path": "C:/sandbox.exe", "enabled": True}]},
    }

    migrated = migrate(v3)

    assert migrated["subprocess_management"] == {
        "interval_seconds": 10,
        "apps": [{"path": "C:/sandbox.exe", "enabled": True}],
    }
    assert "process_monitor" not in migrated


def test_migrates_v4_to_v5_renames_process_monitor_to_subprocess_management():
    v4 = {
        "version": 4,
        "process_monitor": {"interval_seconds": 15, "apps": [{"path": "C:/sandbox.exe", "enabled": False}]},
    }

    migrated = migrate(v4)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["subprocess_management"] == {
        "interval_seconds": 15,
        "apps": [{"path": "C:/sandbox.exe", "enabled": False}],
    }
    assert "process_monitor" not in migrated


def test_migrates_v4_to_v5_defaults_when_process_monitor_missing():
    v4 = {
        "version": 4,
        "master_volume": 0.5,
    }

    migrated = migrate(v4)

    assert migrated["subprocess_management"] == {"interval_seconds": 5, "apps": []}


def test_migrates_v5_to_v6_normalises_app_keys():
    v5 = {
        "version": 5,
        "app_volumes": {"Aurora.exe": {"volume": 0.5, "muted": False}},
        "ignored_apps": ["Nimbus.exe"],
    }

    migrated = migrate(v5)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["app_volumes"] == {"aurora.exe": {"volume": 0.5, "muted": False}}
    assert migrated["ignored_apps"] == ["nimbus.exe"]


def test_migrates_v5_keeps_file_name_keys_usable():
    v5 = {"version": 5, "app_volumes": {"aurora.exe": {"volume": 0.5, "muted": False}}}

    migrated = migrate(v5)

    assert migrated["app_volumes"] == {"aurora.exe": {"volume": 0.5, "muted": False}}


def test_migrates_v5_normalises_path_separators():
    v5 = {"version": 5, "app_volumes": {r"D:\Games\MyGame\Game.exe": {"volume": 0.5}}}

    migrated = migrate(v5)

    assert migrated["app_volumes"] == {"d:/games/mygame/game.exe": {"volume": 0.5}}


def test_migrates_v6_to_v7_moves_geometry_into_horizontal_block():
    v6 = {
        "version": 6,
        "overlay": {"x": 10, "y": 20, "width": 300, "height": 500, "visible_on_start": True},
    }

    migrated = migrate(v6)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["overlay"]["horizontal"] == {"x": 10, "y": 20, "width": 300, "height": 500}
    assert migrated["overlay"]["visible_on_start"] is True
    assert migrated["overlay"]["layout_mode"] == "horizontal"
    assert set(migrated["overlay"]["vertical"]) == {"x", "y", "width", "height"}


def test_migrates_v6_to_v7_drops_flat_geometry_keys():
    v6 = {"version": 6, "overlay": {"x": 10, "y": 20, "width": 300, "height": 500}}

    migrated = migrate(v6)

    for key in ("x", "y", "width", "height"):
        assert key not in migrated["overlay"]


def test_migrates_v6_to_v7_defaults_when_overlay_missing():
    v6 = {"version": 6}

    migrated = migrate(v6)

    assert migrated["overlay"]["layout_mode"] == "horizontal"
    assert migrated["overlay"]["visible_on_start"] is False
    assert migrated["overlay"]["horizontal"]["width"] == DEFAULT_SETTINGS["overlay"]["horizontal"]["width"]


def test_migrates_v7_to_v8_adds_whitelist_mini_widget_and_hotkey():
    v7 = {
        "version": 7,
        "hotkeys": [{"action": "toggle_overlay", "combo": "ctrl+shift+m", "enabled": True}],
    }

    migrated = migrate(v7)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["whitelist"] == {"enabled": False, "apps": []}
    assert migrated["mini_widget"] == {"enabled": False, "x": 100, "y": 40, "scale": 1.0}
    assert migrated["hotkeys"][0] == {
        "action": "toggle_overlay",
        "combo": "ctrl+shift+m",
        "enabled": True,
    }
    assert sum(hotkey["action"] == "toggle_mini_widget" for hotkey in migrated["hotkeys"]) == 1


def test_migrates_partial_v7_hotkeys_to_complete_defaults():
    migrated = migrate({"version": 7})

    assert migrated["hotkeys"] == DEFAULT_SETTINGS["hotkeys"]


def test_migrates_v8_to_v9_preserves_mini_widget_size_from_ui_scale():
    v8 = {
        "version": 8,
        "ui_scale": 1.7,
        "mini_widget": {"enabled": True, "x": 20, "y": 30},
    }

    migrated = migrate(v8)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["mini_widget"] == {"enabled": True, "x": 20, "y": 30, "scale": 1.7}
