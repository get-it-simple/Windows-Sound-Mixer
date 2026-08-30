import sys

from sound_mixer.mixer.subprocess_manager import SubprocessManager, is_any_managed_app_running
from sound_mixer.settings.store import SettingsStore


class _FakeProcess:
    def __init__(self, name: str) -> None:
        self.info = {"name": name}


def _fake_process_iter(running_names):
    def _iter(attrs=None):
        return [_FakeProcess(name) for name in running_names]

    return _iter


def test_is_any_managed_app_running_matches_by_basename():
    running = _fake_process_iter(["Sandbox.exe", "shell.exe"])

    assert is_any_managed_app_running(["C:/Games/sandbox.exe"], process_iter=running) is True


def test_is_any_managed_app_running_false_when_not_running():
    running = _fake_process_iter(["shell.exe"])

    assert is_any_managed_app_running(["C:/Games/sandbox.exe"], process_iter=running) is False


def test_is_any_managed_app_running_false_for_empty_paths():
    running = _fake_process_iter(["sandbox.exe"])

    assert is_any_managed_app_running([], process_iter=running) is False


def _make_settings(tmp_path) -> SettingsStore:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    return store


def _set_managed_executable(settings: SettingsStore, enabled: bool = True) -> None:
    settings.set_managed_apps([{"path": sys.executable, "enabled": enabled}])


def test_has_enabled_apps_reflects_settings(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    manager = SubprocessManager(settings, on_tick=lambda: None)

    assert manager.has_enabled_apps() is False

    _set_managed_executable(settings)
    assert manager.has_enabled_apps() is True

    _set_managed_executable(settings, enabled=False)
    assert manager.has_enabled_apps() is False


def test_is_active_defaults_to_false(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    _set_managed_executable(settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)

    assert manager.is_active() is False


def test_sync_stays_stopped_by_default_even_with_enabled_apps(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    _set_managed_executable(settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)

    manager.sync()

    assert manager._timer.isActive() is False


def test_sync_stays_stopped_when_active_but_no_enabled_apps(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    manager = SubprocessManager(settings, on_tick=lambda: None)

    manager.set_active(True)

    assert manager._timer.isActive() is False


def test_set_active_true_starts_timer_when_apps_enabled(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    _set_managed_executable(settings)
    settings.set_subprocess_management_interval_seconds(2)
    manager = SubprocessManager(settings, on_tick=lambda: None)

    manager.set_active(True)

    assert manager.is_active() is True
    assert manager._timer.isActive() is True
    assert manager._timer.interval() == 2000


def test_set_active_false_stops_timer(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    _set_managed_executable(settings)
    manager = SubprocessManager(settings, on_tick=lambda: None)
    manager.set_active(True)

    manager.set_active(False)

    assert manager.is_active() is False
    assert manager._timer.isActive() is False


def test_sync_ignores_disabled_apps_even_when_active(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    _set_managed_executable(settings, enabled=False)
    manager = SubprocessManager(settings, on_tick=lambda: None)

    manager.set_active(True)

    assert manager._timer.isActive() is False


def test_sync_enforces_minimum_interval(tmp_path, qapp):
    settings = _make_settings(tmp_path)
    _set_managed_executable(settings)
    settings.data["subprocess_management"]["interval_seconds"] = 0
    manager = SubprocessManager(settings, on_tick=lambda: None)

    manager.set_active(True)

    assert manager._timer.interval() >= 1000


def test_check_invokes_callback_only_when_app_is_running(tmp_path, qapp, monkeypatch):
    import sound_mixer.mixer.subprocess_manager as subprocess_manager_module

    settings = _make_settings(tmp_path)
    _set_managed_executable(settings)
    calls = []
    manager = SubprocessManager(settings, on_tick=lambda: calls.append(1))

    monkeypatch.setattr(
        subprocess_manager_module, "is_any_managed_app_running", lambda paths, process_iter=None: False
    )
    manager._check()
    assert calls == []

    monkeypatch.setattr(
        subprocess_manager_module, "is_any_managed_app_running", lambda paths, process_iter=None: True
    )
    manager._check()
    assert calls == [1]
