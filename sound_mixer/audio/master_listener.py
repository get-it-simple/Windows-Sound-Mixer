import logging
import queue
import threading
import time

import comtypes
from pycaw.callbacks import AudioEndpointVolumeCallback, MMNotificationClient
from pycaw.pycaw import AudioUtilities
from PySide6.QtCore import QObject, Qt, Signal, Slot

RETRY_INTERVAL_S = 5.0
_logger = logging.getLogger(__name__)


class _VolumeCallback(AudioEndpointVolumeCallback):
    def __init__(self, messages, generation) -> None:
        super().__init__()
        self._messages = messages
        self._generation = generation

    def on_notify(self, new_volume, new_mute, event_context, channels, channel_volumes):
        self._messages.put(("volume", self._generation, float(new_volume), bool(new_mute)))


class _DeviceCallback(MMNotificationClient):
    def __init__(self, messages) -> None:
        super().__init__()
        self._messages = messages

    def on_default_device_changed(self, flow, flow_id, role, role_id, default_device_id):
        if flow_id == 0 and role_id == 1:
            self._messages.put(("device", None))

    def on_device_added(self, added_device_id):
        self._messages.put(("device", None))

    def on_device_removed(self, removed_device_id):
        self._messages.put(("device", removed_device_id))

    def on_device_state_changed(self, device_id, new_state, new_state_id):
        self._messages.put(("device", device_id))


class MasterAudioListener(QObject):
    state_changed = Signal(float, bool)
    device_changed = Signal()
    availability_changed = Signal(bool)
    _message = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._message.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._messages = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._generation = 0
        self._endpoint = None
        self._endpoint_id = None
        self._volume_callback = None
        self._unavailable_reported = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._messages = queue.Queue()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MasterAudioListener")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._messages.put(("stop",))
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    @Slot(object)
    def _deliver(self, message) -> None:
        kind, generation, *values = message
        if self._stop_event.is_set() or generation != self._generation:
            return
        if kind == "state":
            self.state_changed.emit(*values)
        elif kind == "device":
            self.device_changed.emit()
        elif kind == "available":
            self.availability_changed.emit(*values)

    def _post(self, kind, *values) -> None:
        self._message.emit((kind, self._generation, *values))

    def _unbind(self) -> None:
        endpoint, callback = self._endpoint, self._volume_callback
        self._endpoint = None
        self._endpoint_id = None
        self._volume_callback = None
        if endpoint is not None and callback is not None:
            try:
                endpoint.UnregisterControlChangeNotify(callback)
            except Exception:
                _logger.debug("Cannot unregister master volume callback", exc_info=True)

    def _bind(self, changed_device_id=None) -> None:
        speakers = AudioUtilities.GetSpeakers()
        if speakers is None:
            raise OSError("No default audio output")
        if self._endpoint is not None and speakers.id == self._endpoint_id and changed_device_id != speakers.id:
            return
        self._generation += 1
        self._unbind()
        self._endpoint = speakers.EndpointVolume
        self._endpoint_id = speakers.id
        callback = _VolumeCallback(self._messages, self._generation)
        self._endpoint.RegisterControlChangeNotify(callback)
        self._volume_callback = callback
        volume = self._endpoint.GetMasterVolumeLevelScalar()
        muted = bool(self._endpoint.GetMute())
        self._unavailable_reported = False
        self._post("device")
        self._post("state", volume, muted)
        self._post("available", True)

    def _report_unavailable(self) -> None:
        self._unbind()
        if not self._unavailable_reported:
            self._generation += 1
            self._unavailable_reported = True
            self._post("device")
            self._post("available", False)

    def _listen(self) -> None:
        enumerator = AudioUtilities.GetDeviceEnumerator()
        callback = _DeviceCallback(self._messages)
        enumerator.RegisterEndpointNotificationCallback(callback)
        try:
            retry_at = None
            needs_bind = True
            changed_device_id = None
            while not self._stop_event.is_set():
                if needs_bind:
                    try:
                        self._bind(changed_device_id)
                        retry_at = None
                    except Exception:
                        self._report_unavailable()
                        retry_at = time.monotonic() + RETRY_INTERVAL_S
                        _logger.debug("Master endpoint unavailable; retrying", exc_info=True)
                    needs_bind = False
                timeout = None if retry_at is None else max(0.0, retry_at - time.monotonic())
                try:
                    message = self._messages.get(timeout=timeout)
                except queue.Empty:
                    needs_bind = True
                    continue
                if message[0] == "stop":
                    return
                if message[0] == "device":
                    changed_device_id = message[1]
                    needs_bind = True
                elif message[0] == "volume" and message[1] == self._generation:
                    self._post("state", *message[2:])
        finally:
            self._unbind()
            try:
                enumerator.UnregisterEndpointNotificationCallback(callback)
            except Exception:
                _logger.debug("Cannot unregister audio device callback", exc_info=True)

    def _run(self) -> None:
        initialized = False
        try:
            comtypes.CoInitializeEx(0)
            initialized = True
            while not self._stop_event.is_set():
                try:
                    self._listen()
                except Exception:
                    self._report_unavailable()
                    _logger.debug("Master audio subscription unavailable; retrying", exc_info=True)
                    if self._stop_event.wait(RETRY_INTERVAL_S):
                        return
        except Exception:
            self._post("available", False)
            _logger.exception("Cannot initialize master audio listener")
        finally:
            if initialized:
                comtypes.CoUninitialize()
