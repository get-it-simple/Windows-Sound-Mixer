from time import perf_counter

from PySide6.QtCore import QObject, QTimer, Qt, Slot

from sound_mixer.audio.master_listener import MasterAudioListener

FALLBACK_INTERVAL_MS = 5000
UPDATE_DELAY_MS = 500


class MasterAudioSync(QObject):
    def __init__(self, model, backend, refresh_views, on_device_changed, parent=None, listener=None) -> None:
        super().__init__(parent)
        self._model = model
        self._backend = backend
        self._refresh_views = refresh_views
        self._on_device_changed = on_device_changed
        self._visible = False
        self._available = False
        self._pending_state = None
        self._read_requested = False
        self._listener = listener if listener is not None else MasterAudioListener(self)
        getattr(self._listener, "state_observed", self._listener.state_changed).connect(self._queue_state)
        self._listener.device_changed.connect(self._device_changed)
        self._listener.availability_changed.connect(self._set_available)
        self._timer = QTimer(self)
        self._timer.setInterval(FALLBACK_INTERVAL_MS)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._poll)
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._update_timer.setInterval(UPDATE_DELAY_MS)
        self._update_timer.timeout.connect(self._flush_update)

    def start(self) -> None:
        self._model.set_master_refresh_scheduler(self._request_read)
        self._listener.start()

    def stop(self) -> None:
        self._timer.stop()
        self._cancel_update()
        self._model.set_master_refresh_scheduler(None)
        self._listener.stop()

    @Slot(bool)
    def set_overlay_visible(self, visible: bool) -> None:
        self._visible = visible
        self._sync_timer()

    @Slot(bool)
    def _set_available(self, available: bool) -> None:
        self._available = available
        self._sync_timer()

    def _sync_timer(self) -> None:
        if self._visible and not self._available:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    @Slot(float, bool)
    @Slot(float, bool, float)
    def _queue_state(self, volume: float, muted: bool, timestamp: float | None = None) -> None:
        self._pending_state = (volume, muted, perf_counter() if timestamp is None else timestamp)
        self._update_timer.start()

    def _request_read(self) -> None:
        self._read_requested = True
        self._update_timer.start()

    def _cancel_update(self) -> None:
        self._update_timer.stop()
        self._pending_state = None
        self._read_requested = False

    @Slot()
    def _flush_update(self) -> None:
        state, read_requested = self._pending_state, self._read_requested
        self._cancel_update()
        if read_requested and self._model.refresh_master():
            self._refresh_views()
        elif state is not None and self._model.observe_master_state(*state):
            self._refresh_views()

    @Slot()
    def _device_changed(self) -> None:
        self._cancel_update()
        self._backend.invalidate_master_endpoint()
        self._model.restore_master_profile()
        self._on_device_changed()

    @Slot()
    def _poll(self) -> None:
        if self._visible and not self._available and self._model.refresh_master():
            self._refresh_views()
