from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtTest import QTest

from sound_mixer.app import SoundMixerApp
from sound_mixer.audio.fake_backend import FakeAudioBackend
from sound_mixer.mixer.master_sync import MasterAudioSync
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.overlay.window import OverlayWindow
from tests.test_process_exit_listener import wait_until


class Listener(QObject):
    state_changed = Signal(float, bool)
    device_changed = Signal()
    availability_changed = Signal(bool)

    def start(self):
        pass

    def stop(self):
        pass


def test_fallback_reads_only_after_five_seconds_while_visible_and_unsubscribed(qapp, settings):
    backend = FakeAudioBackend(master_volume=0.2)
    model = MixerModel(backend, settings)
    listener = Listener()
    refreshed = Mock()
    backend.get_master_state = Mock(wraps=backend.get_master_state)
    sync = MasterAudioSync(model, backend, refreshed, Mock(), listener=listener)
    try:
        sync.start()
        backend.set_master_volume(0.6)
        listener.availability_changed.emit(False)
        assert not sync._timer.isActive()
        sync._timer.timeout.emit()
        backend.get_master_state.assert_not_called()

        sync.set_overlay_visible(True)
        assert sync._timer.isActive()
        assert sync._timer.interval() == 5000
        QTest.qWait(100)
        backend.get_master_state.assert_not_called()
        QTest.qWait(5100)
        assert model.entries[0].volume == 0.6
        backend.get_master_state.assert_called_once_with()
        refreshed.assert_called_once_with()

        listener.availability_changed.emit(True)
        assert not sync._timer.isActive()
        backend.get_master_state.reset_mock()
        sync._timer.timeout.emit()
        backend.get_master_state.assert_not_called()

        listener.availability_changed.emit(False)
        assert sync._timer.isActive()
        sync.set_overlay_visible(False)
        assert not sync._timer.isActive()
        sync._timer.timeout.emit()
        backend.get_master_state.assert_not_called()
    finally:
        sync.stop()


