import sys

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from sound_mixer import __version__
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.entry_widget import EntryWidget
from sound_mixer.overlay.icons import DelayedTooltipButton, load_icon
from sound_mixer.overlay.win_effects import apply_acrylic_effect, get_accent_color
from sound_mixer.settings.store import SettingsStore

REFRESH_INTERVAL_MS = 1000
GEOMETRY_SAVE_DELAY_MS = 300
WARM_UP_HIDE_DELAY_MS = 150

BASE_FONT_PX = 13
BASE_ICON_PX = 16
BASE_TITLE_LOGO_PX = 28
BASE_TITLE_FONT_PX = 17
BASE_VERSION_FONT_PX = 11

MIN_OVERLAY_WIDTH = 200
RESIZE_HANDLE_WIDTH_PX = 6
MAX_VISIBLE_ENTRIES = 6


def background_style(scale: float, accent_color: str, transparent: bool = True) -> str:
    font_px = round(BASE_FONT_PX * scale)
    title_font_px = round(BASE_TITLE_FONT_PX * scale)
    version_font_px = round(BASE_VERSION_FONT_PX * scale)
    control_radius = round(8 * scale)
    entry_radius = round(10 * scale)
    background_color = "rgba(32, 32, 32, 140)" if transparent else "rgb(32, 32, 32)"
    return f"""
#background {{
    background-color: {background_color};
    border-radius: 8px;
    font-size: {font_px}px;
}}
#background QScrollArea, #background QScrollArea > QWidget, #background #entryContainer {{
    background: transparent;
    border: none;
}}
#background #titleName {{
    font-size: {title_font_px}px;
    font-weight: 600;
    color: #f2f2f5;
}}
#background #titleVersion {{
    font-size: {version_font_px}px;
    color: #9a9a9a;
}}
#background #titleBar QToolButton {{
    background: rgba(255, 255, 255, 12);
    border: none;
    border-radius: {control_radius}px;
    padding: {round(6 * scale)}px;
}}
#background #titleBar QToolButton:hover {{
    background: rgba(255, 255, 255, 22);
}}
#background #entryWidget {{
    background: rgba(255, 255, 255, 15);
    border: 1px solid transparent;
    border-radius: {entry_radius}px;
}}
#background #entryWidget[focused="true"] {{
    border: 1px solid {accent_color};
}}
#background #entryWidget QToolButton {{
    background: rgba(0, 0, 0, 70);
    border: none;
    border-radius: {control_radius}px;
    padding: {round(6 * scale)}px;
}}
#background #entryWidget QToolButton:hover {{
    background: rgba(0, 0, 0, 100);
}}
#background #entryWidget QSpinBox {{
    background: rgba(0, 0, 0, 70);
    border: none;
    border-radius: {control_radius}px;
    padding: {round(4 * scale)}px {round(8 * scale)}px;
    color: #f2f2f5;
}}
#background QScrollBar:vertical {{
    width: {round(8 * scale)}px;
    background: transparent;
    margin: 2px;
}}
#background QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 60);
    border-radius: {round(4 * scale)}px;
    min-height: 24px;
}}
#background QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 90);
}}
#background QScrollBar::add-line:vertical, #background QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
    background: none;
}}
#background QScrollBar::add-page:vertical, #background QScrollBar::sub-page:vertical {{
    background: none;
}}
"""


