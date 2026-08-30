import pytest

from sound_mixer.autostart.registry import AutostartManager, AutostartUnavailableError
from tests.fake_registry import FakeRegistry


@pytest.fixture
def manager() -> AutostartManager:
    return AutostartManager(app_name="SoundMixerTest", registry=FakeRegistry())


def test_initially_disabled(manager):
    assert manager.is_enabled() is False


def test_enable_then_disable(manager):
    manager.enable()
    assert manager.is_enabled() is True

    manager.disable()
    assert manager.is_enabled() is False


def test_disable_when_not_enabled_is_noop(manager):
    manager.disable()
    assert manager.is_enabled() is False


def test_enable_is_idempotent(manager):
    manager.enable()
    manager.enable()
    assert manager.is_enabled() is True


def test_set_enabled_does_not_rewrite_matching_value(manager):
    manager.set_enabled(True)
    registry = manager._registry

    manager.set_enabled(True)

    assert registry.set_calls == 1


@pytest.mark.parametrize("operation", ["read", "write", "delete"])
def test_registry_os_errors_are_controlled(operation):
    class FailingRegistry(FakeRegistry):
        def OpenKey(self, root, path, reserved, access):
            if operation == "read" and access == self.KEY_READ:
                raise PermissionError("denied")
            return super().OpenKey(root, path, reserved, access)

        def SetValueEx(self, key, name, reserved, type_, value):
            if operation == "write":
                raise OSError("denied")
            return super().SetValueEx(key, name, reserved, type_, value)

        def DeleteValue(self, key, name):
            if operation == "delete":
                raise PermissionError("denied")
            return super().DeleteValue(key, name)

    manager = AutostartManager(app_name="SoundMixerTest", registry=FailingRegistry())

    with pytest.raises(AutostartUnavailableError):
        if operation == "read":
            manager.is_enabled()
        elif operation == "write":
            manager.enable()
        else:
            manager._registry._values.setdefault(manager._key_path, {})[manager._app_name] = "value"
            manager.disable()


def test_portable_command_preserves_flag(manager, monkeypatch):
    monkeypatch.setattr("sound_mixer.autostart.registry.sys.argv", ["SoundMixer.exe", "--portable"])

    assert manager._command().endswith(" --portable")


def test_unavailable_without_registry():
    manager = AutostartManager(app_name="SoundMixerTest", registry=None)

    with pytest.raises(AutostartUnavailableError):
        manager.is_enabled()
