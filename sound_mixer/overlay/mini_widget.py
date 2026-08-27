from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from sound_mixer.i18n import t
from sound_mixer.mixer.model import MixerEntry, MixerModel
from sound_mixer.overlay.icons import DelayedTooltipButton, load_app_icon, load_icon
from sound_mixer.settings.store import SettingsStore

REFRESH_INTERVAL_MS = 1000
POSITION_SAVE_DELAY_MS = 300
PIN_HIDE_DELAY_MS = 600
MIN_VISIBLE_PX = 48
BASE_APP_ICON_PX = 32
BASE_FONT_PX = 13
BASE_ICON_PX = 16
BASE_MARGIN_PX = 8
BASE_SPACING_PX = 8
MUTED_OPACITY = 0.45
MUTED_ICON_SCALE = 0.75


class MiniEntryWidget(QFrame):
    scrolled = Signal(int)
    mute_toggled = Signal()
    focus_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("miniEntryWidget")
        self.key = ""
        self._entry: MixerEntry | None = None
        self._scale = 1.0
        self._volume_below_icon = False

        self._volume_label = QLabel(self)
        self._volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._volume_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._icon_effect = QGraphicsOpacityEffect(self._icon_label)
        self._icon_label.setGraphicsEffect(self._icon_effect)

        self._icon_container = QWidget(self)
        self._icon_label.setParent(self._icon_container)
        self._muted_icon_label = QLabel(self._icon_container)
        self._muted_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._muted_icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._muted_icon_label.hide()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._volume_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_container, 0, Qt.AlignmentFlag.AlignCenter)

        self.apply_scale(1.0)

    def set_volume_below_icon(self, below: bool) -> None:
        below = bool(below)
        if below == self._volume_below_icon:
            return
        layout = self.layout()
        layout.removeWidget(self._volume_label)
        layout.insertWidget(1 if below else 0, self._volume_label, 0, Qt.AlignmentFlag.AlignCenter)
        self._volume_below_icon = below

    def apply_scale(self, scale: float) -> None:
        self._scale = scale
        icon_px = round(BASE_APP_ICON_PX * scale)
        margin = round(BASE_MARGIN_PX * scale)
        spacing = round(BASE_SPACING_PX * scale)
        font = self._volume_label.font()
        font.setPixelSize(round(BASE_FONT_PX * scale))
        self._volume_label.setFont(font)
        self._icon_container.setFixedSize(icon_px, icon_px)
        self._icon_label.setGeometry(0, 0, icon_px, icon_px)
        self._muted_icon_label.setGeometry(0, 0, icon_px, icon_px)
        muted_icon_px = round(icon_px * MUTED_ICON_SCALE)
        self._muted_icon_label.setPixmap(load_icon("muted").pixmap(muted_icon_px, muted_icon_px))
        self._muted_icon_label.raise_()
        layout = self.layout()
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(spacing)
        text_height = self._volume_label.fontMetrics().height()
        extent = max(icon_px, self._volume_label.sizeHint().width()) + 2 * margin
        self.setFixedSize(extent, text_height + icon_px + spacing + 2 * margin)
        self._update_icon()

    def set_entry(self, entry: MixerEntry) -> None:
        self._entry = entry
        self.key = entry.key
        self._volume_label.setText(f"{round(entry.volume * 100)}%")
        self._icon_effect.setOpacity(MUTED_OPACITY if entry.muted else 1.0)
        self._muted_icon_label.setVisible(entry.muted)
        self.setToolTip(entry.display_name)
        self._volume_label.setToolTip(entry.display_name)
        self._icon_label.setToolTip(entry.display_name)
        self._muted_icon_label.setToolTip(entry.display_name)
        self._update_icon()

    def _update_icon(self) -> None:
        if self._entry is None:
            return
        icon_px = round(BASE_APP_ICON_PX * self._scale)
        self._icon_label.setPixmap(load_app_icon(self._entry.icon_path).pixmap(icon_px, icon_px))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.focus_requested.emit()
        if event.button() == Qt.MouseButton.LeftButton:
            self.mute_toggled.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        if not delta:
            return
        self.focus_requested.emit()
        self.scrolled.emit(1 if delta > 0 else -1)
        event.accept()


