import sys

import pytest

import sound_mixer.overlay.icons as icons
from sound_mixer.overlay.icons import clear_caches, load_app_icon, load_icon


@pytest.fixture(autouse=True)
def fresh_icon_caches():
    clear_caches()
    yield
    clear_caches()


def test_load_app_icon_falls_back_for_empty_path(qapp):
    icon = load_app_icon("")

    assert not icon.isNull()


def test_load_app_icon_falls_back_for_nonexistent_path(qapp):
    icon = load_app_icon("C:/does/not/exist.exe")

    assert not icon.isNull()


def test_load_app_icon_returns_icon_for_existing_file(qapp):
    icon = load_app_icon(sys.executable)

    assert not icon.isNull()


def test_load_icon_returns_cached_instance(qapp):
    first = load_icon("volume")
    second = load_icon("volume")

    assert first.cacheKey() == second.cacheKey()


def test_trash_icon_loads(qapp):
    icon = load_icon("trash")

    assert not icon.isNull()


def test_load_app_icon_cached_per_path(qapp):
    first = load_app_icon(sys.executable)
    second = load_app_icon(sys.executable)

    assert first.cacheKey() == second.cacheKey()


def test_load_app_icon_distinct_paths_not_conflated(qapp):
    fallback = load_app_icon("")
    real = load_app_icon(sys.executable)

    assert not fallback.isNull()
    assert not real.isNull()


def test_file_icon_provider_constructed_once(qapp, monkeypatch):
    constructed = []
    real_provider = icons.QFileIconProvider

    class CountingProvider(real_provider):
        def __init__(self):
            constructed.append(1)
            super().__init__()

    monkeypatch.setattr(icons, "QFileIconProvider", CountingProvider)

    load_app_icon(sys.executable)
    load_app_icon(__file__)

    assert len(constructed) == 1
def test_app_icon_cache_evicts_least_recently_used(qapp, monkeypatch):
    from PySide6.QtGui import QIcon
    from unittest.mock import Mock
    import sound_mixer.overlay.icons as icons

    icons.clear_caches()
    monkeypatch.setattr(icons, "APP_ICON_CACHE_LIMIT", 2)
    extract = Mock(side_effect=lambda path: QIcon())
    monkeypatch.setattr(icons, "_extract_app_icon", extract)
    try:
        first = icons.load_app_icon("first.exe")
        icons.load_app_icon("second.exe")
        assert icons.load_app_icon("first.exe") is first
        icons.load_app_icon("third.exe")
        assert len(icons._app_icon_cache) == 2
        icons.load_app_icon("second.exe")
        assert extract.call_count == 4
        assert "first.exe" not in icons._app_icon_cache
    finally:
        icons.clear_caches()
