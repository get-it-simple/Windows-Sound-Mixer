from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractSpinBox, QFrame, QHBoxLayout, QLabel, QSlider, QSpinBox, QVBoxLayout, QWidget

from sound_mixer.i18n import t
from sound_mixer.mixer.model import MixerEntry
from sound_mixer.overlay.icons import DelayedTooltipButton, load_app_icon, load_icon

BASE_ICON_PX = 18
BASE_APP_ICON_PX = 32
BASE_SLIDER_HEIGHT_PX = 10
BASE_FONT_PX = 13
BASE_MARGIN_PX = 8
BASE_SPACING_PX = 8


def slider_style(scale: float, accent_color: str) -> str:
    groove_height = max(1, round(2 * scale))
    handle_size = round(9 * scale)
    if (handle_size - groove_height) % 2:
        handle_size += 1
    margin = (handle_size - groove_height) // 2
    return f"""
QSlider::groove:horizontal {{
    height: {groove_height}px;
    background: #555555;
    border-radius: {groove_height // 2}px;
}}
QSlider::sub-page:horizontal {{
    height: {groove_height}px;
    background: {accent_color};
    border-radius: {groove_height // 2}px;
}}
QSlider::handle:horizontal {{
    width: {handle_size}px;
    height: {handle_size}px;
    margin: -{margin}px 0;
    background: #ffffff;
    border-radius: {handle_size // 2}px;
}}
"""


class EntryWidget(QFrame):
    volume_changed = Signal(float)
    mute_toggled = Signal()
    focus_requested = Signal()
    scrolled = Signal(int)
    ignore_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("entryWidget")
        self._current_icon = QIcon()
        self._app_icon_px = BASE_APP_ICON_PX
        self._is_master = False

        self._mute_button = DelayedTooltipButton(self)
        self._mute_button.setToolTip(t("mute_unmute_tooltip"))
        self._mute_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._mute_button.clicked.connect(self._on_mute_clicked)

        self._icon_container = QWidget(self)
        self._icon_container.setFixedSize(self._app_icon_px, self._app_icon_px)

        self._icon_label = QLabel(self._icon_container)
        self._icon_label.setGeometry(0, 0, self._app_icon_px, self._app_icon_px)
        self._icon_label.setScaledContents(True)

        self._hide_button = DelayedTooltipButton(self._icon_container)
        self._hide_button.setIcon(load_icon("hide"))
        self._hide_button.setToolTip(t("ignore_tooltip"))
        self._hide_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._hide_button.clicked.connect(self._on_hide_clicked)
        self._hide_button.setGeometry(0, 0, self._app_icon_px, self._app_icon_px)
        self._hide_button.raise_()
        self._hide_button.hide()

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setRange(0, 100)
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.valueChanged.connect(self._on_slider_changed)

        self._process_name_label = QLabel("", self)
        self._process_name_label.setObjectName("processNameLabel")
        self._process_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._slider_column = QWidget(self)
        slider_col_layout = QVBoxLayout(self._slider_column)
        slider_col_layout.setContentsMargins(0, 0, 0, 0)
        slider_col_layout.setSpacing(4)
        slider_col_layout.addWidget(self._slider)
        slider_col_layout.addWidget(self._process_name_label)

        self._volume_spinbox = QSpinBox(self)
        self._volume_spinbox.setRange(0, 100)
        self._volume_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._volume_spinbox.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._volume_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._volume_spinbox.valueChanged.connect(self._on_spinbox_changed)

        self._slider.installEventFilter(self)
        self._volume_spinbox.installEventFilter(self)

        layout = QHBoxLayout(self)
        layout.addWidget(self._icon_container)
        layout.addWidget(self._mute_button)
        layout.addWidget(self._volume_spinbox)
        layout.addWidget(self._slider_column, 1)

    def apply_scale(self, scale: float, accent_color: str = "#3a96dd") -> None:
        icon_px = round(BASE_ICON_PX * scale)
        self._mute_button.setIconSize(QSize(icon_px, icon_px))
        self._hide_button.setIconSize(QSize(icon_px, icon_px))
        self._slider.setStyleSheet(slider_style(scale, accent_color))
        self._slider.setMinimumHeight(round(BASE_SLIDER_HEIGHT_PX * scale))

        font_px = round(BASE_FONT_PX * scale)

        font = self._volume_spinbox.font()
        font.setPixelSize(font_px)
        self._volume_spinbox.setFont(font)
        self._volume_spinbox.setFixedWidth(self._volume_spinbox.minimumSizeHint().width())

        name_font = self._process_name_label.font()
        name_font.setPixelSize(font_px)
        self._process_name_label.setFont(name_font)

        self._slider_column.layout().setSpacing(round(4 * scale))

        self._app_icon_px = round(BASE_APP_ICON_PX * scale)
        self._icon_container.setFixedSize(self._app_icon_px, self._app_icon_px)
        self._icon_label.setGeometry(0, 0, self._app_icon_px, self._app_icon_px)
        self._hide_button.setGeometry(0, 0, self._app_icon_px, self._app_icon_px)
        self._update_icon_pixmap()

        layout = self.layout()
        margin = round(BASE_MARGIN_PX * scale)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(round(BASE_SPACING_PX * scale))

    def set_entry(self, entry: MixerEntry, focused: bool) -> None:
        self._mute_button.setIcon(load_icon("muted" if entry.muted else "volume"))
        self._is_master = entry.is_master

        if entry.is_master:
            self._icon_label.hide()
        else:
            self._icon_label.setToolTip(entry.display_name)
            self._current_icon = load_app_icon(entry.icon_path)
            self._update_icon_pixmap()
            self._icon_label.show()
        self._icon_container.show()

        self._process_name_label.setText(entry.display_name)

        self.setToolTip(entry.display_name)
        self._slider.setToolTip(entry.display_name)
        self._volume_spinbox.setToolTip(entry.display_name)

        value = round(entry.volume * 100)

        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)

        self._volume_spinbox.blockSignals(True)
        self._volume_spinbox.setValue(value)
        self._volume_spinbox.blockSignals(False)

        self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)

        if self.underMouse() and not self._is_master:
            self._hide_button.show()
        else:
            self._hide_button.hide()

    def set_ignore_tooltip(self, text: str) -> None:
        self._hide_button.setToolTip(text)

    def retranslate(self) -> None:
        self._mute_button.setToolTip(t("mute_unmute_tooltip"))
        self._hide_button.setToolTip(t("ignore_tooltip"))

    def _on_slider_changed(self, value: int) -> None:
        self.focus_requested.emit()
        self.volume_changed.emit(value / 100)

    def _on_spinbox_changed(self, value: int) -> None:
        self.focus_requested.emit()
        self.volume_changed.emit(value / 100)

    def _on_mute_clicked(self) -> None:
        self.focus_requested.emit()
        self.mute_toggled.emit()

    def _on_hide_clicked(self) -> None:
        self.focus_requested.emit()
        self.ignore_requested.emit()

    def mousePressEvent(self, event) -> None:
        self.focus_requested.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        if not self._is_master:
            self._hide_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hide_button.hide()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        if not delta:
            return
        self.focus_requested.emit()
        self.scrolled.emit(1 if delta > 0 else -1)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Wheel and watched in (self._slider, self._volume_spinbox):
            self.wheelEvent(event)
            return True
        return super().eventFilter(watched, event)

    def _update_icon_pixmap(self) -> None:
        if not self._current_icon.isNull():
            self._icon_label.setPixmap(self._current_icon.pixmap(self._app_icon_px, self._app_icon_px))
