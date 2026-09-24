import threading
from ctypes import pointer
from types import SimpleNamespace

import pytest
from pycaw.api.endpointvolume.depend import AUDIO_VOLUME_NOTIFICATION_DATA
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest

from sound_mixer.audio import master_listener
from sound_mixer.audio.master_listener import MasterAudioListener
from sound_mixer.audio.pycaw_backend import PycawAudioBackend
from sound_mixer.mixer.master_sync import MasterAudioSync
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.overlay.window import OverlayWindow
from tests.test_process_exit_listener import wait_until


class Endpoint:
    def __init__(self, volume, muted=False):
        self.volume = volume
        self.muted = muted
        self.callbacks = []
        self.history = []
        self.threads = []
        self.volume_reads = 0
        self.fail_register = False
        self.fail_read = False

    def RegisterControlChangeNotify(self, callback):
        self.threads.append(threading.get_ident())
        if self.fail_register:
            raise OSError("Registration failed")
        self.callbacks.append(callback)
        self.history.append(callback)

    def UnregisterControlChangeNotify(self, callback):
        self.threads.append(threading.get_ident())
        self.callbacks.remove(callback)

    def GetMasterVolumeLevelScalar(self):
        self.volume_reads += 1
        if self.fail_read:
            raise OSError("Device unavailable")
        return self.volume

    def GetMute(self):
        if self.fail_read:
            raise OSError("Device unavailable")
        return self.muted

    def SetMasterVolumeLevelScalar(self, value, context):
        self.volume = value
        self.notify()

    def SetMute(self, value, context):
        self.muted = value
        self.notify()

    def notify(self, callback=None):
        data = AUDIO_VOLUME_NOTIFICATION_DATA()
        data.fMasterVolume = self.volume
        data.bMuted = self.muted
        data.nChannels = 1
        for handler in [callback] if callback is not None else list(self.callbacks):
            handler.OnNotify(pointer(data))


class Devices:
    def __init__(self):
        self.first = SimpleNamespace(id="speakers", EndpointVolume=Endpoint(0.25))
        self.second = SimpleNamespace(id="headphones", EndpointVolume=Endpoint(0.75, True))
        self.current = self.first
        self.callback = None
        self.threads = []
        self.fail_register = False

    def GetSpeakers(self):
        return self.current

    def RegisterEndpointNotificationCallback(self, callback):
        self.threads.append(threading.get_ident())
        if self.fail_register:
            raise OSError("Device notifications unavailable")
        self.callback = callback

    def UnregisterEndpointNotificationCallback(self, callback):
        self.threads.append(threading.get_ident())
        assert self.callback is callback
        self.callback = None

    def switch(self, device):
        self.current = device
        self.callback.OnDefaultDeviceChanged(0, 1, device.id if device else None)


@pytest.fixture
def devices(monkeypatch):
    devices = Devices()
    monkeypatch.setattr(master_listener.AudioUtilities, "GetSpeakers", devices.GetSpeakers)
    monkeypatch.setattr(master_listener.AudioUtilities, "GetDeviceEnumerator", lambda: devices)
    monkeypatch.setattr(master_listener.AudioUtilities, "GetAllSessions", lambda: [])
    monkeypatch.setattr(master_listener.AudioUtilities, "GetAudioSessionManager", lambda: None)
    return devices


@pytest.fixture
def listener(qapp, devices):
    listener = MasterAudioListener()
    yield listener
    listener.stop()
    listener.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_volume_and_mute_callbacks_are_delivered_on_gui_thread_without_polling(qapp, devices, listener):
    states = []
    listener.state_changed.connect(lambda volume, muted: states.append((volume, muted, threading.get_ident())))
    listener.start()
    wait_until(lambda: len(states) == 1)
    endpoint = devices.first.EndpointVolume
    assert states == [(0.25, False, threading.get_ident())]
    reads = endpoint.volume_reads

    endpoint.volume, endpoint.muted = 0.6, True
    thread = threading.Thread(target=endpoint.notify)
    thread.start()
    thread.join()
    assert len(states) == 1
    wait_until(lambda: len(states) == 2)
    assert states[-1] == (pytest.approx(0.6), True, threading.get_ident())
    QTest.qWait(50)
    assert endpoint.volume_reads == reads

    listener.stop()
    assert not endpoint.callbacks
    assert devices.callback is None
    assert all(thread_id != threading.get_ident() for thread_id in endpoint.threads + devices.threads)
    endpoint.notify(endpoint.history[-1])
    qapp.processEvents()
    assert len(states) == 2


def test_device_switch_discards_old_callbacks_and_rebinds(qapp, devices, listener):
    states = []
    changes = []
    listener.state_changed.connect(lambda volume, muted: states.append((volume, muted)))
    listener.device_changed.connect(lambda: changes.append(True))
    listener.start()
    wait_until(lambda: states == [(0.25, False)])
    old_callback = devices.first.EndpointVolume.history[-1]

    devices.switch(devices.second)
    wait_until(lambda: states[-1] == (0.75, True))
    assert not devices.first.EndpointVolume.callbacks
    assert len(devices.second.EndpointVolume.callbacks) == 1
    assert len(changes) == 2
    devices.first.EndpointVolume.volume = 0.1
    devices.first.EndpointVolume.notify(old_callback)
    devices.second.EndpointVolume.volume = 0.8
    devices.second.EndpointVolume.notify()
    wait_until(lambda: states[-1] == (pytest.approx(0.8), True))
    assert not any(volume == pytest.approx(0.1) for volume, _ in states)