class _ResizeHandle(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self._drag_start_pos: int | None = None
        self._start_width = 0

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            self._drag_start_pos = event.globalPosition().toPoint().x()
            self._start_width = window.width()
            window._pause_refresh()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint().x() - self._drag_start_pos
            window = self.window()
            new_width = max(MIN_OVERLAY_WIDTH, self._start_width + delta)
            window.resize(new_width, window.height())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start_pos = None
        self.window()._resume_refresh()
        super().mouseReleaseEvent(event)


class _TitleBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_offset = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            self.window()._pause_refresh()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        self.window()._resume_refresh()
        super().mouseReleaseEvent(event)


class OverlayWindow(QWidget):
    visibility_changed = Signal(bool)
    settings_requested = Signal()

    def __init__(self, model: MixerModel, settings: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._settings = settings
        self._entry_widgets: list[EntryWidget] = []

        self.setWindowTitle("Sound Mixer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumWidth(MIN_OVERLAY_WIDTH)
        self._accent_color = get_accent_color()
        self._build_ui()
        self._restore_geometry()
        self.apply_scale()
        apply_acrylic_effect(self, self._settings.get_transparency_enabled())

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.timeout.connect(self._save_geometry)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

        self._sync_entry_widgets()

        if sys.platform == "win32":
            self._warm_up_acrylic()

    def _warm_up_acrylic(self) -> None:
        visible_on_start = self._settings.get_overlay_geometry()["visible_on_start"]
        self.show()
        if not visible_on_start:
            QTimer.singleShot(WARM_UP_HIDE_DELAY_MS, self.close)

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        background = QFrame(self)
        background.setObjectName("background")
        outer_layout.addWidget(background)
        self._background = background

        layout = QVBoxLayout(background)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title_bar = self._build_title_bar(background)
        layout.addWidget(title_bar)

        self._container = QWidget(background)
        self._container.setObjectName("entryContainer")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.addStretch(1)

        scroll_area = QScrollArea(background)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self._container)
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll_area)

        self._title_bar = title_bar
        self._resize_handle_width = _ResizeHandle(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def _build_title_bar(self, parent: QWidget) -> QWidget:
        title_bar = _TitleBar(parent)
        title_bar.setObjectName("titleBar")

        icon_label = QLabel(title_bar)
        self._title_icon_label = icon_label

        name_label = QLabel("Sound Mixer", title_bar)
        name_label.setObjectName("titleName")
        version_label = QLabel(f"v{__version__}", title_bar)
        version_label.setObjectName("titleVersion")

        title_text_layout = QVBoxLayout()
        title_text_layout.setContentsMargins(0, 0, 0, 0)
        title_text_layout.setSpacing(0)
        title_text_layout.addWidget(name_label)
        title_text_layout.addWidget(version_label)

        settings_button = DelayedTooltipButton(title_bar)
        settings_button.setIcon(load_icon("settings"))
        settings_button.setToolTip("Settings")
        settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        settings_button.clicked.connect(self.settings_requested.emit)
        self._settings_button = settings_button

        close_button = DelayedTooltipButton(title_bar)
        close_button.setIcon(load_icon("close"))
        close_button.setToolTip("Close")
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(self.close)
        self._close_button = close_button

        layout = QHBoxLayout(title_bar)
        layout.addWidget(icon_label)
        layout.addLayout(title_text_layout)
        layout.addStretch(1)
        layout.addWidget(settings_button)
        layout.addWidget(close_button)
        return title_bar

    def _restore_geometry(self) -> None:
        geometry = self._settings.get_overlay_geometry()
        self.setGeometry(geometry["x"], geometry["y"], geometry["width"], geometry["height"])

    def _save_geometry(self) -> None:
        geometry = self.geometry()
        self._settings.set_overlay_geometry(geometry.x(), geometry.y(), geometry.width(), geometry.height())

    def _schedule_geometry_save(self) -> None:
        self._geometry_save_timer.start(GEOMETRY_SAVE_DELAY_MS)

    def moveEvent(self, event) -> None:
        self._schedule_geometry_save()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        title_bar_height = self._title_bar.height()
        self._resize_handle_width.setGeometry(
            self.width() - RESIZE_HANDLE_WIDTH_PX, title_bar_height, RESIZE_HANDLE_WIDTH_PX, self.height() - title_bar_height
        )
        self._resize_handle_width.raise_()

        self._schedule_geometry_save()
        super().resizeEvent(event)

    def _update_window_height(self) -> None:
        if not self._entry_widgets:
            return

        entry_height = max(widget.sizeHint().height() for widget in self._entry_widgets)
        margins = self._container_layout.contentsMargins()
        visible_count = min(len(self._entry_widgets), MAX_VISIBLE_ENTRIES)
        container_height = (
            margins.top() + margins.bottom() + visible_count * entry_height
            + max(0, visible_count - 1) * self._container_layout.spacing()
        )
        title_bar_height = self._title_bar.sizeHint().height()
        self.setFixedHeight(title_bar_height + container_height)

    def _refresh(self) -> None:
        self._model.refresh()
        self._sync_entry_widgets()

    def _pause_refresh(self) -> None:
        self._refresh_timer.stop()

    def _resume_refresh(self) -> None:
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

    def refresh_view(self) -> None:
        self._sync_entry_widgets()

    def apply_scale(self) -> None:
        scale = self._settings.get_ui_scale()
        transparent = self._settings.get_transparency_enabled()
        self._background.setStyleSheet(background_style(scale, self._accent_color, transparent))

        icon_px = round(BASE_ICON_PX * scale)
        logo_px = round(BASE_TITLE_LOGO_PX * scale)
        self._title_icon_label.setPixmap(load_icon("logo").pixmap(logo_px, logo_px))
        self._settings_button.setIconSize(QSize(icon_px, icon_px))
        self._close_button.setIconSize(QSize(icon_px, icon_px))

        title_bar_layout = self._title_bar.layout()
        margin = round(12 * scale)
        spacing = round(10 * scale)
        title_bar_layout.setContentsMargins(margin, margin, margin, margin)
        title_bar_layout.setSpacing(spacing)

        container_margin = round(8 * scale)
        self._container_layout.setContentsMargins(container_margin, container_margin, container_margin, container_margin)
        self._container_layout.setSpacing(container_margin)

        for widget in self._entry_widgets:
            widget.apply_scale(scale)

        self._update_window_height()

    def _sync_entry_widgets(self) -> None:
        entries = self._model.entries

        while len(self._entry_widgets) < len(entries):
            widget = EntryWidget(self._container)
            widget.volume_changed.connect(lambda value, w=widget: self._on_volume_changed(w, value))
            widget.mute_toggled.connect(lambda w=widget: self._on_mute_toggled(w))
            widget.focus_requested.connect(lambda w=widget: self._on_focus_requested(w))
            widget.scrolled.connect(lambda direction, w=widget: self._on_scrolled(w, direction))
            widget.apply_scale(self._settings.get_ui_scale())
            self._container_layout.insertWidget(len(self._entry_widgets), widget)
            self._entry_widgets.append(widget)

        while len(self._entry_widgets) > len(entries):
            widget = self._entry_widgets.pop()
            self._container_layout.removeWidget(widget)
            widget.deleteLater()

        for index, (entry, widget) in enumerate(zip(entries, self._entry_widgets)):
            widget.set_entry(entry, focused=(index == self._model.focused_index))

        self._update_window_height()

    def _on_volume_changed(self, widget: EntryWidget, value: float) -> None:
        index = self._entry_widgets.index(widget)
        self._model.focused_index = index
        self._model.set_volume(value, index)
        self._sync_entry_widgets()

    def _on_mute_toggled(self, widget: EntryWidget) -> None:
        index = self._entry_widgets.index(widget)
        self._model.focused_index = index
        self._model.toggle_mute(index)
        self._sync_entry_widgets()

    def _on_focus_requested(self, widget: EntryWidget) -> None:
        index = self._entry_widgets.index(widget)
        self._model.focused_index = index
        self._sync_entry_widgets()

    def _on_scrolled(self, widget: EntryWidget, direction: int) -> None:
        index = self._entry_widgets.index(widget)
        self._model.focused_index = index
        self._model.adjust_volume(direction * self._settings.get_scroll_step(), index)
        self._sync_entry_widgets()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Up:
            self._model.move_focus(-1)
        elif key == Qt.Key.Key_Down:
            self._model.move_focus(1)
        elif key == Qt.Key.Key_Left:
            self._model.adjust_volume(-self._settings.get_arrow_step())
        elif key == Qt.Key.Key_Right:
            self._model.adjust_volume(self._settings.get_arrow_step())
        else:
            super().keyPressEvent(event)
            return
        self._sync_entry_widgets()
