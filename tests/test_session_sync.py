import ctypes
import queue
from time import perf_counter
from unittest.mock import Mock

from comtypes import GUID
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest

from sound_mixer.audio.events import SessionEvent, VOLUME_EVENT_CONTEXT
from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.audio.session_listener import _SessionHandler
from sound_mixer.mixer.model import MixerModel
from sound_mixer.mixer.session_sync import SessionAudioSync
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings.store import SettingsStore


class Listener(QObject):
    event_received = Signal(object)
    availability_changed = Signal(int, bool)
    process_exited = Signal()

    def __init__(self):
        super().__init__()
        self.generation = 0
        self.rescans = 0

    def start(self):
        self.generation += 1
        self.availability_changed.emit(self.generation, True)

    def restart(self):
        self.generation += 1

    def rescan(self):
        self.rescans += 1

    def stop(self):
        self.generation += 1

    def sync(self, pids):
        self.pids = pids


@pytest.fixture
def rig(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    listener = Listener()
    process_listener = Listener()
    refreshed = Mock()
    sync = SessionAudioSync(model, fake_backend, refreshed, listener=listener, process_listener=process_listener)
    fake_backend.refresh = Mock(wraps=fake_backend.refresh)
    sync.start()
    QTest.qWait(100)
    fake_backend.refresh.reset_mock()
    refreshed.reset_mock()
    yield sync, listener, model, refreshed
    sync.stop()


@pytest.mark.parametrize("visible", [False, True])
def test_external_volume_updates_views_and_persists_without_scanning(rig, fake_backend, settings, visible):
    sync, listener, model, refreshed = rig
    overlay = OverlayWindow(model, settings, request_refresh=sync.request_refresh)
    overlay._finish_warm_up()
    mini = MiniWidget(model, settings, request_refresh=sync.request_refresh)
    mini.set_enabled(True)
    sync._refresh_views = lambda: (overlay.refresh_view(), mini.refresh_view())
    try:
        overlay.setVisible(visible)
        QTest.qWait(100)
        fake_backend.refresh.reset_mock()
        before = overlay._entry_widgets[1]._slider.value()
        session = fake_backend.enumerate_sessions()[0]
        listener.event_received.emit(SessionEvent.volume_changed(listener.generation, session.instance_id, 0.37, True))
        QTest.qWait(100)
        assert session.volume == 0.37 and session.muted
        assert model.entries[1].volume == 0.37 and model.entries[1].muted
        assert mini._entries[session.key]._volume_label.text() == "37%"
        assert overlay._entry_widgets[1]._slider.value() == (37 if visible else before)
        fake_backend.refresh.assert_not_called()
        reloaded = SettingsStore(settings.path)
        reloaded.load()
        assert reloaded.get_app_volume(session.key) == 0.37
        assert reloaded.get_app_muted(session.key)
        overlay.show()
        assert overlay._entry_widgets[1]._slider.value() == 37
    finally:
        overlay.close()
        mini.stop()
        mini.close()


def test_event_burst_is_bounded_and_newest_value_wins(rig, fake_backend):
    sync, listener, model, refreshed = rig
    identity = fake_backend.enumerate_sessions()[0].instance_id
    for value in (0.1, 0.2, 0.3, 0.4):
        listener.event_received.emit(SessionEvent.volume_changed(listener.generation, identity, value, False))
        QTest.qWait(20)
    assert refreshed.call_count >= 1
    QTest.qWait(80)
    assert model.entries[1].volume == 0.4
    assert refreshed.call_count <= 2
    fake_backend.refresh.assert_not_called()


def test_creation_exit_and_scan_requests_share_one_refresh(rig, fake_backend):
    sync, listener, model, refreshed = rig
    session = FakeAudioSession(123, "new.exe", "New")
    fake_backend.add_session(session)
    listener.event_received.emit(SessionEvent(listener.generation, "topology"))
    sync.request_refresh()
    sync._process_listener.process_exited.emit()
    QTest.qWait(100)
    fake_backend.refresh.assert_called_once()
    assert model.entries[-1].key == "new.exe"
    assert session.pid in sync._process_listener.pids


def test_late_event_cannot_undo_local_volume(rig, fake_backend):
    sync, listener, model, refreshed = rig
    session = fake_backend.enumerate_sessions()[0]
    event = SessionEvent.volume_changed(listener.generation, session.instance_id, 0.2, False)
    model.set_volume(0.7, 1)
    listener.event_received.emit(event)
    QTest.qWait(100)
    assert model.entries[1].volume == session.volume == 0.7


def test_new_session_initial_state_does_not_overwrite_saved_volume(rig, fake_backend, settings):
    sync, listener, model, refreshed = rig
    settings.set_app_volume("new.exe", 0.23)
    settings.set_app_muted("new.exe", True)
    session = FakeAudioSession(123, "new.exe", "New")
    fake_backend.add_session(session)
    listener.event_received.emit(SessionEvent(listener.generation, "topology"))
    listener.event_received.emit(SessionEvent.volume_changed(listener.generation, session.instance_id, 1, False))
    QTest.qWait(100)
    assert session.volume == 0.23 and session.muted
    assert settings.get_app_volume("new.exe") == 0.23
    assert settings.get_app_muted("new.exe")


def test_device_reconnect_drops_old_events_and_restores_new_sessions(rig, fake_backend, settings):
    sync, listener, model, refreshed = rig
    old = fake_backend.enumerate_sessions()[0]
    model.set_volume(0.32, 1)
    stale = SessionEvent.volume_changed(listener.generation, old.instance_id, 0.9, False)
    listener.event_received.emit(stale)
    fake_backend._sessions.clear()
    sync.device_changed()
    QTest.qWait(100)
    assert len(model.entries) == 1
    assert settings.get_app_volume(old.key) == 0.32
    replacement = FakeAudioSession(old.pid, old.process_name, old.display_name)
    fake_backend.add_session(replacement)
    listener.availability_changed.emit(listener.generation, True)
    listener.event_received.emit(stale)
    QTest.qWait(100)
    assert model.entries[1].volume == replacement.volume == 0.32
    assert not sync._fallback.isActive()


def test_fallback_tracks_visibility_and_stops_on_recovery(rig, fake_backend, settings):
    sync, listener, model, refreshed = rig
    assert not sync._fallback.isActive()
    listener.availability_changed.emit(listener.generation, False)
    assert sync._fallback.interval() == 30000
    sync.set_visible(True)
    assert sync._fallback.interval() == 5000
    fake_backend.enumerate_sessions()[0].volume = 0.44
    sync._fallback.timeout.emit()
    QTest.qWait(100)
    assert model.entries[1].volume == 0.44
    assert settings.get_app_volume(model.entries[1].key) == 0.44
    listener.availability_changed.emit(listener.generation, True)
    QTest.qWait(100)
    fake_backend.refresh.reset_mock()
    QTest.qWait(100)
    assert not sync._fallback.isActive()
    fake_backend.refresh.assert_not_called()


def test_recovery_snapshot_saves_external_changes_missed_during_outage(rig, fake_backend, settings):
    sync, listener, model, refreshed = rig
    listener.availability_changed.emit(listener.generation, False)
    QTest.qWait(100)
    fake_backend.enumerate_sessions()[0].volume = 0.29
    listener.availability_changed.emit(listener.generation, True)
    QTest.qWait(100)
    assert model.entries[1].volume == 0.29
    assert settings.get_app_volume(model.entries[1].key) == 0.29


def test_repeated_external_state_does_not_rewrite_settings(rig, fake_backend, settings):
    sync, listener, model, refreshed = rig
    identity = fake_backend.enumerate_sessions()[0].instance_id
    listener.event_received.emit(SessionEvent.volume_changed(listener.generation, identity, 0.38, True))
    QTest.qWait(100)
    settings.save = Mock(wraps=settings.save)
    listener.event_received.emit(SessionEvent.volume_changed(listener.generation, identity, 0.38, True))
    QTest.qWait(100)
    settings.save.assert_not_called()


def test_session_callback_ignores_own_context_and_copies_external_values():
    messages = queue.Queue()
    callback = _SessionHandler(messages, 7, "session-a")
    own_context = GUID(VOLUME_EVENT_CONTEXT)
    callback.on_simple_volume_changed(0.2, True, ctypes.pointer(own_context))
    assert messages.empty()
    callback.on_simple_volume_changed(0.4, False, None)
    event = messages.get_nowait()
    assert (event.generation, event.session_id, event.volume, event.muted) == (7, "session-a", 0.4, False)
    assert 0 < event.timestamp <= perf_counter()
    callback.on_state_changed("Inactive", 0)
    assert messages.empty()
    callback.on_state_changed("Expired", 2)
    assert messages.get_nowait().kind == "removed"


def test_volume_changes_do_not_relayout_or_update_other_entries(qapp, fake_backend, settings):
    model = MixerModel(fake_backend, settings)
    mini = MiniWidget(model, settings)
    mini.set_enabled(True)
    layout = Mock(wraps=mini._layout_entries)
    mini._layout_entries = layout
    try:
        initial_size = mini.size()
        model.set_volume(0.41, 1)
        mini.refresh_view()
        assert mini._entries["aurora.exe"]._volume_label.text() == "41%"
        assert mini._entries["lumen.exe"]._volume_label.text() == "100%"
        layout.assert_not_called()
        assert mini.size() == initial_size
        fake_backend.add_session(FakeAudioSession(987, "new.exe", "New"))
        model.refresh()
        mini.refresh_view()
        layout.assert_called_once()
        assert "new.exe" in mini._entries
    finally:
        mini.stop()
        mini.close()