class PinDragButton(DelayedTooltipButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None

    def is_dragging(self) -> bool:
        return self._drag_offset is not None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.window().finish_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MiniWidget(QWidget):
    model_changed = Signal()

    def __init__(self, model: MixerModel, settings: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._settings = settings
        self._enabled = False
        self._entries: dict[str, MiniEntryWidget] = {}
        self._pin_below_content: bool | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "QWidget, QFrame { background: transparent; border: none; }"
            "QToolButton { background: transparent; border: none; padding: 4px; }"
            "QToolButton:hover { background: rgba(255, 255, 255, 24); border-radius: 6px; }"
            "QLabel { color: #f2f2f5; background: transparent; }"
        )

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._pin_row = QWidget(self)
        pin_layout = QHBoxLayout(self._pin_row)
        pin_layout.setContentsMargins(0, 0, 0, 0)
        pin_layout.addStretch(1)
        self._pin_button = PinDragButton(self._pin_row)
        self._pin_button.setIcon(load_icon("pin"))
        self._pin_button.setToolTip(t("mini_pin_tooltip"))
        self._pin_button.set_tooltip_delay_ms(self._settings.get_tooltip_delay_ms())
        self._pin_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._pin_button.hide()
        pin_layout.addWidget(self._pin_button)
        pin_layout.addStretch(1)
        self._outer_layout.addWidget(self._pin_row)

        self._content = QWidget(self)
        self._content.setObjectName("miniWidgetContent")
        self._content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._content.setStyleSheet("QWidget#miniWidgetContent { background: rgba(0, 0, 0, 51); }")
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.addWidget(self._content)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._position_save_timer = QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.timeout.connect(self._save_position)
        self._pin_hide_timer = QTimer(self)
        self._pin_hide_timer.setSingleShot(True)
        self._pin_hide_timer.timeout.connect(self._hide_pin_if_idle)

        position = self._settings.get_mini_widget_position()
        self.move(position["x"], position["y"])
        self.apply_scale()

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool, persist: bool = True) -> None:
        enabled = bool(enabled)
        self._enabled = enabled
        if persist and self._settings.get_mini_widget_enabled() != enabled:
            self._settings.set_mini_widget_enabled(enabled)
        if enabled:
            self._refresh_timer.start(REFRESH_INTERVAL_MS)
            self._refresh()
        else:
            self._refresh_timer.stop()
            self.hide()

    def sync_from_settings(self) -> None:
        self.apply_scale()
        self.set_enabled(self._settings.get_mini_widget_enabled(), persist=False)

    def stop(self) -> None:
        self._refresh_timer.stop()
        self._position_save_timer.stop()
        self._pin_hide_timer.stop()
        self._save_position()

    def _refresh(self) -> None:
        try:
            self._model.refresh()
        except Exception:
            return
        self.refresh_view()
        self.model_changed.emit()

    def refresh_view(self) -> None:
        if not self._enabled:
            self.hide()
            return

        entries = [entry for entry in self._model.entries if not entry.is_master]
        active_keys = {entry.key for entry in entries}
        for key in list(self._entries):
            if key not in active_keys:
                widget = self._entries.pop(key)
                self._grid.removeWidget(widget)
                widget.deleteLater()

        ordered_widgets = []
        for entry in entries:
            widget = self._entries.get(entry.key)
            if widget is None:
                widget = MiniEntryWidget(self._content)
                widget.focus_requested.connect(lambda w=widget: self._model.focus_key(w.key))
                widget.scrolled.connect(lambda direction, w=widget: self._on_scrolled(w.key, direction))
                widget.mute_toggled.connect(lambda w=widget: self._on_mute_toggled(w.key))
                widget.apply_scale(self._settings.get_mini_widget_scale())
                widget.set_volume_below_icon(bool(self._pin_below_content))
                self._entries[entry.key] = widget
            widget.set_entry(entry)
            ordered_widgets.append(widget)

        if not ordered_widgets:
            self.hide()
            return

        self._layout_entries(ordered_widgets)
        self._ensure_on_screen()
        if not self.isVisible():
            self.show()

    def _layout_entries(self, widgets: list[MiniEntryWidget]) -> None:
        while self._grid.count():
            self._grid.takeAt(0)

        spacing = round(BASE_SPACING_PX * self._settings.get_mini_widget_scale())
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)
        cell_width = max(widget.width() for widget in widgets)
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        available_width = screen.availableGeometry().width() if screen is not None else cell_width
        max_columns = max(1, (available_width + spacing) // (cell_width + spacing))
        columns = min(len(widgets), max_columns)

        for index, widget in enumerate(widgets):
            self._grid.addWidget(widget, index // columns, index % columns, Qt.AlignmentFlag.AlignCenter)

        self._content.adjustSize()
        content_hint = self._grid.sizeHint()
        self._content.setFixedSize(content_hint)
        self._pin_row.setFixedWidth(content_hint.width())
        width = max(content_hint.width(), self._pin_row.sizeHint().width())
        self.setFixedSize(width, self._pin_row.height() + content_hint.height())
        self._update_pin_position()

    def _on_scrolled(self, key: str, direction: int) -> None:
        self._model.adjust_volume_by_key(key, direction * self._settings.get_scroll_step())
        self.refresh_view()
        self.model_changed.emit()

    def _on_mute_toggled(self, key: str) -> None:
        self._model.toggle_mute_by_key(key)
        self.refresh_view()
        self.model_changed.emit()

    def apply_scale(self) -> None:
        scale = self._settings.get_mini_widget_scale()
        icon_px = round(BASE_ICON_PX * scale)
        self._pin_button.setIconSize(QSize(icon_px, icon_px))
        self._pin_row.setFixedHeight(icon_px + round(8 * scale))
        for widget in self._entries.values():
            widget.apply_scale(scale)
        if self._entries:
            self._layout_entries(list(self._entries.values()))

    def retranslate(self) -> None:
        self._pin_button.setToolTip(t("mini_pin_tooltip"))

    def enterEvent(self, event) -> None:
        self._pin_hide_timer.stop()
        self._pin_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._pin_button.is_dragging():
            self._pin_hide_timer.start(PIN_HIDE_DELAY_MS)
        super().leaveEvent(event)

    def finish_drag(self) -> None:
        self._ensure_on_screen()
        self._schedule_position_save()
        if not self.underMouse():
            self._pin_hide_timer.start(PIN_HIDE_DELAY_MS)

    def _hide_pin_if_idle(self) -> None:
        if not self.underMouse() and not self._pin_button.is_dragging():
            self._pin_button.hide()

    def moveEvent(self, event) -> None:
        self._update_pin_position()
        self._schedule_position_save()
        super().moveEvent(event)

    def _schedule_position_save(self) -> None:
        self._position_save_timer.start(POSITION_SAVE_DELAY_MS)

    def _save_position(self) -> None:
        self._settings.set_mini_widget_position(self.x(), self.y())

    def _ensure_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        rect = self.frameGeometry()
        screen = self._screen_for_rect(rect, screens)
        if QGuiApplication.screenAt(rect.center()) is None:
            overlap = screen.availableGeometry().intersected(rect)
            if overlap.width() < min(MIN_VISIBLE_PX, rect.width()) or overlap.height() < min(
                MIN_VISIBLE_PX, rect.height()
            ):
                screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        x = min(max(rect.x(), available.left()), max(available.left(), available.right() - rect.width() + 1))
        y = min(max(rect.y(), available.top()), max(available.top(), available.bottom() - rect.height() + 1))
        if x != rect.x() or y != rect.y():
            self.move(x, y)
        self._update_pin_position()

    def _update_pin_position(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        rect = self.frameGeometry()
        screen = self._screen_for_rect(rect, screens)
        pin_below_content = rect.center().y() <= screen.availableGeometry().center().y()
        for widget in self._entries.values():
            widget.set_volume_below_icon(pin_below_content)
        if pin_below_content == self._pin_below_content:
            return
        self._outer_layout.removeWidget(self._pin_row)
        self._outer_layout.insertWidget(1 if pin_below_content else 0, self._pin_row)
        self._pin_below_content = pin_below_content

    @staticmethod
    def _screen_for_rect(rect, screens):
        screen = QGuiApplication.screenAt(rect.center())
        if screen is not None:
            return screen
        return max(
            screens,
            key=lambda candidate: candidate.availableGeometry().intersected(rect).width()
            * candidate.availableGeometry().intersected(rect).height(),
        )
