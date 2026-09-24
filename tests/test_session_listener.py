import pytest
from PySide6.QtTest import QTest

from sound_mixer.audio import session_listener
from sound_mixer.audio.session_listener import AudioSessionListener
from tests.test_process_exit_listener import wait_until


class Control:
    def __init__(self, identity="one"):
        self.identity = identity
        self.state = 1
        self.callbacks = []

    def QueryInterface(self, interface):
        return self

    def GetProcessId(self):
        return 123

    def GetState(self):
        return self.state

    def GetSessionInstanceIdentifier(self):
        return self.identity

    def RegisterAudioSessionNotification(self, callback):
        self.callbacks.append(callback)

    def UnregisterAudioSessionNotification(self, callback):
        self.callbacks.remove(callback)


class Manager:
    def __init__(self):
        self.controls = [Control()]
        self.callbacks = []
        self.enumerations = 0

    def RegisterSessionNotification(self, callback):
        self.callbacks.append(callback)

    def UnregisterSessionNotification(self, callback):
        self.callbacks.remove(callback)

    def GetSessionEnumerator(self):
        self.enumerations += 1
        return self

    def GetCount(self):
        return len(self.controls)

    def GetSession(self, index):
        return self.controls[index]


@pytest.fixture
def native_listener(qapp, monkeypatch):
    manager = Manager()
    monkeypatch.setattr(session_listener.AudioUtilities, "GetAudioSessionManager", lambda: manager)
    listener = AudioSessionListener()
    events = []
    listener.event_received.connect(events.append)
    listener.start()
    wait_until(lambda: bool(events))
    yield listener, manager, events
    listener.stop()
    qapp.processEvents()
    assert not manager.callbacks
    assert all(not control.callbacks for control in manager.controls)


def test_native_subscription_idles_without_enumerating(native_listener):
    listener, manager, events = native_listener
    count = manager.enumerations
    QTest.qWait(150)
    assert manager.enumerations == count
    manager.controls[0].callbacks[0].on_simple_volume_changed(0.4, True, None)
    wait_until(lambda: any(event.kind == "volume" for event in events))
    assert manager.enumerations == count
    event = events[-1]
    assert event.session_id == "one" and event.volume == 0.4 and event.muted


def test_new_sessions_subscribe_and_expired_sessions_unsubscribe(native_listener):
    listener, manager, events = native_listener
    new = Control("two")
    manager.controls.append(new)
    manager.callbacks[0].OnSessionCreated(None)
    wait_until(lambda: bool(new.callbacks))
    assert len(new.callbacks) == 1
    new.state = 0
    new.callbacks[0].on_state_changed("Inactive", 0)
    QTest.qWait(50)
    assert len(new.callbacks) == 1
    new.state = 2
    new.callbacks[0].on_state_changed("Expired", 2)
    wait_until(lambda: not new.callbacks)
    wait_until(lambda: any(event.kind == "removed" and event.session_id == "two" for event in events))


def test_restart_replaces_callbacks_without_leaking(native_listener):
    listener, manager, events = native_listener
    old = manager.controls[0].callbacks[0]
    generation = listener.generation
    listener.restart()
    wait_until(lambda: manager.controls[0].callbacks and manager.controls[0].callbacks[0] is not old)
    assert len(manager.controls[0].callbacks) == 1
    assert len(manager.callbacks) == 1
    assert listener.generation > generation


def test_session_creation_burst_enumerates_once(native_listener):
    listener, manager, events = native_listener
    count = manager.enumerations
    for index in range(20):
        manager.controls.append(Control(f"new-{index}"))
        manager.callbacks[0].OnSessionCreated(None)
    wait_until(lambda: all(control.callbacks for control in manager.controls))
    assert manager.enumerations == count + 1
    assert all(len(control.callbacks) == 1 for control in manager.controls)


def test_unavailable_manager_recovers_and_stop_interrupts_retry(qapp, monkeypatch):
    manager = Manager()
    current = [None]
    monkeypatch.setattr(session_listener, "RETRY_INITIAL_S", 0.02)
    monkeypatch.setattr(session_listener, "RETRY_MAX_S", 0.08)
    monkeypatch.setattr(session_listener.AudioUtilities, "GetAudioSessionManager", lambda: current[0])
    listener = AudioSessionListener()
    available = []
    listener.availability_changed.connect(lambda generation, state: available.append(state))
    try:
        listener.start()
        wait_until(lambda: available and available[-1] is False)
        current[0] = manager
        wait_until(lambda: available[-1] is True)
        assert len(manager.controls[0].callbacks) == 1
    finally:
        listener.stop()
    assert not listener._thread.is_alive()
    assert not manager.callbacks