def test_master_snapshot_preserves_apps_focus_settings_and_notifies_mute(fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    model.focus_key("lumen.exe")
    apps = list(model.entries[1:])
    saved_master = (settings.get_master_volume(), settings.get_master_muted())
    mutes = []
    model.set_master_mute_listener(mutes.append)
    fake_backend.refresh = Mock(wraps=fake_backend.refresh)
    fake_backend.enumerate_sessions = Mock(wraps=fake_backend.enumerate_sessions)
    fake_backend.set_master_volume = Mock(wraps=fake_backend.set_master_volume)
    fake_backend.set_master_mute = Mock(wraps=fake_backend.set_master_mute)

    model.apply_master_state(0.3, True)
    assert model.entries[0].volume == 0.3
    assert model.entries[0].muted is True
    assert model.entries[1:] == apps
    assert model.focused_entry.key == "lumen.exe"
    assert mutes == [False, True]
    assert (settings.get_master_volume(), settings.get_master_muted()) == saved_master
    fake_backend.refresh.assert_not_called()
    fake_backend.enumerate_sessions.assert_not_called()
    fake_backend.set_master_volume.assert_not_called()
    fake_backend.set_master_mute.assert_not_called()


@pytest.fixture
def widgets(qapp, fake_backend, settings, monkeypatch):
    monkeypatch.setattr("sound_mixer.audio.session_listener.AudioUtilities.GetAudioSessionManager", lambda: None)
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    overlay._finish_warm_up()
    mini = MiniWidget(model, settings)
    mini.set_enabled(True)
    overlay.model_changed.connect(mini.refresh_view)
    mini.model_changed.connect(overlay.refresh_view)
    app = SoundMixerApp.__new__(SoundMixerApp)
    app.model, app.overlay, app.mini_widget, app.settings = model, overlay, mini, settings
    sync = MasterAudioSync(model, fake_backend, app._refresh_views, Mock(), listener=Listener())
    sync.start()
    fake_backend.get_master_state = Mock(wraps=fake_backend.get_master_state)
    yield app
    sync.stop()
    mini.stop()
    mini.close()
    overlay.close()
    overlay._session_listener.stop()
    mini.deleteLater()
    overlay.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("show_master", [True, False])
@pytest.mark.parametrize("event", [
    "session", "exit", "slider", "mute", "scroll", "mini_volume", "mini_mute", "hotkey_volume",
    "hotkey_mute", "ignored_volume", "ignored_mute",
])
def test_app_events_read_master_exactly_once_when_enabled(widgets, fake_backend, settings, show_master, event):
    app = widgets
    settings.set_mini_widget_show_master(show_master)
    app.model.focus_key("aurora.exe")
    if event.startswith("ignored"):
        app.model.ignore_app("aurora.exe")
    fake_backend.get_master_state.reset_mock()
    fake_backend.set_master_volume(0.37)
    fake_backend.set_master_mute(True)
    events = {
        "session": app.overlay._on_new_session,
        "exit": app.mini_widget._on_process_exited,
        "slider": lambda: app.overlay._entry_widgets[1].volume_changed.emit(0.4),
        "mute": lambda: app.overlay._entry_widgets[1].mute_toggled.emit(),
        "scroll": lambda: app.overlay._entry_widgets[1].scrolled.emit(-1),
        "mini_volume": lambda: app.mini_widget.adjust_selected_volume(-1),
        "mini_mute": lambda: app.mini_widget._entries["aurora.exe"].mute_toggled.emit(),
        "hotkey_volume": app._on_volume_down_hotkey,
        "hotkey_mute": app._on_mute_toggle_hotkey,
        "ignored_volume": lambda: app.model.set_ignored_volume("aurora.exe", 0.4),
        "ignored_mute": lambda: app.model.toggle_ignored_mute("aurora.exe"),
    }
    events[event]()
    fake_backend.get_master_state.assert_not_called()
    if show_master:
        wait_until(lambda: fake_backend.get_master_state.call_count > 0)
    else:
        QTest.qWait(550)
    assert fake_backend.get_master_state.call_count == int(show_master)
    assert app.model.entries[0].volume == (0.37 if show_master else 0.5)
    assert app.model.entries[0].muted is show_master
    if show_master and not event.startswith("ignored"):
        assert app.mini_widget._entries["master"]._volume_label.text() == "37%"


def test_periodic_app_updates_do_not_read_master(widgets, fake_backend, settings):
    settings.set_mini_widget_show_master(True)
    fake_backend.set_master_volume(0.3)
    widgets.overlay._refresh()
    widgets._on_subprocess_manager_tick()
    fake_backend.get_master_state.assert_not_called()
    assert widgets.model.entries[0].volume == 0.5
    assert widgets.mini_widget._entries["master"]._volume_label.text() == "50%"


def test_master_controls_do_not_trigger_extra_master_read(widgets, fake_backend, settings):
    settings.set_mini_widget_show_master(True)
    widgets.model.set_volume(0.3, 0)
    widgets.model.toggle_mute(0)
    fake_backend.get_master_state.assert_not_called()
    assert fake_backend.get_master_volume() == 0.3
    assert fake_backend.get_master_mute() is True


def test_system_event_burst_updates_once_500ms_after_last_event(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    listener = Listener()
    refreshed = Mock()
    sync = MasterAudioSync(model, fake_backend, refreshed, Mock(), listener=listener)
    try:
        sync.start()
        listener.state_changed.emit(0.3, False)
        QTest.qWait(300)
        listener.state_changed.emit(0.7, True)
        QTest.qWait(300)
        assert model.entries[0].volume == 0.5
        assert model.entries[0].muted is False
        refreshed.assert_not_called()
        wait_until(lambda: model.entries[0].volume == 0.7)
        assert model.entries[0].muted is True
        refreshed.assert_called_once_with()
        listener.state_changed.emit(0.7, True)
        QTest.qWait(550)
        refreshed.assert_called_once_with()
    finally:
        sync.stop()


def test_app_event_burst_schedules_one_master_read(widgets, fake_backend, settings):
    settings.set_mini_widget_show_master(True)
    fake_backend.set_master_volume(0.8)
    widgets.model.set_volume(0.4, 1)
    widgets.model.toggle_mute(1)
    QTest.qWait(300)
    widgets.overlay._on_new_session()
    widgets.mini_widget._on_process_exited()
    QTest.qWait(300)
    fake_backend.get_master_state.assert_not_called()
    wait_until(lambda: widgets.model.entries[0].volume == 0.8)
    fake_backend.get_master_state.assert_called_once_with()
    assert widgets.mini_widget._entries["master"]._volume_label.text() == "80%"


@pytest.mark.parametrize("cancel", ["device", "stop"])
def test_device_change_and_stop_cancel_pending_old_state(qapp, fake_backend, settings, cancel):
    model = MixerModel(fake_backend, settings)
    listener = Listener()
    refreshed = Mock()
    sync = MasterAudioSync(model, fake_backend, refreshed, Mock(), listener=listener)
    try:
        sync.start()
        listener.state_changed.emit(0.3, True)
        if cancel == "device":
            listener.device_changed.emit()
        else:
            sync.stop()
        QTest.qWait(550)
        assert model.entries[0].volume == 0.5
        assert model.entries[0].muted is False
        refreshed.assert_not_called()
    finally:
        sync.stop()
