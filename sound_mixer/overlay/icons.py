from PySide6.QtCore import QEvent, QFileInfo, QPoint, QTimer
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import QFileIconProvider, QToolButton, QToolTip

from sound_mixer.paths import resource_path

ICON_NAMES = ("volume", "muted", "settings", "help", "pin", "close", "toggle_on", "toggle_off", "app", "logo", "hide", "arrow_up", "dropdown_arrow", "trash")

ROTATED_ICON_PX = 64
TOGGLE_SWITCH_WIDTH_PX = 36
TOGGLE_SWITCH_HEIGHT_PX = 20

_icon_cache: dict[tuple[str, int], QIcon] = {}
_app_icon_cache: dict[str, QIcon] = {}
_icon_provider: QFileIconProvider | None = None


def clear_caches() -> None:
    global _icon_provider
    _icon_cache.clear()
    _app_icon_cache.clear()
    _icon_provider = None


def icon_path(name: str) -> str:
    return str(resource_path("resources", "icons", f"{name}.svg"))


def load_icon(name: str, rotation: int = 0) -> QIcon:
    key = (name, rotation % 360)
    if key not in _icon_cache:
        icon = QIcon(icon_path(name))
        if key[1]:
            pixmap = icon.pixmap(ROTATED_ICON_PX, ROTATED_ICON_PX)
            icon = QIcon(pixmap.transformed(QTransform().rotate(key[1])))
        _icon_cache[key] = icon
    return _icon_cache[key]


def _provider() -> QFileIconProvider:
    global _icon_provider
    if _icon_provider is None:
        _icon_provider = QFileIconProvider()
    return _icon_provider


def load_app_icon(exe_path: str) -> QIcon:
    if exe_path not in _app_icon_cache:
        _app_icon_cache[exe_path] = _extract_app_icon(exe_path)
    return _app_icon_cache[exe_path]


def _extract_app_icon(exe_path: str) -> QIcon:
    if exe_path and QFileInfo(exe_path).exists():
        icon = _provider().icon(QFileInfo(exe_path))
        if not icon.isNull():
            return icon
    return load_icon("app")


def bordered_input_style(object_name: str) -> str:
    return f"""
QFrame#{object_name} {{
    border: 1px solid #3f3f42;
    border-radius: 4px;
    background: #2d2d30;
}}
QFrame#{object_name}:focus {{
    border-color: #6b6a7c;
}}
"""


def toggle_switch_style(object_name: str) -> str:
    off_path = icon_path("toggle_off").replace("\\", "/")
    on_path = icon_path("toggle_on").replace("\\", "/")
    return f"""
QCheckBox#{object_name}::indicator {{
    width: {TOGGLE_SWITCH_WIDTH_PX}px;
    height: {TOGGLE_SWITCH_HEIGHT_PX}px;
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
