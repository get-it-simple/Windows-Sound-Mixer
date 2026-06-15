from PySide6.QtCore import QEvent, QFileInfo, QPoint, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileIconProvider, QToolButton, QToolTip

from sound_mixer.paths import resource_path

ICON_NAMES = ("volume", "muted", "settings", "pin", "close", "toggle_on", "toggle_off", "app", "logo")


def icon_path(name: str) -> str:
    return str(resource_path("resources", "icons", f"{name}.svg"))


def load_icon(name: str) -> QIcon:
    return QIcon(icon_path(name))


def load_app_icon(exe_path: str) -> QIcon:
    if exe_path and QFileInfo(exe_path).exists():
        icon = QFileIconProvider().icon(QFileInfo(exe_path))
        if not icon.isNull():
            return icon
    return load_icon("app")


def toggle_switch_style(object_name: str) -> str:
    off_path = icon_path("toggle_off").replace("\\", "/")
    on_path = icon_path("toggle_on").replace("\\", "/")
    return f"""
QCheckBox#{object_name}::indicator {{
    width: 36px;
    height: 20px;
    image: url({off_path});
}}
QCheckBox#{object_name}::indicator:checked {{
    image: url({on_path});
}}
"""


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
