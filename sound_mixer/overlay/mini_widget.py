from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QLabel,
    QSlider,
    QWidget,
)

from sound_mixer.audio.process_exit_listener import ProcessExitListener
from sound_mixer.i18n import t
from sound_mixer.mixer.model import MixerEntry, MixerModel
from sound_mixer.overlay.icons import DelayedTooltipButton, load_app_icon, load_icon
from sound_mixer.overlay.scaling import ScaleLimit
from sound_mixer.overlay.taskbar_listener import TaskbarListener
from sound_mixer.settings.store import SettingsStore
from sound_mixer.overlay.win_effects import get_accent_color, raise_without_activating

POSITION_SAVE_DELAY_MS = 300
PIN_HIDE_DELAY_MS = 600
SELECTION_HIGHLIGHT_MS = 1500
SCREEN_UPDATE_EVENT = QEvent.Type(QEvent.registerEventType())
MIN_VISIBLE_PX = 48
DRAG_UPDATE_INTERVAL_MS = 33
SNAP_DISTANCE_PX = 8
SNAP_RELEASE_DISTANCE_PX = 16
BASE_SLIDER_WIDTH_PX = 6
BASE_APP_ICON_PX = 32
BASE_FONT_PX = 13
BASE_ICON_PX = 16
BASE_MARGIN_PX = 8
BASE_SPACING_PX = 8
BASE_ENTRY_RADIUS_PX = 10
MUTED_OPACITY = 0.45
MUTED_ICON_SCALE = 0.75


def mini_slider_style(scale: float, accent_color: str) -> str:
    width = max(1, round(2 * scale))
    return f"""
QSlider::groove:vertical {{
    width: {width}px;
    background: #555555;
    border-radius: {width // 2}px;
}}
QSlider::add-page:vertical {{
    width: {width}px;
    background: {accent_color};
    border-radius: {width // 2}px;
}}
QSlider::handle:vertical {{
    width: 0px;
    height: 0px;
    margin: 0;
    background: transparent;
    border: none;
}}
"""


