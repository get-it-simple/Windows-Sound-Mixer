import os

import pytest

from sound_mixer.autostart.registry import AutostartManager
from tests.conftest import windows_only


@pytest.fixture
def manager():
    app_name = f"SoundMixerTest{os.getpid()}"
    instance = AutostartManager(app_name=app_name)
    yield instance
    instance.disable()


@windows_only
def test_initially_disabled(manager):
    assert manager.is_enabled() is False


@windows_only
def test_enable_then_disable(manager):
    manager.enable()
    assert manager.is_enabled() is True

    manager.disable()
    assert manager.is_enabled() is False


@windows_only
def test_disable_when_not_enabled_is_noop(manager):
    manager.disable()
    assert manager.is_enabled() is False


@windows_only
def test_enable_is_idempotent(manager):
    manager.enable()
    manager.enable()
    assert manager.is_enabled() is True
