import ctypes
import sys
from ctypes import wintypes
from typing import Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sound_mixer import __version__
from sound_mixer.audio.session_listener import AudioSessionListener
from sound_mixer.i18n import t
from sound_mixer.mixer.model import MixerModel
from sound_mixer.mixer.subprocess_manager import SubprocessManager
from sound_mixer.overlay.entry_widget import (
    BASE_VERTICAL_VALUE_FONT_PX,
    VALUE_TEXT_PADDING_PX,
    EntryWidget,
)
from sound_mixer.overlay.icons import (
    TOGGLE_SWITCH_HEIGHT_PX,
    TOGGLE_SWITCH_WIDTH_PX,
    DelayedTooltipButton,
    load_icon,
    toggle_switch_style,
)
from sound_mixer.overlay.win_effects import WM_DWMCOLORIZATIONCOLORCHANGED, apply_acrylic_effect, get_accent_color
from sound_mixer.settings.schema import LAYOUT_HORIZONTAL, LAYOUT_VERTICAL
from sound_mixer.settings.store import SettingsStore

REFRESH_INTERVAL_MS = 1000
GEOMETRY_SAVE_DELAY_MS = 300
WARM_UP_HIDE_DELAY_MS = 150
WARM_UP_RESHOW_DELAY_MS = 50

BASE_FONT_PX = 13
BASE_ICON_PX = 16
BASE_TITLE_LOGO_PX = 28
BASE_TITLE_FONT_PX = 17
BASE_VERSION_FONT_PX = 11
BASE_DIVIDER_MARGIN_PX = 4

MIN_OVERLAY_WIDTH = 200
MAX_WIDGET_SIZE = 16777215
RESIZE_HANDLE_WIDTH_PX = 6
RESIZE_HANDLE_HEIGHT_PX = 6
MIN_VISIBLE_PX = 48
MAX_VISIBLE_ENTRIES = 6
BACKGROUND_BORDER_PX = 1


def _accent_rgba(hex_color: str, alpha: int) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def background_style(scale: float, accent_color: str, transparent: bool = True, vertical: bool = False) -> str:
    font_px = round(BASE_FONT_PX * scale)
    title_font_px = round(BASE_TITLE_FONT_PX * scale)
    version_font_px = round(BASE_VERSION_FONT_PX * scale)
    control_radius = round(8 * scale)
    entry_radius = round(10 * scale)
    background_color = "rgba(32, 32, 32, 140)" if transparent else "rgb(32, 32, 32)"
    accent_bg = _accent_rgba(accent_color, 45)
    ignored_button_padding = (
        f"{round(4 * scale)}px {round(2 * scale)}px" if vertical else f"{round(4 * scale)}px"
    )
    value_padding = round((VALUE_TEXT_PADDING_PX if vertical else 8) * scale)
    value_font_px = round((BASE_VERTICAL_VALUE_FONT_PX if vertical else BASE_FONT_PX) * scale)
    ignored_button_width = "" if vertical else "\n    width: 100%;"
    return f"""
#background {{
    background-color: {background_color};
    border: 1px solid {accent_color};
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
    background: {accent_bg};
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
    padding: {round(4 * scale)}px {value_padding}px;
    min-height: {font_px}px;
    font-size: {value_font_px}px;
    color: #f2f2f5;
}}
#background #entryWidget #processNameLabel {{
    background: rgba(0, 0, 0, 70);
    border: none;
    border-radius: {control_radius}px;
    padding: {round(3 * scale)}px {round(8 * scale)}px;
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
#background QScrollBar:horizontal {{
    height: {round(8 * scale)}px;
    background: transparent;
    margin: 2px;
}}
#background QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 60);
    border-radius: {round(4 * scale)}px;
    min-width: 24px;
}}
#background QScrollBar::handle:horizontal:hover {{
    background: rgba(255, 255, 255, 90);
}}
#background QScrollBar::add-line:horizontal, #background QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
    background: none;
}}
#background QScrollBar::add-page:horizontal, #background QScrollBar::sub-page:horizontal {{
    background: none;
}}
#background #ignoredDivider {{
    color: rgba(255, 255, 255, 40);
}}
#background #expandButton, #background #collapseButton {{
    background: rgba(255, 255, 255, 8);
    border: none;
    border-radius: {control_radius}px;
    padding: {ignored_button_padding};{ignored_button_width}
}}
#background #expandButton:hover, #background #collapseButton:hover {{
    background: rgba(255, 255, 255, 18);
}}
"""


