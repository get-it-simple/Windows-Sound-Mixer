from PySide6.QtCore import QEvent, QPoint, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolButton, QToolTip

from sound_mixer.paths import resource_path

ICON_NAMES = ("volume", "muted", "settings", "pin", "close")


def icon_path(name: str) -> str:
    return str(resource_path("resources", "icons", f"{name}.svg"))


def load_icon(name: str) -> QIcon:
    return QIcon(icon_path(name))


class DelayedTooltipButton(QToolButton):
    def __init__(self, parent=None, tooltip_delay_ms: int = 500) -> None:
        super().__init__(parent)
        self._tooltip_delay_ms = tooltip_delay_ms

    def set_tooltip_delay_ms(self, delay_ms: int) -> None:
        self._tooltip_delay_ms = delay_ms

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            global_pos = event.globalPos()
            QTimer.singleShot(self._tooltip_delay_ms, lambda: self._show_tooltip(global_pos))
            return True
        return super().event(event)

    def _show_tooltip(self, global_pos: QPoint) -> None:
        if self.underMouse() and self.toolTip():
            QToolTip.showText(global_pos, self.toolTip(), self)