def test_microphone_communications_and_unrelated_devices_do_not_rebind(qapp, devices, listener):
    states = []
    listener.state_changed.connect(lambda *state: states.append(state))
    listener.start()
    wait_until(lambda: len(states) == 1)
    endpoint = devices.first.EndpointVolume
    devices.callback.OnDefaultDeviceChanged(1, 1, "microphone")
    devices.callback.OnDefaultDeviceChanged(0, 2, "communications")
    devices.callback.OnDeviceAdded("microphone")
    devices.callback.OnDeviceStateChanged("microphone", 1)
    QTest.qWait(50)
    assert len(endpoint.history) == 1
    assert endpoint.volume_reads == 1
    assert len(states) == 1


def test_no_output_retains_device_subscription_and_recovers_on_event(qapp, devices, listener):
    states, available = [], []
    listener.state_changed.connect(lambda *state: states.append(state))
    listener.availability_changed.connect(available.append)
    listener.start()
    wait_until(lambda: available and available[-1])
    devices.switch(None)
    wait_until(lambda: available[-1] is False)
    assert devices.callback is not None
    assert not devices.first.EndpointVolume.callbacks
    assert states == [(0.25, False)]

    devices.switch(devices.second)
    wait_until(lambda: available[-1] is True)
    assert states[-1] == (0.75, True)


@pytest.mark.parametrize("failure", ["endpoint", "enumerator", "read"])
def test_subscription_failure_recovers_on_retry(qapp, devices, listener, monkeypatch, failure):
    monkeypatch.setattr(master_listener, "RETRY_INTERVAL_S", 0.05)
    endpoint = devices.first.EndpointVolume
    endpoint.fail_register = failure == "endpoint"
    devices.fail_register = failure == "enumerator"
    endpoint.fail_read = failure == "read"
    states, available = [], []
    listener.state_changed.connect(lambda *state: states.append(state))
    listener.availability_changed.connect(available.append)
    listener.start()
    wait_until(lambda: available and available[-1] is False)
    assert states == []
    endpoint.fail_register = devices.fail_register = endpoint.fail_read = False
    wait_until(lambda: available[-1] is True)
    assert states == [(0.25, False)]
    assert len(endpoint.callbacks) == 1


def test_stop_during_retry_is_prompt_and_suppresses_queued_updates(qapp, devices, listener):
    devices.current = None
    available = []
    listener.availability_changed.connect(available.append)
    listener.start()
    wait_until(lambda: available == [False])
    listener.stop()
    assert devices.callback is None
    qapp.processEvents()
    assert available == [False]


def test_failed_master_read_preserves_last_known_state(devices, settings):
    backend = PycawAudioBackend()
    model = MixerModel(backend, settings)
    devices.first.EndpointVolume.fail_read = True
    assert model.refresh_master() is False
    assert model.entries[0].volume == 0.25
    assert model.entries[0].muted is False


def test_hidden_overlay_mini_and_tray_follow_system_and_new_endpoint(qapp, devices, settings):
    settings.set_mini_widget_show_master(True)
    backend = PycawAudioBackend()
    model = MixerModel(backend, settings)
    overlay = OverlayWindow(model, settings)
    overlay._finish_warm_up()
    mini = MiniWidget(model, settings)
    mini.set_enabled(True)
    tray_mutes = []
    model.set_master_mute_listener(tray_mutes.append)

    def refresh_views():
        overlay.refresh_view()
        mini.refresh_view()

    sync = MasterAudioSync(model, backend, refresh_views, overlay.restart_session_listener)
    overlay.visibility_changed.connect(sync.set_overlay_visible)
    try:
        sync.start()
        wait_until(lambda: bool(devices.first.EndpointVolume.callbacks))
        assert not overlay.isVisible()
        devices.first.EndpointVolume.volume = 0.4
        devices.first.EndpointVolume.muted = True
        devices.first.EndpointVolume.notify()
        wait_until(lambda: mini._entries["master"]._volume_label.text() == "40%")
        assert model.entries[0].volume == pytest.approx(0.4)
        assert overlay._entry_widgets[0]._slider.value() == 40
        assert mini._entries["master"]._muted_icon_label.isVisible()
        assert tray_mutes[-1] is True

        devices.switch(devices.second)
        wait_until(lambda: mini._entries["master"]._volume_label.text() == "75%")
        model.set_volume(0.9, 0)
        assert devices.second.EndpointVolume.volume == pytest.approx(0.9)
        assert devices.first.EndpointVolume.volume == 0.4
        assert not sync._timer.isActive()
    finally:
        sync.stop()
        mini.stop()
        mini.close()
        overlay.close()
        overlay._session_listener.stop()
        mini.deleteLater()
        overlay.deleteLater()
        sync.deleteLater()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
