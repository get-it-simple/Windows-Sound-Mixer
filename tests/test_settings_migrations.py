import logging

from sound_mixer.settings.migrations import migrate
from sound_mixer.settings.schema import CURRENT_VERSION


def test_migrates_legacy_v0_document():
    legacy = {
        "volumes": {"chrome.exe": {"volume": 0.5, "muted": False}},
        "master_volume": 0.7,
    }

    migrated = migrate(legacy)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["app_volumes"] == {"chrome.exe": {"volume": 0.5, "muted": False}}
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
        "app_volumes": {"chrome.exe": {"volume": 0.8, "muted": False}},
    }

    migrated = migrate(v1)

    assert migrated["version"] == CURRENT_VERSION
    assert migrated["ignored_apps"] == []
    assert migrated["app_volumes"] == {"chrome.exe": {"volume": 0.8, "muted": False}}


def test_migrates_v1_preserves_existing_ignored_apps():
    v1 = {
        "version": 1,
        "ignored_apps": ["discord.exe"],
    }

    migrated = migrate(v1)

    assert migrated["ignored_apps"] == ["discord.exe"]


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