class _ResizeHandle(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._vertical = False
        self._drag_start_pos: int | None = None
        self._start_size = 0
        self.set_vertical(False)

    def set_vertical(self, vertical: bool) -> None:
        self._vertical = vertical
        self.setCursor(Qt.CursorShape.SizeVerCursor if vertical else Qt.CursorShape.SizeHorCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            position = event.globalPosition().toPoint()
            self._drag_start_pos = position.y() if self._vertical else position.x()
            self._start_size = window.height() if self._vertical else window.width()
            window._pause_refresh()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            position = event.globalPosition().toPoint()
            window = self.window()
            if self._vertical:
                delta = position.y() - self._drag_start_pos
                window.resize(window.width(), max(window.minimumHeight(), self._start_size + delta))
            else:
                delta = position.x() - self._drag_start_pos
                window.resize(max(window.minimumWidth(), self._start_size + delta), window.height())
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

    def __init__(
        self,
        model: MixerModel,
        settings: SettingsStore,
        subprocess_manager: Optional[SubprocessManager] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._settings = settings
        self._subprocess_manager = subprocess_manager
        self._entry_widgets: list[EntryWidget] = []
        self._ignored_widgets: list[EntryWidget] = []
        self._ignored_expanded = False
        self._layout_mode = settings.get_layout_mode()
        self._vertical = self._layout_mode == LAYOUT_VERTICAL
        self._warming_up = False
        self._show_after_warm_up = False

        self.setWindowTitle(t("sound_mixer_title"))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumWidth(MIN_OVERLAY_WIDTH)
        self._accent_color = get_accent_color()

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.timeout.connect(self._save_geometry)

        self._build_ui()
        self._apply_layout_mode()
        self._restore_geometry()
        self.apply_scale()
        self._ensure_on_screen()
        apply_acrylic_effect(self, self._settings.get_transparency_enabled())

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)

        self._session_listener = AudioSessionListener(self._on_new_session)

        self.sync_subprocess_management_toggle()
        self._sync_entry_widgets()

        if sys.platform == "win32":
            self._warm_up_acrylic()

    def _warm_up_acrylic(self) -> None:
        self._warming_up = True
        self.show()
        QTimer.singleShot(WARM_UP_HIDE_DELAY_MS, self._finish_warm_up)

    def _finish_warm_up(self) -> None:
        self._warming_up = False
        self.close()
        if self._show_after_warm_up:
            self._show_after_warm_up = False
            QTimer.singleShot(WARM_UP_RESHOW_DELAY_MS, self.show)

    def show_on_start(self) -> None:
        if self._warming_up:
            self._show_after_warm_up = True
            return
        self.show()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        background = QFrame(self)
        background.setObjectName("background")
        outer_layout.addWidget(background)
        self._background = background

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, background)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._background_layout = layout
        title_bar = self._build_title_bar(background)
        layout.addWidget(title_bar)

        self._active_container = QWidget()
        self._active_container.setObjectName("entryContainer")
        self._active_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._active_container)
        self._active_layout.setContentsMargins(0, 0, 0, 0)
        self._active_layout.setSpacing(0)

        self._expand_button = DelayedTooltipButton()
        self._expand_button.setObjectName("expandButton")
        self._expand_button.setIcon(load_icon("dropdown_arrow"))
        self._expand_button.setToolTip(t("show_ignored"))
        self._expand_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._expand_button.clicked.connect(self._on_expand_ignored)
        self._expand_button.hide()

        self._divider = QFrame()
        self._divider.setObjectName("ignoredDivider")
        self._divider.setFrameShape(QFrame.Shape.HLine)
        self._divider.hide()

        self._ignored_container = QWidget()
        self._ignored_container.setObjectName("entryContainer")
        self._ignored_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._ignored_container)
        self._ignored_layout.setContentsMargins(0, 0, 0, 0)
        self._ignored_layout.setSpacing(0)
        self._ignored_container.hide()

        self._collapse_button = DelayedTooltipButton()
        self._collapse_button.setObjectName("collapseButton")
        self._collapse_button.setIcon(load_icon("arrow_up"))
        self._collapse_button.setToolTip(t("hide_ignored"))
        self._collapse_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._collapse_button.clicked.connect(self._on_collapse_ignored)
        self._collapse_button.hide()

        scroll_container = QWidget()
        scroll_container.setObjectName("entryContainer")
        self._container_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, scroll_container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)
        self._container_layout.addWidget(self._active_container)
        self._container_layout.addWidget(self._expand_button)
        self._container_layout.addWidget(self._divider)
        self._container_layout.addWidget(self._ignored_container)
        self._container_layout.addWidget(self._collapse_button)
        self._container_layout.addStretch(1)

        scroll_area = QScrollArea(background)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_container)
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll_area)
        self._scroll_area = scroll_area

        self._title_bar = title_bar
        self._resize_handle = _ResizeHandle(self)

    def _refresh_accent_color(self) -> None:
        new_color = get_accent_color()
        if new_color != self._accent_color:
            self._accent_color = new_color
            self.apply_scale()

    def nativeEvent(self, event_type: bytes, message) -> tuple:
        if sys.platform == "win32" and event_type == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_DWMCOLORIZATIONCOLORCHANGED:
                self._refresh_accent_color()
        return super().nativeEvent(event_type, message)

    def showEvent(self, event) -> None:
        self._ensure_on_screen()
        super().showEvent(event)
        self._refresh_accent_color()
        self._session_listener.stop()
        self._refresh()
        self._refresh_timer.start(REFRESH_INTERVAL_MS)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._refresh_timer.stop()
        self._session_listener.start()
        self.visibility_changed.emit(False)

    def _build_title_bar(self, parent: QWidget) -> QWidget:
        title_bar = _TitleBar(parent)
        title_bar.setObjectName("titleBar")

        icon_label = QLabel(title_bar)
        icon_label.setToolTip(f"{t('sound_mixer_title')}\nv{__version__}")
        self._title_icon_label = icon_label

        name_label = QLabel(t("sound_mixer_title"), title_bar)
        name_label.setObjectName("titleName")
        self._title_name_label = name_label
        version_label = QLabel(f"v{__version__}", title_bar)
        version_label.setObjectName("titleVersion")
        self._title_version_label = version_label

        title_text_layout = QVBoxLayout()
        title_text_layout.setContentsMargins(0, 0, 0, 0)
        title_text_layout.setSpacing(0)
        title_text_layout.addWidget(name_label)
        title_text_layout.addWidget(version_label)
        self._title_text_layout = title_text_layout

        subprocess_management_toggle = QCheckBox(title_bar)
        subprocess_management_toggle.setObjectName("subprocessManagementToggle")
        subprocess_management_toggle.setStyleSheet(toggle_switch_style("subprocessManagementToggle"))
        subprocess_management_toggle.setFixedSize(TOGGLE_SWITCH_WIDTH_PX, TOGGLE_SWITCH_HEIGHT_PX)
        subprocess_management_toggle.setToolTip(t("subprocess_management_toggle_tooltip"))
        subprocess_management_toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        subprocess_management_toggle.setVisible(False)
        subprocess_management_toggle.toggled.connect(self._on_subprocess_management_toggled)
        self._subprocess_management_toggle = subprocess_management_toggle

        settings_button = DelayedTooltipButton(title_bar)
        settings_button.setIcon(load_icon("settings"))
        settings_button.setToolTip(t("settings_tooltip"))
        settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        settings_button.clicked.connect(self.settings_requested.emit)
        self._settings_button = settings_button

        guide_button = DelayedTooltipButton(title_bar)
        guide_button.setIcon(load_icon("help"))
        guide_button.setToolTip(t("controls_guide_tooltip"))
        guide_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        guide_button.clicked.connect(self._show_guide)
        self._guide_button = guide_button

        close_button = DelayedTooltipButton(title_bar)
        close_button.setIcon(load_icon("close"))
        close_button.setToolTip(t("close_tooltip"))
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(self.close)
        self._close_button = close_button

        layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, title_bar)
        layout.addWidget(icon_label)
        layout.addLayout(title_text_layout)
        layout.addStretch(1)
        layout.addWidget(subprocess_management_toggle)
        layout.addWidget(settings_button)
        layout.addWidget(guide_button)
        layout.addWidget(close_button)
        return title_bar

    def _restore_geometry(self) -> None:
        geometry = self._settings.get_overlay_geometry()
        self.setGeometry(geometry["x"], geometry["y"], geometry["width"], geometry["height"])

    def _ensure_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return

        rect = self.frameGeometry()
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry()

        if self._vertical and rect.height() > available.height():
            self.resize(self.width(), max(self.minimumHeight(), available.height()))
        elif not self._vertical and rect.width() > available.width():
            self.resize(max(MIN_OVERLAY_WIDTH, available.width()), self.height())

        rect = self.frameGeometry()
        for candidate in screens:
            overlap = candidate.availableGeometry().intersected(rect)
            if overlap.width() >= min(MIN_VISIBLE_PX, rect.width()) and overlap.height() >= min(
                MIN_VISIBLE_PX, rect.height()
            ):
                return

        center = available.center()
        self.move(center.x() - rect.width() // 2, center.y() - rect.height() // 2)

    def _save_geometry(self) -> None:
        geometry = self.geometry()
        self._settings.set_overlay_geometry(geometry.x(), geometry.y(), geometry.width(), geometry.height())

    def _schedule_geometry_save(self) -> None:
        self._geometry_save_timer.start(GEOMETRY_SAVE_DELAY_MS)

    def moveEvent(self, event) -> None:
        self._schedule_geometry_save()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        if self._vertical:
            title_bar_width = self._title_bar.width()
            self._resize_handle.setGeometry(
                title_bar_width,
                self.height() - RESIZE_HANDLE_HEIGHT_PX,
                self.width() - title_bar_width,
                RESIZE_HANDLE_HEIGHT_PX,
            )
        else:
            title_bar_height = self._title_bar.height()
            self._resize_handle.setGeometry(
                self.width() - RESIZE_HANDLE_WIDTH_PX,
                title_bar_height,
                RESIZE_HANDLE_WIDTH_PX,
                self.height() - title_bar_height,
            )
        self._resize_handle.raise_()

        self._schedule_geometry_save()
        super().resizeEvent(event)

    def _entry_extent(self, widget: EntryWidget) -> int:
        hint = widget.sizeHint()
        return hint.width() if self._vertical else hint.height()

    def _widget_extent(self, widget: QWidget) -> int:
        hint = widget.sizeHint()
        return hint.width() if self._vertical else hint.height()

    def _apply_minimum_height(self) -> None:
        if not self._vertical:
            return

        entry_widgets = self._entry_widgets + self._ignored_widgets
        entries_min = max((widget.minimumSizeHint().height() for widget in entry_widgets), default=0)
        margins = self._container_layout.contentsMargins()
        scrollbar_height = 0
        if self._scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn:
            scrollbar_height = self._scroll_area.horizontalScrollBar().sizeHint().height()
        content_min = margins.top() + margins.bottom() + entries_min + scrollbar_height

        target_height = max(
            self._title_bar.sizeHint().height() + 2 * BACKGROUND_BORDER_PX,
            content_min + 2 * BACKGROUND_BORDER_PX,
        )
        if self.minimumHeight() != target_height:
            self.setMinimumHeight(target_height)

    def _update_window_size(self) -> None:
        self._update_horizontal_scrollbar_policy()
        self._apply_minimum_height()

        all_ref_widgets = self._entry_widgets or self._ignored_widgets
        if not all_ref_widgets:
            return

        entry_extent = max(self._entry_extent(w) for w in all_ref_widgets)
        spacing = self._container_layout.spacing()
        margins = self._container_layout.contentsMargins()

        active_count = len(self._entry_widgets)
        ignored_visible = len(self._ignored_widgets) if self._ignored_expanded else 0
        total_entries = min(active_count + ignored_visible, MAX_VISIBLE_ENTRIES)

        entries_extent = total_entries * entry_extent + max(0, total_entries - 1) * spacing

        extra_extent = 0
        fallback = round(28 * self._settings.get_ui_scale())
        has_ignored = bool(self._ignored_widgets)
        if has_ignored and not self._ignored_expanded:
            btn = self._widget_extent(self._expand_button)
            extra_extent += spacing + (btn if btn > 0 else fallback)
        elif has_ignored and self._ignored_expanded:
            div = self._widget_extent(self._divider)
            btn = self._widget_extent(self._collapse_button)
            if div > 0:
                extra_extent += spacing + div
            extra_extent += spacing + (btn if btn > 0 else fallback)

        if self._vertical:
            container_width = margins.left() + margins.right() + entries_extent + extra_extent
            target_width = (
                self._title_bar.sizeHint().width() + container_width + 2 * BACKGROUND_BORDER_PX
            )
            if self.width() != target_width or self.minimumWidth() != target_width:
                self.setFixedWidth(target_width)
            return

        container_height = margins.top() + margins.bottom() + entries_extent + extra_extent
        title_bar_height = self._title_bar.sizeHint().height()
        target_height = title_bar_height + container_height + 2 * BACKGROUND_BORDER_PX
        if self.height() != target_height or self.minimumHeight() != target_height:
            self.setFixedHeight(target_height)

    def _on_new_session(self) -> None:
        try:
            self._model.refresh()
        except Exception:
            return

    def _refresh(self) -> None:
        try:
            self._model.refresh()
        except Exception:
            return
        self._sync_entry_widgets()

    def _pause_refresh(self) -> None:
        self._refresh_timer.stop()

    def _resume_refresh(self) -> None:
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

    def refresh_view(self) -> None:
        self._sync_entry_widgets()

    def _apply_layout_mode(self) -> None:
        vertical = self._vertical
        direction = QBoxLayout.Direction.LeftToRight if vertical else QBoxLayout.Direction.TopToBottom
        self._container_layout.setDirection(direction)
        self._active_layout.setDirection(direction)
        self._ignored_layout.setDirection(direction)
        self._divider.setFrameShape(QFrame.Shape.VLine if vertical else QFrame.Shape.HLine)
        self._background_layout.setDirection(direction)
        self._apply_title_bar_mode()

        rotation = -90 if vertical else 0
        self._expand_button.setIcon(load_icon("dropdown_arrow", rotation))
        self._collapse_button.setIcon(load_icon("arrow_up", rotation))

        self._update_horizontal_scrollbar_policy()
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if vertical else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._resize_handle.set_vertical(vertical)

        if vertical:
            self.setMaximumHeight(MAX_WIDGET_SIZE)
            self._apply_minimum_height()
        else:
            self.setMinimumHeight(0)
            self.setMaximumHeight(MAX_WIDGET_SIZE)
            self.setMinimumWidth(MIN_OVERLAY_WIDTH)
            self.setMaximumWidth(MAX_WIDGET_SIZE)

        for widget in self._entry_widgets + self._ignored_widgets:
            widget.set_layout_mode(self._layout_mode)

    def _apply_title_bar_mode(self) -> None:
        vertical = self._vertical
        title_layout = self._title_bar.layout()
        title_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight
        )
        alignment = Qt.AlignmentFlag.AlignHCenter if vertical else Qt.AlignmentFlag.AlignVCenter
        for widget in (
            self._title_icon_label,
            self._subprocess_management_toggle,
            self._settings_button,
            self._guide_button,
            self._close_button,
        ):
            title_layout.setAlignment(widget, alignment)
        title_layout.setAlignment(self._title_text_layout, alignment)

        self._title_name_label.setVisible(not vertical)
        self._title_version_label.setVisible(not vertical)

        self._title_bar.setSizePolicy(
            QSizePolicy.Policy.Maximum if vertical else QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred if vertical else QSizePolicy.Policy.Maximum,
        )

    def layout_mode(self) -> str:
        return self._layout_mode

    def set_layout_mode(self, mode: str) -> None:
        mode = LAYOUT_VERTICAL if mode == LAYOUT_VERTICAL else LAYOUT_HORIZONTAL
        if mode == self._layout_mode:
            return

        self._geometry_save_timer.stop()
        self._save_geometry()
        self._settings.set_layout_mode(mode)
        self._layout_mode = mode
        self._vertical = mode == LAYOUT_VERTICAL

        self._apply_layout_mode()
        self._restore_geometry()
        self.apply_scale()
        self._ensure_on_screen()

    def _apply_ignored_button_thickness(self) -> None:
        for button in (self._expand_button, self._collapse_button):
            button.ensurePolished()
            if self._vertical:
                button.setFixedWidth(button.sizeHint().height())
            else:
                button.setMinimumWidth(0)
                button.setMaximumWidth(MAX_WIDGET_SIZE)

    def _update_horizontal_scrollbar_policy(self) -> None:
        visible_entries = len(self._entry_widgets)
        if self._ignored_expanded:
            visible_entries += len(self._ignored_widgets)
        show_scrollbar = self._vertical and visible_entries > MAX_VISIBLE_ENTRIES
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
            if show_scrollbar
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setHorizontalScrollBarPolicy(policy)

    def apply_scale(self) -> None:
        scale = self._settings.get_ui_scale()
        transparent = self._settings.get_transparency_enabled()
        self._background.setStyleSheet(background_style(scale, self._accent_color, transparent, self._vertical))

        icon_px = round(BASE_ICON_PX * scale)
        logo_px = round(BASE_TITLE_LOGO_PX * scale)
        self._title_icon_label.setPixmap(load_icon("logo").pixmap(logo_px, logo_px))
        self._settings_button.setIconSize(QSize(icon_px, icon_px))
        self._guide_button.setIconSize(QSize(icon_px, icon_px))
        self._close_button.setIconSize(QSize(icon_px, icon_px))
        self._expand_button.setIconSize(QSize(icon_px, icon_px))
        self._collapse_button.setIconSize(QSize(icon_px, icon_px))
        self._apply_ignored_button_thickness()

        title_bar_layout = self._title_bar.layout()
        margin = round(12 * scale)
        spacing = round(10 * scale)
        title_bar_layout.setContentsMargins(margin, margin, margin, margin)
        title_bar_layout.setSpacing(spacing)

        for label in (self._title_name_label, self._title_version_label):
            label.ensurePolished()
            label.updateGeometry()

        container_margin = round(8 * scale)
        self._container_layout.setContentsMargins(container_margin, container_margin, container_margin, container_margin)
        self._container_layout.setSpacing(container_margin)
        self._active_layout.setContentsMargins(0, 0, 0, 0)
        self._active_layout.setSpacing(container_margin)
        self._ignored_layout.setContentsMargins(0, 0, 0, 0)
        self._ignored_layout.setSpacing(container_margin)

        for widget in self._entry_widgets + self._ignored_widgets:
            widget.apply_scale(scale, self._accent_color)

        self._update_window_size()

    def _make_active_widget(self) -> EntryWidget:
        widget = EntryWidget(self._active_container)
        widget.volume_changed.connect(lambda value, w=widget: self._on_volume_changed(w, value))
        widget.mute_toggled.connect(lambda w=widget: self._on_mute_toggled(w))
        widget.focus_requested.connect(lambda w=widget: self._on_focus_requested(w))
        widget.scrolled.connect(lambda direction, w=widget: self._on_scrolled(w, direction))
        widget.ignore_requested.connect(lambda w=widget: self._on_ignore_requested(w))
        widget.set_layout_mode(self._layout_mode)
        widget.apply_scale(self._settings.get_ui_scale(), self._accent_color)
        return widget

    def _make_ignored_widget(self) -> EntryWidget:
        widget = EntryWidget(self._ignored_container)
        widget.set_ignore_tooltip(t("restore_tooltip"))
        widget.volume_changed.connect(lambda value, w=widget: self._on_ignored_volume_changed(w, value))
        widget.mute_toggled.connect(lambda w=widget: self._on_ignored_mute_toggled(w))
        widget.scrolled.connect(lambda direction, w=widget: self._on_ignored_scrolled(w, direction))
        widget.ignore_requested.connect(lambda w=widget: self._on_unignore_requested(w))
        widget.set_layout_mode(self._layout_mode)
        widget.apply_scale(self._settings.get_ui_scale(), self._accent_color)
        return widget

    def _sync_entry_widgets(self) -> None:
        active_entries = self._model.entries
        ignored_entries = self._model.ignored_entries

        while len(self._entry_widgets) < len(active_entries):
            widget = self._make_active_widget()
            self._active_layout.addWidget(widget)
            self._entry_widgets.append(widget)
        while len(self._entry_widgets) > len(active_entries):
            widget = self._entry_widgets.pop()
            self._active_layout.removeWidget(widget)
            widget.deleteLater()

        while len(self._ignored_widgets) < len(ignored_entries):
            widget = self._make_ignored_widget()
            self._ignored_layout.addWidget(widget)
            self._ignored_widgets.append(widget)
        while len(self._ignored_widgets) > len(ignored_entries):
            widget = self._ignored_widgets.pop()
            self._ignored_layout.removeWidget(widget)
            widget.deleteLater()

        for index, (entry, widget) in enumerate(zip(active_entries, self._entry_widgets)):
            widget.set_entry(entry, focused=(index == self._model.focused_index))

        for entry, widget in zip(ignored_entries, self._ignored_widgets):
            widget.set_entry(entry, focused=False)

        has_ignored = bool(self._ignored_widgets)
        self._expand_button.setVisible(has_ignored and not self._ignored_expanded)
        self._divider.setVisible(has_ignored and self._ignored_expanded)
        self._ignored_container.setVisible(has_ignored and self._ignored_expanded)
        self._collapse_button.setVisible(has_ignored and self._ignored_expanded)

        self._update_window_size()

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

    def _on_ignore_requested(self, widget: EntryWidget) -> None:
        index = self._entry_widgets.index(widget)
        key = self._model.entries[index].key
        self._model.ignore_app(key)
        self._sync_entry_widgets()

    def _on_ignored_volume_changed(self, widget: EntryWidget, value: float) -> None:
        index = self._ignored_widgets.index(widget)
        key = self._model.ignored_entries[index].key
        self._model.set_ignored_volume(key, value)
        self._sync_entry_widgets()

    def _on_ignored_mute_toggled(self, widget: EntryWidget) -> None:
        index = self._ignored_widgets.index(widget)
        key = self._model.ignored_entries[index].key
        self._model.toggle_ignored_mute(key)
        self._sync_entry_widgets()

    def _on_ignored_scrolled(self, widget: EntryWidget, direction: int) -> None:
        index = self._ignored_widgets.index(widget)
        key = self._model.ignored_entries[index].key
        self._model.adjust_ignored_volume(key, direction * self._settings.get_scroll_step())
        self._sync_entry_widgets()

    def _on_unignore_requested(self, widget: EntryWidget) -> None:
        index = self._ignored_widgets.index(widget)
        key = self._model.ignored_entries[index].key
        self._model.unignore_app(key)
        self._sync_entry_widgets()

    def _on_expand_ignored(self) -> None:
        self._ignored_expanded = True
        self._sync_entry_widgets()

    def _on_collapse_ignored(self) -> None:
        self._ignored_expanded = False
        self._sync_entry_widgets()

    def _show_guide(self) -> None:
        from sound_mixer.overlay.guide import GuideDialog

        GuideDialog(vertical=self._vertical, parent=self).exec()

    def sync_subprocess_management_toggle(self) -> None:
        if self._subprocess_manager is None:
            self._subprocess_management_toggle.setVisible(False)
            return
        self._subprocess_management_toggle.setVisible(self._subprocess_manager.has_enabled_apps())
        self._subprocess_management_toggle.blockSignals(True)
        self._subprocess_management_toggle.setChecked(self._subprocess_manager.is_active())
        self._subprocess_management_toggle.blockSignals(False)
        self._apply_minimum_height()

    def _on_subprocess_management_toggled(self, checked: bool) -> None:
        if self._subprocess_manager is not None:
            self._subprocess_manager.set_active(checked)

    def retranslate(self) -> None:
        self.setWindowTitle(t("sound_mixer_title"))
        self._title_name_label.setText(t("sound_mixer_title"))
        self._title_icon_label.setToolTip(f"{t('sound_mixer_title')}\nv{__version__}")
        self._expand_button.setToolTip(t("show_ignored"))
        self._collapse_button.setToolTip(t("hide_ignored"))
        self._settings_button.setToolTip(t("settings_tooltip"))
        self._guide_button.setToolTip(t("controls_guide_tooltip"))
        self._close_button.setToolTip(t("close_tooltip"))
        self._subprocess_management_toggle.setToolTip(t("subprocess_management_toggle_tooltip"))
        for widget in self._entry_widgets:
            widget.retranslate()
        for widget in self._ignored_widgets:
            widget.retranslate()
            widget.set_ignore_tooltip(t("restore_tooltip"))

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if self._vertical:
            focus_prev, focus_next = Qt.Key.Key_Left, Qt.Key.Key_Right
            volume_down, volume_up = Qt.Key.Key_Down, Qt.Key.Key_Up
        else:
            focus_prev, focus_next = Qt.Key.Key_Up, Qt.Key.Key_Down
            volume_down, volume_up = Qt.Key.Key_Left, Qt.Key.Key_Right

        if key == focus_prev:
            self._model.move_focus(-1)
        elif key == focus_next:
            self._model.move_focus(1)
        elif key == volume_down:
            self._model.adjust_volume(-self._settings.get_arrow_step())
        elif key == volume_up:
            self._model.adjust_volume(self._settings.get_arrow_step())
        else:
            super().keyPressEvent(event)
            return
        self._sync_entry_widgets()
