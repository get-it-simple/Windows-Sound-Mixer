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
