from PySide6.QtCore import QObject, QTimer, Slot

from sound_mixer.audio.process_exit_listener import ProcessExitListener
from sound_mixer.audio.session_listener import AudioSessionListener


UPDATE_DELAY_MS = 50
VISIBLE_FALLBACK_MS = 5000
HIDDEN_FALLBACK_MS = 30000


class SessionAudioSync(QObject):
    def __init__(self, model, backend, refresh_views, parent=None, listener=None, process_listener=None):
        super().__init__(parent)
        self._model = model
        self._backend = backend
        self._refresh_views = refresh_views
        self._listener = listener if listener is not None else AudioSessionListener(self)
        self._process_listener = process_listener if process_listener is not None else ProcessExitListener(self)
        self._listener.event_received.connect(self._on_event)
        self._listener.availability_changed.connect(self._set_available)
        self._process_listener.process_exited.connect(self.request_refresh)
        self._running = False
        self._available = False
        self._visible = False
        self._topology = False
        self._pending = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(UPDATE_DELAY_MS)
        self._timer.timeout.connect(self._flush)
        self._fallback = QTimer(self)
        self._fallback.timeout.connect(self.request_refresh)
        self._names_timer = QTimer(self)
        self._names_timer.setSingleShot(True)
        self._names_timer.timeout.connect(self._refresh_names)

    def start(self):
        self._running = True
        self._listener.start()
        self._sync_fallback()
        self.request_refresh()

    def stop(self):
        self._running = False
        self._timer.stop()
        self._fallback.stop()
        self._names_timer.stop()
        self._pending.clear()
        self._process_listener.stop()
        self._listener.stop()

    def set_visible(self, visible):
        self._visible = bool(visible)
        set_names_visible = getattr(self._backend, "set_names_visible", None)
        if set_names_visible is not None:
            set_names_visible(self._visible)
        self._sync_fallback()
        self._schedule_names()

    def _sync_fallback(self):
        if not self._running or self._available:
            self._fallback.stop()
        else:
            interval = VISIBLE_FALLBACK_MS if self._visible else HIDDEN_FALLBACK_MS
            if not self._fallback.isActive() or self._fallback.interval() != interval:
                self._fallback.start(interval)

    @Slot(int, bool)
    def _set_available(self, generation, available):
        if not self._running or generation != self._listener.generation:
            return
        self._available = available
        self._sync_fallback()
        self.request_refresh()

    @Slot()
    def request_refresh(self):
        if self._running:
            self._topology = True
            self._schedule()

    def _schedule(self):
        if not self._timer.isActive():
            self._timer.start()

    @Slot(object)
    def _on_event(self, event):
        if not self._running or event.generation != self._listener.generation:
            return
        if event.kind == "volume":
            self._pending[event.session_id] = event
        else:
            if event.kind == "removed":
                exclude = getattr(self._backend, "exclude_session", None)
                if exclude is not None:
                    exclude(event.session_id)
            self._topology = True
        self._schedule()

    def _flush(self):
        if not self._running:
            return
        pending, topology = self._pending, self._topology
        self._pending, self._topology = {}, False
        changed = topology
        if topology:
            self._model.refresh(include_master=False)
            self._listener.rescan()
            self._process_listener.sync(self._model.session_pids)
        for event in sorted(pending.values(), key=lambda item: item.timestamp):
            if event.generation == self._listener.generation:
                changed |= self._model.apply_session_state(event)
        if changed:
            self._model.refresh_master_after_app_event()
            self._refresh_views()
        self._schedule_names()

    @Slot()
    def device_changed(self):
        if not self._running:
            return
        self._pending.clear()
        self._available = False
        reset = getattr(self._backend, "reset_sessions", None)
        if reset is not None:
            reset()
        self._listener.restart()
        self._sync_fallback()
        self.request_refresh()

    def _schedule_names(self):
        self._names_timer.stop()
        if not self._running or not self._visible:
            return
        delay = getattr(self._backend, "name_retry_delay", lambda: None)()
        if delay is not None:
            self._names_timer.start(max(50, round(delay * 1000)))

    def _refresh_names(self):
        if self._visible and self._running:
            if self._backend.refresh_names():
                self._model.sync_names()
                self._refresh_views()
            self._schedule_names()