class MiniEntryWidget(QFrame):
    scrolled = Signal(int)
    mute_toggled = Signal()
    focus_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("miniEntryWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.key = ""
        self._entry: MixerEntry | None = None
        self._scale = 1.0
        self._background_transparency = 0.8
        self._selected = False
        self._volume_below_icon = False
        self._vertical = False
        self._slider_before_icon = False

        self._volume_label = QLabel(self)
        self._volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._volume_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._slider = QSlider(Qt.Orientation.Vertical, self)
        self._slider.setRange(0, 100)
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._slider.setEnabled(False)
        self._slider.hide()

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

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._volume_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_container, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._slider, 0, Qt.AlignmentFlag.AlignCenter)

        self.apply_scale(1.0)

    def set_volume_below_icon(self, below: bool) -> None:
        below = bool(below)
        if below == self._volume_below_icon:
            return
        self._volume_below_icon = below
        self._update_layout()

    def set_vertical(self, vertical: bool, *, slider_before_icon: bool = False) -> None:
        if vertical == self._vertical and slider_before_icon == self._slider_before_icon:
            return
        self._vertical = vertical
        self._slider_before_icon = slider_before_icon
        self._update_layout()
        self.apply_scale(self._scale)

    def _update_layout(self) -> None:
        layout = self.layout()
        while layout.count():
            layout.takeAt(0)
        if self._vertical:
            layout.setDirection(QBoxLayout.Direction.LeftToRight)
            widgets = (self._slider, self._icon_container) if self._slider_before_icon else (
                self._icon_container, self._slider
            )
        else:
            layout.setDirection(QBoxLayout.Direction.TopToBottom)
            widgets = (self._icon_container, self._volume_label) if self._volume_below_icon else (
                self._volume_label, self._icon_container
            )
        self._volume_label.setVisible(not self._vertical)
        self._slider.setVisible(self._vertical)
        for widget in widgets:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignCenter)

    def apply_scale(self, scale: float) -> None:
        self._scale = scale
        icon_px = round(BASE_APP_ICON_PX * scale)
        margin = round(BASE_MARGIN_PX * scale)
        spacing = round(BASE_SPACING_PX * scale)
        radius = round(BASE_ENTRY_RADIUS_PX * scale)
        self._apply_background(radius)
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
        self._slider.setStyleSheet(mini_slider_style(scale, get_accent_color()))
        self._slider.setFixedSize(round(BASE_SLIDER_WIDTH_PX * scale), icon_px)
        if self._vertical:
            self.setFixedSize(icon_px + spacing + self._slider.width() + 2 * margin, icon_px + 2 * margin)
        else:
            extent = max(icon_px, self._volume_label.fontMetrics().horizontalAdvance("100%")) + 2 * margin
            self.setFixedSize(extent, text_height + icon_px + spacing + 2 * margin)
        self._update_icon()

    def set_background_transparency(self, transparency: float) -> None:
        self._background_transparency = transparency
        self._apply_background(round(BASE_ENTRY_RADIUS_PX * self._scale))

    def _apply_background(self, radius: int) -> None:
        alpha = round(255 * (1 - self._background_transparency))
        border = get_accent_color() if self._selected else "transparent"
        self.setStyleSheet(
            f"QFrame#miniEntryWidget {{ background: rgba(0, 0, 0, {alpha}); border: 1px solid {border}; border-radius: {radius}px; }}"
        )

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.setProperty("selected", selected)
            self._apply_background(round(BASE_ENTRY_RADIUS_PX * self._scale))

    def set_entry(self, entry: MixerEntry) -> None:
        state = (entry.key, entry.display_name, entry.volume, entry.muted, entry.icon_path, entry.is_master)
        if state == getattr(self, "_entry_state", None):
            self._entry = entry
            return
        old_icon = getattr(self, "_entry_icon", None)
        self._entry_state = state
        self._entry = entry
        self.key = entry.key
        self._volume_label.setText(f"{round(entry.volume * 100)}%")
        self._slider.setValue(round(entry.volume * 100))
        show_muted = entry.muted or (entry.is_master and entry.volume == 0)
        self._icon_effect.setOpacity(MUTED_OPACITY if show_muted else 1.0)
        self._muted_icon_label.setVisible(show_muted)
        self.setToolTip(entry.display_name)
        self._volume_label.setToolTip(entry.display_name)
        self._icon_label.setToolTip(entry.display_name)
        self._muted_icon_label.setToolTip(entry.display_name)
        self._entry_icon = (entry.is_master, entry.icon_path)
        if self._entry_icon != old_icon:
            self._update_icon()

    def _update_icon(self) -> None:
        if self._entry is None:
            return
        icon_px = round(BASE_APP_ICON_PX * self._scale)
        icon = load_icon("volume") if self._entry.is_master else load_app_icon(self._entry.icon_path)
        self._icon_label.setPixmap(icon.pixmap(icon_px, icon_px))

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
        self._drag_size = QSize()
        self._pending_drag: QRect | None = None
        self._drag_moved = False
        self._drag_timer = QTimer(self)
        self._drag_timer.setSingleShot(True)
        self._drag_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._drag_timer.setInterval(DRAG_UPDATE_INTERVAL_MS)
        self._drag_timer.timeout.connect(self._flush_drag)

    def _flush_drag(self) -> None:
        if self._pending_drag is None:
            return
        rect = self._pending_drag
        self._pending_drag = None
        self.window().drag_to(rect)
        self._drag_timer.start()

    def cancel_drag(self) -> None:
        self._drag_timer.stop()
        self._pending_drag = None
        self._drag_offset = None
        self._drag_moved = False

    def is_dragging(self) -> bool:
        return self._drag_offset is not None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.cancel_drag()
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            self._drag_size = self.window().size()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_moved = True
            self._pending_drag = QRect(event.globalPosition().toPoint() - self._drag_offset, self._drag_size)
            if not self._drag_timer.isActive():
                self._flush_drag()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            if self._drag_moved:
                self._pending_drag = QRect(event.globalPosition().toPoint() - self._drag_offset, self._drag_size)
                self._flush_drag()
            self.cancel_drag()
            self.window().finish_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MiniWidget(QWidget):
    visibility_changed = Signal(bool)
    model_changed = Signal()

    def __init__(self, model: MixerModel, settings: SettingsStore, parent=None, request_refresh=None) -> None:
        super().__init__(parent)
        self._model = model
        self._settings = settings
        self._enabled = False
        self._selected_key: str | None = None
        self._request_refresh = request_refresh
        self._selected_state: tuple[str, float, bool] | None = None
        self._dock_edge = self._settings.get_mini_widget_dock_edge()
        self._entries: dict[str, MiniEntryWidget] = {}
        self._pin_below_content: bool | None = None
        self._pin_layout_state = None
        self._updating_drag = False
        self._screen = None
        self._screen_update_pending = False
        self._process_exit_listener = ProcessExitListener(self)
        self._process_exit_listener.process_exited.connect(self._on_process_exited)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "QWidget, QFrame { background: transparent; border: none; }"
            "QToolButton { background: transparent; border: none; padding: 4px; }"
            "QToolButton:hover { background: rgba(255, 255, 255, 24); border-radius: 6px; }"
            "QLabel { color: #f2f2f5; background: transparent; }"
        )

        self._outer_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._pin_row = QWidget(self)
        pin_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._pin_row)
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
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.addWidget(self._content)

        self._position_save_timer = QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.timeout.connect(self._save_position)
        self._pin_hide_timer = QTimer(self)
        self._pin_hide_timer.setSingleShot(True)
        self._pin_hide_timer.timeout.connect(self._hide_pin_if_idle)
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(SELECTION_HIGHLIGHT_MS)
        self._selection_timer.timeout.connect(self._clear_selection_highlight)

        self._taskbar_listener = TaskbarListener(self)
        self._taskbar_listener.changed.connect(self._raise_above_taskbar)

        app = QApplication.instance()
        app.screenAdded.connect(self._watch_screen)
        app.screenRemoved.connect(self._schedule_screen_update)
        for screen in app.screens():
            self._watch_screen(screen)

        position = self._settings.get_mini_widget_position()
        self.move(position["x"], position["y"])
        self.scale_limit = ScaleLimit(self)
        self.scale_limit.changed.connect(self.apply_scale)
        self.apply_scale()

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool, persist: bool = True) -> None:
        enabled = bool(enabled)
        self._enabled = enabled
        if persist and self._settings.get_mini_widget_enabled() != enabled:
            self._settings.set_mini_widget_enabled(enabled)
        if enabled:
            self.refresh_view()
        else:
            self._process_exit_listener.stop()
            self.hide()

    def sync_from_settings(self) -> None:
        self.apply_scale()
        self.set_enabled(self._settings.get_mini_widget_enabled(), persist=False)

    def stop(self) -> None:
        self._clear_selection_highlight()
        self._process_exit_listener.stop()
        self._pin_button.cancel_drag()
        self._position_save_timer.stop()
        self._pin_hide_timer.stop()
        self._taskbar_listener.stop()
        self._cancel_screen_update()
        self._save_position()

    def refresh_view(self) -> None:
        entries = self._available_entries()
        keys = [entry.key for entry in entries]
        if self._selected_key not in keys:
            self._clear_selection_highlight()
            self._selected_key = keys[0] if keys else None
        if not self._enabled:
            self.hide()
            return

        selected = next((entry for entry in entries if entry.key == self._selected_key), None)
        state = (selected.key, selected.volume, selected.muted) if selected else None
        if state and self._selected_state and state[0] == self._selected_state[0] and state != self._selected_state:
            self._highlight_selection()
        self._selected_state = state

        if self._request_refresh is None:
            self._process_exit_listener.sync({pid for entry in entries for pid in entry.pids})
        order_changed = keys != list(self._entries)
        active_keys = {entry.key for entry in entries}
        for key in list(self._entries):
            if key not in active_keys:
                widget = self._entries.pop(key)
                self._grid.removeWidget(widget)
                widget.hide()
                widget.deleteLater()

        ordered_widgets = []
        for entry in entries:
            widget = self._entries.get(entry.key)
            if widget is None:
                widget = MiniEntryWidget(self._content)
                widget.focus_requested.connect(lambda w=widget: self._select_key(w.key))
                widget.scrolled.connect(lambda direction, w=widget: self._on_scrolled(w.key, direction))
                widget.mute_toggled.connect(lambda w=widget: self._on_mute_toggled(w.key))
                widget.apply_scale(self.scale_limit.constrain(self._settings.get_mini_widget_scale()))
                widget.set_volume_below_icon(bool(self._pin_below_content))
                self._entries[entry.key] = widget
            widget.set_entry(entry)
            widget.set_selected(entry.key == self._selected_key and self._selection_timer.isActive())
            widget.set_background_transparency(self._settings.get_mini_widget_background_transparency())
            ordered_widgets.append(widget)

        if not ordered_widgets:
            self.hide()
            return

        self._entries = {widget.key: widget for widget in ordered_widgets}
        if order_changed:
            self._layout_entries(ordered_widgets)
            self._ensure_on_screen()
        if not self.isVisible():
            self.show()
        self._sync_taskbar_stacking()

    def _on_process_exited(self) -> None:
        if self._request_refresh is not None:
            self._request_refresh()
            return
        if self._enabled:
            self._model.refresh(include_master=False)
            self._model.refresh_master_after_app_event()
            self.refresh_view()
            self.model_changed.emit()

    def _sync_taskbar_stacking(self) -> None:
        if self._settings.get_mini_widget_show_above_taskbar() and self._enabled and self.isVisible():
            self._taskbar_listener.start()
            self._raise_above_taskbar()
        else:
            self._taskbar_listener.stop()

    def _raise_above_taskbar(self) -> None:
        if self._settings.get_mini_widget_show_above_taskbar() and self._enabled and self.isVisible():
            raise_without_activating(self)

    def hideEvent(self, event) -> None:
        self._clear_selection_highlight()
        self._selected_state = None
        self._pin_button.cancel_drag()
        self._taskbar_listener.stop()
        self._cancel_screen_update()
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def event(self, event) -> bool:
        if event.type() == SCREEN_UPDATE_EVENT:
            self._screen_update_pending = False
            self._update_screen_layout()
            return True
        result = super().event(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            if hasattr(self, "_screen_update_pending"):
                self._schedule_screen_update()
        return result

    def _watch_screen(self, screen) -> None:
        screen.geometryChanged.connect(self._schedule_screen_update)
        screen.availableGeometryChanged.connect(self._schedule_screen_update)
        screen.logicalDotsPerInchChanged.connect(self._schedule_screen_update)
        screen.physicalDotsPerInchChanged.connect(self._schedule_screen_update)
        self._schedule_screen_update()

    def _schedule_screen_update(self, *args) -> None:
        if self._enabled and self.isVisible() and not self._screen_update_pending:
            self._screen_update_pending = True
            QApplication.postEvent(self, QEvent(SCREEN_UPDATE_EVENT))

    def _cancel_screen_update(self) -> None:
        QApplication.removePostedEvents(self, SCREEN_UPDATE_EVENT)
        self._screen_update_pending = False

    def _update_screen_layout(self) -> None:
        if not self._enabled or not self.isVisible() or not self._entries:
            return
        screens = QGuiApplication.screens()
        if not screens:
            return
        screen = self._screen if self._screen in screens else QGuiApplication.primaryScreen()
        self._pin_button.cancel_drag()
        self._layout_entries(list(self._entries.values()), screen)
        self._ensure_on_screen(screen=screen)

    def _screen_geometry(self, screen):
        if self._settings.get_mini_widget_show_above_taskbar():
            return screen.geometry()
        return screen.availableGeometry()

    def _layout_entries(self, widgets: list[MiniEntryWidget], screen=None) -> None:
        while self._grid.count():
            self._grid.takeAt(0)

        spacing = round(BASE_SPACING_PX * self.scale_limit.constrain(self._settings.get_mini_widget_scale()))
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)
        if screen is None:
            screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        vertical = self._dock_edge in ("left", "right")
        for widget in widgets:
            widget.set_vertical(vertical, slider_before_icon=self._dock_edge == "right")
        if vertical:
            cell_height = max(widget.height() for widget in widgets)
            available_height = self._screen_geometry(screen).height() if screen is not None else cell_height
            rows = max(1, (available_height + spacing) // (cell_height + spacing))
        else:
            cell_width = max(widget.width() for widget in widgets)
            available_width = self._screen_geometry(screen).width() if screen is not None else cell_width
            columns = max(1, (available_width + spacing) // (cell_width + spacing))

        for index, widget in enumerate(widgets):
            row, column = (index % rows, index // rows) if vertical else (index // columns, index % columns)
            self._grid.addWidget(widget, row, column, Qt.AlignmentFlag.AlignCenter)
            widget.show()

        self._content.adjustSize()
        content_hint = self._grid.sizeHint()
        self._content.setFixedSize(content_hint)
        self._update_pin_position()

    @property
    def selected_key(self) -> str | None:
        return self._selected_key

    def _available_entries(self) -> list[MixerEntry]:
        return [entry for entry in self._model.entries
                if not entry.is_master or self._settings.get_mini_widget_show_master()]

    def _select_key(self, key: str) -> None:
        if self._selected_key == key:
            return
        self._selected_key = key
        self._highlight_selection()

    def _highlight_selection(self) -> None:
        self._selection_timer.start()
        for entry_key, widget in self._entries.items():
            widget.set_selected(entry_key == self._selected_key)

    def _clear_selection_highlight(self) -> None:
        self._selection_timer.stop()
        for widget in self._entries.values():
            widget.set_selected(False)

    def move_selection(self, delta: int) -> None:
        if not self.isVisible():
            return
        self.refresh_view()
        keys = [entry.key for entry in self._available_entries()]
        if keys:
            self._select_key(keys[(keys.index(self._selected_key) + delta) % len(keys)])

    def adjust_selected_volume(self, direction: int) -> None:
        if not self.isVisible():
            return
        self.refresh_view()
        if self._selected_key is not None:
            self._adjust_volume(self._selected_key, direction * self._settings.get_arrow_step())

    def toggle_master_visibility(self) -> None:
        self._settings.set_mini_widget_show_master(not self._settings.get_mini_widget_show_master())
        self.refresh_view()

    def _adjust_volume(self, key: str, delta: float) -> None:
        for index, entry in enumerate(self._model.entries):
            if entry.key == key:
                self._model.adjust_volume(delta, index)
                self._highlight_selection()
                break
        self.refresh_view()
        self.model_changed.emit()

    def _on_scrolled(self, key: str, direction: int) -> None:
        self._select_key(key)
        self._adjust_volume(key, direction * self._settings.get_scroll_step())

    def _on_mute_toggled(self, key: str) -> None:
        self._select_key(key)
        for index, entry in enumerate(self._model.entries):
            if entry.key == key:
                self._model.toggle_mute(index)
                break
        self.refresh_view()
        self.model_changed.emit()

    def apply_scale(self) -> None:
        scale = self.scale_limit.constrain(self._settings.get_mini_widget_scale())
        icon_px = round(BASE_ICON_PX * scale)
        self._pin_button.setIconSize(QSize(icon_px, icon_px))
        pin_extent = icon_px + round(8 * scale)
        self._pin_button.setFixedSize(pin_extent, pin_extent)
        for widget in self._entries.values():
            widget.apply_scale(scale)
        if self._entries:
            self._layout_entries(list(self._entries.values()))
            self._ensure_on_screen()

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

    def drag_to(self, rect: QRect) -> None:
        previous_edge = self._dock_edge
        self._dock_edge = ""
        screens = QGuiApplication.screens()
        screen = None
        if screens:
            screen = self._screen_for_rect(rect, screens)
            available = self._screen_geometry(screen)
            distances = {
                "left": max(0, rect.left() - available.left()),
                "right": max(0, available.right() - rect.right()),
                "top": max(0, rect.top() - available.top()),
                "bottom": max(0, available.bottom() - rect.bottom()),
            }
            edge = min(distances, key=lambda candidate: (distances[candidate], candidate != previous_edge))
            if previous_edge and distances[previous_edge] <= SNAP_RELEASE_DISTANCE_PX:
                self._dock_edge = previous_edge
            elif distances[edge] <= SNAP_DISTANCE_PX:
                self._dock_edge = edge
        layout_changed = self._dock_edge != previous_edge
        updates_enabled = self.updatesEnabled()
        self._updating_drag = True
        if layout_changed:
            self.setUpdatesEnabled(False)
        try:
            if self._entries and layout_changed:
                self._layout_entries(list(self._entries.values()), screen)
            self._ensure_on_screen(QRect(rect.topLeft(), self.size()), screen)
        finally:
            self._updating_drag = False
            if layout_changed:
                self.setUpdatesEnabled(updates_enabled)

    def finish_drag(self) -> None:
        self._ensure_on_screen()
        self._schedule_position_save()
        if not self.underMouse():
            self._pin_hide_timer.start(PIN_HIDE_DELAY_MS)

    def _hide_pin_if_idle(self) -> None:
        if not self.underMouse() and not self._pin_button.is_dragging():
            self._pin_button.hide()

    def moveEvent(self, event) -> None:
        if not self._updating_drag:
            self._update_pin_position()
        self._schedule_position_save()
        super().moveEvent(event)

    def _schedule_position_save(self) -> None:
        self._position_save_timer.start(POSITION_SAVE_DELAY_MS)

    def _save_position(self) -> None:
        self._settings.set_mini_widget_position(self.x(), self.y(), self._dock_edge)

    def _ensure_on_screen(self, rect: QRect | None = None, screen=None) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        if rect is None:
            rect = self.frameGeometry()
        if screen is None:
            screen = self._screen_for_rect(rect, screens)
            if QGuiApplication.screenAt(rect.center()) is None:
                overlap = self._screen_geometry(screen).intersected(rect)
                if overlap.width() < min(MIN_VISIBLE_PX, rect.width()) or overlap.height() < min(
                    MIN_VISIBLE_PX, rect.height()
                ):
                    screen = QGuiApplication.primaryScreen()
        self._screen = screen
        available = self._screen_geometry(screen)
        x = min(max(rect.x(), available.left()), max(available.left(), available.right() - rect.width() + 1))
        y = min(max(rect.y(), available.top()), max(available.top(), available.bottom() - rect.height() + 1))
        if self._dock_edge == "left":
            x = available.left()
        elif self._dock_edge == "right":
            x = max(available.left(), available.right() - rect.width() + 1)
        elif self._dock_edge == "top":
            y = available.top()
        elif self._dock_edge == "bottom":
            y = max(available.top(), available.bottom() - rect.height() + 1)
        if x != self.x() or y != self.y():
            self.move(x, y)
        self._update_pin_position()

    def _update_pin_position(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        rect = self.frameGeometry()
        screen = self._screen_for_rect(rect, screens)
        vertical = self._dock_edge in ("left", "right")
        pin_below_content = self._dock_edge == "top" or (
            self._dock_edge == "" and (
                self._pin_below_content if self._pin_below_content is not None
                else rect.center().y() <= self._screen_geometry(screen).center().y()
            )
        )
        pin_extent = self._pin_button.width()
        content_size = self._content.size()
        state = (vertical, self._dock_edge, pin_below_content, pin_extent, content_size)
        if state == self._pin_layout_state:
            return
        self._pin_layout_state = state
        for widget in self._entries.values():
            widget.set_volume_below_icon(pin_below_content)
        pin_after_content = self._dock_edge == "left" if vertical else pin_below_content
        self._outer_layout.setDirection(
            QBoxLayout.Direction.LeftToRight if vertical else QBoxLayout.Direction.TopToBottom
        )
        self._pin_row.layout().setDirection(
            QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight
        )
        if self._outer_layout.indexOf(self._pin_row) != int(pin_after_content):
            self._outer_layout.removeWidget(self._pin_row)
            self._outer_layout.insertWidget(int(pin_after_content), self._pin_row)
        self._pin_below_content = pin_below_content
        if vertical:
            self._pin_row.setFixedSize(pin_extent, content_size.height())
            self.setFixedSize(content_size.width() + pin_extent, content_size.height())
        else:
            self._pin_row.setFixedSize(content_size.width(), pin_extent)
            self.setFixedSize(content_size.width(), content_size.height() + pin_extent)
        self._outer_layout.activate()
        self._pin_row.layout().activate()

    def _screen_for_rect(self, rect, screens):
        screen = QGuiApplication.screenAt(rect.center())
        if screen is not None:
            return screen
        return max(
            screens,
            key=lambda candidate: self._screen_geometry(candidate).intersected(rect).width()
            * self._screen_geometry(candidate).intersected(rect).height(),
        )
