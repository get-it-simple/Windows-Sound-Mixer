from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from sound_mixer import __version__
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.entry_widget import EntryWidget
from sound_mixer.overlay.icons import DelayedTooltipButton, load_icon
from sound_mixer.settings.store import SettingsStore

REFRESH_INTERVAL_MS = 1000
GEOMETRY_SAVE_DELAY_MS = 300

BACKGROUND_STYLE = """
#background {
    background-color: rgba(32, 32, 32, 235);
    border-radius: 8px;
}
"""


class _TitleBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_offset = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class OverlayWindow(QWidget):
    visibility_changed = Signal(bool)

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
        self._build_ui()
        self._restore_geometry()

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.timeout.connect(self._save_geometry)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

        self._sync_entry_widgets()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        background = QFrame(self)
        background.setObjectName("background")
        background.setStyleSheet(BACKGROUND_STYLE)
        outer_layout.addWidget(background)

        layout = QVBoxLayout(background)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_title_bar(background))

        self._container = QWidget(background)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(4, 4, 4, 4)
        self._container_layout.setSpacing(2)
        self._container_layout.addStretch(1)

        scroll_area = QScrollArea(background)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self._container)
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll_area)

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
        icon_label.setPixmap(load_icon("volume").pixmap(16, 16))

        name_label = QLabel("Sound Mixer", title_bar)
        version_label = QLabel(f"v{__version__}", title_bar)

        close_button = DelayedTooltipButton(title_bar)
        close_button.setIcon(load_icon("close"))
        close_button.setToolTip("Close")
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(self.close)

        layout = QHBoxLayout(title_bar)
        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(version_label)
        layout.addStretch(1)
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
        self._schedule_geometry_save()
        super().resizeEvent(event)

    def _refresh(self) -> None:
        self._model.refresh()
        self._sync_entry_widgets()

    def refresh_view(self) -> None:
        self._sync_entry_widgets()

    def _sync_entry_widgets(self) -> None:
        entries = self._model.entries

        while len(self._entry_widgets) < len(entries):
            widget = EntryWidget(self._container)
            widget.volume_changed.connect(lambda value, w=widget: self._on_volume_changed(w, value))
            widget.mute_toggled.connect(lambda w=widget: self._on_mute_toggled(w))
            widget.focus_requested.connect(lambda w=widget: self._on_focus_requested(w))
            widget.scrolled.connect(lambda direction, w=widget: self._on_scrolled(w, direction))
            self._container_layout.insertWidget(len(self._entry_widgets), widget)
            self._entry_widgets.append(widget)

        while len(self._entry_widgets) > len(entries):
            widget = self._entry_widgets.pop()
            self._container_layout.removeWidget(widget)
            widget.deleteLater()

        for index, (entry, widget) in enumerate(zip(entries, self._entry_widgets)):
            widget.set_entry(entry, focused=(index == self._model.focused_index))

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
