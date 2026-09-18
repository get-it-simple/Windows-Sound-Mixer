from PySide6.QtCore import QEvent, QObject, QTimer, Signal

from sound_mixer.settings.schema import MAX_UI_SCALE


class ScaleLimit(QObject):
    changed = Signal()

    def __init__(self, window) -> None:
        super().__init__(window)
        self._window = window
        self._maximum = self.maximum_percent()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)
        window.installEventFilter(self)

    def maximum_percent(self) -> int:
        ratio = max(1.0, self._window.devicePixelRatioF())
        return max(1, int(MAX_UI_SCALE * 100 / ratio))

    def constrain(self, scale: float) -> float:
        return min(scale, self.maximum_percent() / 100)

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.Show, QEvent.Type.DevicePixelRatioChange):
            self._timer.start(0)
        return super().eventFilter(watched, event)

    def _refresh(self) -> None:
        maximum = self.maximum_percent()
        if maximum != self._maximum:
            self._maximum = maximum
            self.changed.emit()
