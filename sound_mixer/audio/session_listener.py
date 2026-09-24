import logging
import queue
import threading
import time

import comtypes
from comtypes import COMObject
from comtypes.hresult import S_OK
from pycaw.callbacks import AudioSessionEvents
from pycaw.pycaw import AudioSession, AudioUtilities, IAudioSessionControl2, IAudioSessionNotification
from PySide6.QtCore import QObject, Signal

from sound_mixer.audio.events import SessionEvent, VOLUME_EVENT_CONTEXT


_logger = logging.getLogger(__name__)
RETRY_INITIAL_S = 5
RETRY_MAX_S = 30
EVENT_BATCH_S = 0.05


class _NotificationHandler(COMObject):
    _com_interfaces_ = [IAudioSessionNotification]

    def __init__(self, messages, generation):
        super().__init__()
        self._messages = messages
        self._generation = generation

    def OnSessionCreated(self, new_session):
        self._messages.put(SessionEvent(self._generation, "topology"))
        return S_OK


class _SessionHandler(AudioSessionEvents):
    def __init__(self, messages, generation, identity):
        super().__init__()
        self._messages = messages
        self._generation = generation
        self._identity = identity

    def on_simple_volume_changed(self, new_volume, new_mute, event_context):
        if event_context and str(event_context.contents).upper() == VOLUME_EVENT_CONTEXT:
            return
        self._messages.put(SessionEvent.volume_changed(
            self._generation, self._identity, new_volume, new_mute
        ))

    def on_state_changed(self, new_state, new_state_id):
        if new_state_id == 2:
            self._messages.put(SessionEvent(self._generation, "removed", self._identity))

    def on_session_disconnected(self, disconnect_reason, disconnect_reason_id):
        self._messages.put(SessionEvent(self._generation, "removed", self._identity))


class AudioSessionListener(QObject):
    event_received = Signal(object)
    availability_changed = Signal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages = queue.Queue()
        self._thread = None
        self._generation = 0
        self._stop_event = threading.Event()
        self._retry_delay = RETRY_INITIAL_S

    @property
    def generation(self):
        return self._generation

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._generation += 1
        self._stop_event.clear()
        self._retry_delay = RETRY_INITIAL_S
        self._messages = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="AudioSessionListener", daemon=True)
        self._thread.start()

    def restart(self):
        self._generation += 1
        self._messages.put("restart")

    def rescan(self):
        self._messages.put("rescan")

    def stop(self):
        self._generation += 1
        self._stop_event.set()
        self._messages.put("stop")
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _reconcile(self, manager, sessions, generation, removed):
        enumerator = manager.GetSessionEnumerator()
        live = set()
        observed = set()
        for index in range(enumerator.GetCount()):
            control = enumerator.GetSession(index)
            if control is None:
                continue
            session = AudioSession(control.QueryInterface(IAudioSessionControl2))
            identity = session.InstanceIdentifier
            observed.add(identity)
            if session.ProcessId == 0 or session.State == 2:
                continue
            if identity in removed:
                continue
            live.add(identity)
            if identity not in sessions:
                session.register_notification(_SessionHandler(self._messages, generation, identity))
                sessions[identity] = session
        for identity in sessions.keys() - live:
            session = sessions.pop(identity)
            try:
                session.unregister_notification()
            except Exception:
                _logger.debug("Cannot unsubscribe expired audio session", exc_info=True)
        removed.intersection_update(observed)

    def _listen(self, generation):
        manager = AudioUtilities.GetAudioSessionManager()
        if manager is None:
            raise OSError("No default audio output")
        handler = _NotificationHandler(self._messages, generation)
        sessions = {}
        removed = set()
        manager.RegisterSessionNotification(handler)
        try:
            self._reconcile(manager, sessions, generation, removed)
            self._retry_delay = RETRY_INITIAL_S
            self.availability_changed.emit(generation, True)
            self.event_received.emit(SessionEvent(generation, "topology"))
            deadline = None
            structural_events = {}
            while not self._stop_event.is_set() and generation == self._generation:
                if deadline is not None and time.monotonic() >= deadline:
                    self._reconcile(manager, sessions, generation, removed)
                    for event in structural_events.values():
                        self.event_received.emit(event)
                    structural_events.clear()
                    deadline = None
                timeout = None if deadline is None else max(0, deadline - time.monotonic())
                try:
                    message = self._messages.get(timeout=timeout)
                except queue.Empty:
                    continue
                if isinstance(message, str):
                    if message in ("stop", "restart"):
                        return
                    if message == "rescan":
                        if deadline is None:
                            deadline = time.monotonic() + EVENT_BATCH_S
                    continue
                if message.generation != generation:
                    continue
                if message.kind in ("topology", "removed"):
                    if message.kind == "removed":
                        removed.add(message.session_id)
                    structural_events[(message.kind, message.session_id)] = message
                    if deadline is None:
                        deadline = time.monotonic() + EVENT_BATCH_S
                else:
                    self.event_received.emit(message)
        finally:
            for session in sessions.values():
                try:
                    session.unregister_notification()
                except Exception:
                    _logger.debug("Cannot unsubscribe audio session", exc_info=True)
            manager.UnregisterSessionNotification(handler)

    def _run(self):
        initialized = False
        try:
            comtypes.CoInitializeEx(0)
            initialized = True
            while not self._stop_event.is_set():
                generation = self._generation
                try:
                    self._listen(generation)
                except Exception:
                    if generation == self._generation:
                        self._generation += 1
                    generation = self._generation
                    self.availability_changed.emit(generation, False)
                    _logger.debug("Audio session subscription unavailable; retrying", exc_info=True)
                    deadline = time.monotonic() + self._retry_delay
                    while not self._stop_event.is_set() and generation == self._generation:
                        try:
                            message = self._messages.get(timeout=max(0, deadline - time.monotonic()))
                        except queue.Empty:
                            break
                        if isinstance(message, str) and message in ("stop", "restart"):
                            break
                    self._retry_delay = min(RETRY_MAX_S, self._retry_delay * 2)
        except Exception:
            self.availability_changed.emit(self._generation, False)
            _logger.exception("Cannot initialize audio session listener")
        finally:
            if initialized:
                comtypes.CoUninitialize()
