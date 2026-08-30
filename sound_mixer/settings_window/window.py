from typing import Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sound_mixer import __version__
from sound_mixer.autostart.registry import AutostartManager, AutostartUnavailableError
from sound_mixer.hotkeys.binding import normalize_combo, parse_combo
from sound_mixer.hotkeys.manager import HotkeyManager
from sound_mixer.i18n import AVAILABLE_LANGUAGES, language_display_name, t
from sound_mixer.mixer.subprocess_manager import SubprocessManager
from sound_mixer.overlay.icons import bordered_input_style, icon_path, load_icon, toggle_switch_style
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings.schema import (
    LAYOUT_HORIZONTAL,
    LAYOUT_VERTICAL,
    MAX_UI_SCALE,
    MIN_UI_SCALE,
)
from sound_mixer.settings.store import SettingsStore
from sound_mixer.settings_window.managed_apps_editor import AppListEditor, ManagedAppRow

MODIFIER_OPTIONS = [
    ("", "Select"),
    ("ctrl", "Ctrl (Left)"),
    ("ctrl", "Ctrl (Right)"),
    ("alt", "Alt (Left)"),
    ("alt", "Alt (Right)"),
    ("shift", "Shift (Left)"),
    ("shift", "Shift (Right)"),
    ("win", "Win (Left)"),
    ("win", "Win (Right)"),
]

KEY_OPTIONS = [
    ("", "Select"),
    *[(chr(c), chr(c).upper()) for c in range(ord("a"), ord("z") + 1)],
    *[(str(d), str(d)) for d in range(10)],
    *[(f"num{d}", f"NumPad {d}") for d in range(10)],
    *[(f"f{n}", f"F{n}") for n in range(1, 25)],
    ("up", "Up"),
    ("down", "Down"),
    ("left", "Left"),
    ("right", "Right"),
    ("space", "Space"),
    ("enter", "Enter"),
    ("esc", "Esc"),
    ("tab", "Tab"),
    ("backspace", "Backspace"),
    ("delete", "Delete"),
    ("insert", "Insert"),
    ("home", "Home"),
    ("end", "End"),
    ("page up", "Page Up"),
    ("page down", "Page Down"),
    ("caps lock", "Caps Lock"),
    ("print screen", "Print Screen"),
    ("scroll lock", "Scroll Lock"),
    ("pause", "Pause"),
    ("num lock", "Num Lock"),
]


def _action_labels() -> dict[str, str]:
    return {
        "toggle_overlay": t("action_toggle_overlay"),
        "toggle_mini_widget": t("action_toggle_mini_widget"),
        "volume_up": t("action_volume_up"),
        "volume_down": t("action_volume_down"),
        "focus_next": t("action_focus_next"),
        "focus_prev": t("action_focus_prev"),
        "mute_toggle": t("action_mute_toggle"),
    }


class HotkeyComboEditor(QFrame):
    def __init__(self, combo: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._select_boxes: list[QComboBox] = []
        self._syncing = False

        self.setObjectName("hotkeyComboInput")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(bordered_input_style("hotkeyComboInput"))

        self._select_layout = QHBoxLayout(self)
        self._select_layout.setContentsMargins(10, 10, 10, 10)
        self._select_layout.setSpacing(4)

        self._placeholder_label = QLabel(t("press_shortcut"), self)
        self._placeholder_label.setStyleSheet("color: #b7b7bd; padding-left: 2px;")
        self._select_layout.addWidget(self._placeholder_label)
        self._select_layout.addStretch(1)

        self.set_combo(combo)

    def combo(self) -> str:
        return "+".join(box.currentData() for box in self._select_boxes if box.currentData())

    def set_combo(self, combo: str) -> None:
        try:
            tokens = parse_combo(combo)
        except ValueError:
            tokens = []
        self._set_tokens(tokens)

    def clear(self) -> None:
        self._set_tokens([])
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.clear()
            event.accept()
            return
        tokens = self._tokens_from_event(event)
        if tokens:
            self._set_tokens(tokens)
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.clear()
            return True
        if watched in self._select_boxes and event.type() == QEvent.Type.KeyPress:
            tokens = self._tokens_from_event(event)
            if len(tokens) > 1:
                self._set_tokens(tokens)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        self.setFocus()
        super().mousePressEvent(event)

    def _set_tokens(self, tokens: list[str]) -> None:
        self._syncing = True
        self._clear_select_boxes()
        for token in tokens:
            box = self._create_box(self._options_for_token(token))
            self._set_box_value(box, token)
            self._select_boxes.append(box)
            self._select_layout.insertWidget(self._select_layout.count() - 1, box)

        self._placeholder_label.setVisible(not self._select_boxes)
        self._syncing = False

    def _clear_select_boxes(self) -> None:
        while self._select_boxes:
            box = self._select_boxes.pop()
            self._select_layout.removeWidget(box)
            box.setParent(None)
            box.deleteLater()

    def _create_box(self, options: list[tuple[str, str]]) -> QComboBox:
        box = QComboBox(self)
        box.setMinimumHeight(32)
        box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        arrow_path = icon_path("dropdown_arrow").replace("\\", "/")
        box.setStyleSheet(
            f"""
            QComboBox {{
                background: #626071;
                border: 0;
                border-radius: 7px;
                color: #f2f2f5;
                padding: 5px 20px 5px 9px;
            }}
            QComboBox:hover {{
                background: #716f82;
            }}
            QComboBox:focus {{
                background: #78758a;
            }}
            QComboBox::drop-down {{
                border: 0;
                width: 18px;
            }}
            QComboBox::down-arrow {{
                image: url({arrow_path});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background: #2d2d30;
                border: 1px solid #56565c;
                color: #f2f2f5;
                selection-background-color: #626071;
            }}
            """
        )
        for value, label in options:
            box.addItem(label, value)
        box.currentIndexChanged.connect(self._sync_select_options)
        box.installEventFilter(self)
        return box

    def _options_for_token(self, token: str) -> list[tuple[str, str]]:
        if token in {"ctrl", "alt", "shift", "win"}:
            return MODIFIER_OPTIONS
        return KEY_OPTIONS

    def _set_box_value(self, box: QComboBox, value: str) -> None:
        index = box.findData(value)
        box.setCurrentIndex(index if index >= 0 else 0)

    def _sync_select_options(self) -> None:
        if self._syncing:
            return
        tokens = [box.currentData() for box in self._select_boxes if box.currentData()]
        modifiers = []
        keys = []
        for token in tokens:
            if token in {"ctrl", "alt", "shift", "win"} and token not in modifiers:
                modifiers.append(token)
            elif token not in {"ctrl", "alt", "shift", "win"} and not keys:
                keys.append(token)
        self._set_tokens(modifiers + keys)

    def _tokens_from_event(self, event) -> list[str]:
        key = self._key_token_from_event(event)
        tokens = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            tokens.append("ctrl")
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            tokens.append("alt")
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            tokens.append("shift")
        if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            tokens.append("win")
        if key and key not in tokens:
            tokens.append(key)
        return tokens

    def _key_token_from_event(self, event) -> str:
        key = event.key()
        text = event.text().lower()
        if len(text) == 1 and text.isalpha():
            return text
        if len(text) == 1 and text.isdigit():
            if event.modifiers() & Qt.KeyboardModifier.KeypadModifier:
                return f"num{text}"
            return text

        key_map = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "page up",
            Qt.Key.Key_PageDown: "page down",
            Qt.Key.Key_CapsLock: "caps lock",
            Qt.Key.Key_Print: "print screen",
            Qt.Key.Key_ScrollLock: "scroll lock",
            Qt.Key.Key_Pause: "pause",
            Qt.Key.Key_NumLock: "num lock",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Down: "down",
        }
        if int(Qt.Key.Key_F1) <= key <= int(Qt.Key.Key_F24):
            return f"f{key - int(Qt.Key.Key_F1) + 1}"
        return key_map.get(key, "")


class SettingsWindow(QDialog):
    def __init__(
        self,
        settings: SettingsStore,
        autostart: Optional[AutostartManager] = None,
        hotkeys: Optional[HotkeyManager] = None,
        overlay: Optional[OverlayWindow] = None,
        mini_widget: Optional[MiniWidget] = None,
        subprocess_manager: Optional[SubprocessManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._autostart = autostart
        self._hotkeys = hotkeys
        self._overlay = overlay
        self._mini_widget = mini_widget
        self._subprocess_manager = subprocess_manager
        self._hotkey_rows: list[tuple[str, HotkeyComboEditor, QCheckBox]] = []
        self._managed_app_rows: list[ManagedAppRow] = []

        self.setWindowTitle(t("settings_title"))
        self.setWindowIcon(load_icon("logo"))

        layout = QVBoxLayout(self)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), t("tab_general"))
        tabs.addTab(self._build_hotkeys_tab(), t("tab_hotkeys"))
        tabs.addTab(self._build_whitelist_tab(), t("tab_whitelist"))
        tabs.addTab(self._build_subprocess_management_tab(), t("tab_subprocess_management"))
        tabs.addTab(self._build_about_tab(), t("tab_about"))
        layout.addWidget(tabs)

        self._error_label = QLabel(self)
        self._error_label.setStyleSheet("color: #ff5555;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        self._autostart_checkbox = QCheckBox(tab)
        self._autostart_checkbox.setObjectName("autostartToggle")
        self._autostart_checkbox.setStyleSheet(toggle_switch_style("autostartToggle"))
        self._autostart_checkbox.setChecked(self._settings.get_autostart_enabled())
        layout.addWidget(self._field(t("start_with_windows"), self._autostart_checkbox, tab))

        self._start_opened_checkbox = QCheckBox(tab)
        self._start_opened_checkbox.setObjectName("startOpenedToggle")
        self._start_opened_checkbox.setStyleSheet(toggle_switch_style("startOpenedToggle"))
        self._start_opened_checkbox.setChecked(self._settings.get_visible_on_start())
        layout.addWidget(self._field(t("start_opened"), self._start_opened_checkbox, tab))

        self._transparency_checkbox = QCheckBox(tab)
        self._transparency_checkbox.setObjectName("transparencyToggle")
        self._transparency_checkbox.setStyleSheet(toggle_switch_style("transparencyToggle"))
        self._transparency_checkbox.setChecked(self._settings.get_transparency_enabled())
        layout.addWidget(self._field(t("transparent_overlay_background"), self._transparency_checkbox, tab))

        self._mini_widget_checkbox = QCheckBox(tab)
        self._mini_widget_checkbox.setObjectName("miniWidgetToggle")
        self._mini_widget_checkbox.setStyleSheet(toggle_switch_style("miniWidgetToggle"))
        self._mini_widget_checkbox.setChecked(self._settings.get_mini_widget_enabled())
        layout.addWidget(self._field(t("show_mini_widget"), self._mini_widget_checkbox, tab))

        self._tooltip_delay_spinbox = QSpinBox(tab)
        self._tooltip_delay_spinbox.setRange(0, 10000)
        self._tooltip_delay_spinbox.setSingleStep(100)
        self._tooltip_delay_spinbox.setSuffix(" ms")
        self._tooltip_delay_spinbox.setValue(self._settings.get_tooltip_delay_ms())
        layout.addWidget(self._field(t("tooltip_delay"), self._tooltip_delay_spinbox, tab))

        self._arrow_step_spinbox = QSpinBox(tab)
        self._arrow_step_spinbox.setRange(1, 100)
        self._arrow_step_spinbox.setSuffix(" %")
        self._arrow_step_spinbox.setValue(round(self._settings.get_arrow_step() * 100))
        layout.addWidget(self._field(t("arrow_key_volume_step"), self._arrow_step_spinbox, tab))

        self._scroll_step_spinbox = QSpinBox(tab)
        self._scroll_step_spinbox.setRange(1, 100)
        self._scroll_step_spinbox.setSuffix(" %")
        self._scroll_step_spinbox.setValue(round(self._settings.get_scroll_step() * 100))
        layout.addWidget(self._field(t("scroll_volume_step"), self._scroll_step_spinbox, tab))

        self._default_app_volume_spinbox = QSpinBox(tab)
        self._default_app_volume_spinbox.setRange(0, 100)
        self._default_app_volume_spinbox.setSuffix(" %")
        self._default_app_volume_spinbox.setValue(round(self._settings.get_default_app_volume() * 100))
        layout.addWidget(self._field(t("default_volume_for_new_apps"), self._default_app_volume_spinbox, tab))

        scale_row = QWidget(tab)
        scale_layout = QHBoxLayout(scale_row)
        scale_layout.setContentsMargins(0, 0, 0, 0)

        self._ui_scale_slider = QSlider(Qt.Orientation.Horizontal, scale_row)
        self._ui_scale_slider.setRange(round(MIN_UI_SCALE * 100), round(MAX_UI_SCALE * 100))
        self._ui_scale_slider.setSingleStep(10)
        self._ui_scale_slider.setValue(round(self._settings.get_ui_scale() * 100))

        self._ui_scale_label = QLabel(f"{self._ui_scale_slider.value()}%", scale_row)
        self._ui_scale_label.setMinimumWidth(40)

        self._ui_scale_slider.valueChanged.connect(self._on_ui_scale_changed)

        scale_layout.addWidget(self._ui_scale_slider)
        scale_layout.addWidget(self._ui_scale_label)
        layout.addWidget(self._field(t("overlay_scale"), scale_row, tab))

        mini_scale_row = QWidget(tab)
        mini_scale_layout = QHBoxLayout(mini_scale_row)
        mini_scale_layout.setContentsMargins(0, 0, 0, 0)

        self._mini_widget_scale_slider = QSlider(Qt.Orientation.Horizontal, mini_scale_row)
        self._mini_widget_scale_slider.setRange(round(MIN_UI_SCALE * 100), round(MAX_UI_SCALE * 100))
        self._mini_widget_scale_slider.setSingleStep(10)
        self._mini_widget_scale_slider.setValue(round(self._settings.get_mini_widget_scale() * 100))

        self._mini_widget_scale_label = QLabel(f"{self._mini_widget_scale_slider.value()}%", mini_scale_row)
        self._mini_widget_scale_label.setMinimumWidth(40)

        self._mini_widget_scale_slider.valueChanged.connect(self._on_mini_widget_scale_changed)

        mini_scale_layout.addWidget(self._mini_widget_scale_slider)
        mini_scale_layout.addWidget(self._mini_widget_scale_label)
        layout.addWidget(self._field(t("mini_widget_scale"), mini_scale_row, tab))

        self._layout_mode_combo = QComboBox(tab)
        self._layout_mode_combo.addItem(t("layout_horizontal"), LAYOUT_HORIZONTAL)
        self._layout_mode_combo.addItem(t("layout_vertical"), LAYOUT_VERTICAL)
        mode_index = self._layout_mode_combo.findData(self._settings.get_layout_mode())
        if mode_index >= 0:
            self._layout_mode_combo.setCurrentIndex(mode_index)
        layout.addWidget(self._field(t("overlay_layout"), self._layout_mode_combo, tab))

        self._language_combo = QComboBox(tab)
        self._language_combo.addItem(t("language_system"), "system")
        for lang_code in AVAILABLE_LANGUAGES:
            self._language_combo.addItem(language_display_name(lang_code), lang_code)
        current_language = self._settings.get_language()
        idx = self._language_combo.findData(current_language)
        if idx >= 0:
            self._language_combo.setCurrentIndex(idx)
        layout.addWidget(self._field(t("language"), self._language_combo, tab))

        self._guide_button = QPushButton(t("controls_guide_button"), tab)
        self._guide_button.clicked.connect(self._show_guide)
        layout.addWidget(self._guide_button)
        layout.addStretch(1)

        return tab

    def _on_ui_scale_changed(self, value: int) -> None:
        self._ui_scale_label.setText(f"{value}%")
        self._settings.set_ui_scale(value / 100)
        if self._overlay is not None:
            self._overlay.apply_scale()

    def _on_mini_widget_scale_changed(self, value: int) -> None:
        self._mini_widget_scale_label.setText(f"{value}%")
        self._settings.set_mini_widget_scale(value / 100)
        if self._mini_widget is not None:
            self._mini_widget.apply_scale()

    def _build_hotkeys_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        labels = _action_labels()
        for hotkey in self._settings.get_hotkeys():
            action = hotkey["action"]
            label = labels.get(action, action)

            row = QWidget(tab)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            combo_edit = HotkeyComboEditor(hotkey["combo"], row)

            enabled_checkbox = QCheckBox(row)
            enabled_checkbox.setObjectName(f"{action}HotkeyToggle")
            enabled_checkbox.setStyleSheet(toggle_switch_style(f"{action}HotkeyToggle"))
            enabled_checkbox.setChecked(hotkey["enabled"])

            row_layout.addWidget(enabled_checkbox)
            row_layout.addWidget(combo_edit, 1)

            layout.addWidget(self._field(label, row, tab))
            self._hotkey_rows.append((action, combo_edit, enabled_checkbox))

        layout.addStretch(1)
        return tab

    def _build_subprocess_management_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        self._subprocess_interval_spinbox = QSpinBox(tab)
        self._subprocess_interval_spinbox.setRange(1, 3600)
        self._subprocess_interval_spinbox.setSuffix(" s")
        self._subprocess_interval_spinbox.setValue(self._settings.get_subprocess_management_interval_seconds())
        layout.addWidget(self._field(t("subprocess_scan_interval"), self._subprocess_interval_spinbox, tab))

        editor = AppListEditor(self._settings.get_managed_apps(), tab)
        layout.addWidget(editor)
        self._managed_apps_editor = editor
        self._managed_app_drop_zone = editor.drop_zone
        self._managed_app_rows_layout = editor.rows_layout
        self._managed_app_rows = editor.rows

        layout.addStretch(1)
        return tab

    def _on_managed_app_dropped(self, path: str) -> None:
        self._managed_apps_editor.add_path(path)

    def _add_managed_app_row(self, path: str, enabled: bool) -> None:
        self._managed_apps_editor.add_row(path, enabled)

    def _remove_managed_app_row(self, row: ManagedAppRow) -> None:
        self._managed_apps_editor.remove_row(row)

    def _build_whitelist_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        self._whitelist_checkbox = QCheckBox(tab)
        self._whitelist_checkbox.setObjectName("whitelistToggle")
        self._whitelist_checkbox.setStyleSheet(toggle_switch_style("whitelistToggle"))
        self._whitelist_checkbox.setChecked(self._settings.get_whitelist_enabled())
        layout.addWidget(self._field(t("whitelist_mode"), self._whitelist_checkbox, tab))

        editor = AppListEditor(self._settings.get_whitelist_apps(), tab)
        layout.addWidget(editor)
        layout.addStretch(1)
        self._whitelist_editor = editor
        self._whitelist_app_rows = editor.rows
        return tab

    def _build_about_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo_label = QLabel(tab)
        logo_label.setPixmap(load_icon("logo").pixmap(64, 64))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(logo_label)

        layout.addWidget(QLabel(f"Sound Mixer v{__version__}", tab))
        layout.addWidget(QLabel(t("app_description"), tab))
        return tab

    def _show_guide(self) -> None:
        from sound_mixer.overlay.guide import GuideDialog

        GuideDialog(vertical=self._layout_mode_combo.currentData() == LAYOUT_VERTICAL, parent=self).exec()

    def accept(self) -> None:
        try:
            hotkey_updates = []
            for action, combo_edit, enabled_checkbox in self._hotkey_rows:
                combo = normalize_combo(combo_edit.combo())
                parse_combo(combo)
                hotkey_updates.append((action, combo, enabled_checkbox.isChecked()))
        except ValueError as exc:
            self._error_label.setText(str(exc))
            self._error_label.show()
            return

        self._error_label.hide()

        autostart_enabled = self._autostart_checkbox.isChecked()
        self._settings.set_autostart_enabled(autostart_enabled)
        self._settings.set_visible_on_start(self._start_opened_checkbox.isChecked())
        self._settings.set_transparency_enabled(self._transparency_checkbox.isChecked())
        self._settings.set_mini_widget_enabled(self._mini_widget_checkbox.isChecked())
        self._settings.set_tooltip_delay_ms(self._tooltip_delay_spinbox.value())
        self._settings.set_arrow_step(self._arrow_step_spinbox.value() / 100)
        self._settings.set_scroll_step(self._scroll_step_spinbox.value() / 100)
        self._settings.set_default_app_volume(self._default_app_volume_spinbox.value() / 100)
        self._settings.set_language(self._language_combo.currentData())
        self._settings.set_subprocess_management_interval_seconds(self._subprocess_interval_spinbox.value())
        self._settings.set_managed_apps(self._managed_apps_editor.apps())
        self._settings.set_whitelist_enabled(self._whitelist_checkbox.isChecked())
        self._settings.set_whitelist_apps(self._whitelist_editor.apps())

        for action, combo, enabled in hotkey_updates:
            self._settings.set_hotkey(action, combo, enabled)

        if self._autostart is not None:
            try:
                self._autostart.set_enabled(autostart_enabled)
            except AutostartUnavailableError:
                pass

        if self._hotkeys is not None:
            self._hotkeys.reload()

        layout_mode = self._layout_mode_combo.currentData()
        if self._overlay is not None:
            self._overlay.set_layout_mode(layout_mode)
            self._overlay.apply_scale()
        else:
            self._settings.set_layout_mode(layout_mode)

        if self._subprocess_manager is not None:
            self._subprocess_manager.sync()

        super().accept()

    def _field(self, label: str, control: QWidget, parent: QWidget) -> QWidget:
        field = QWidget(parent)
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(4)
        layout.addWidget(QLabel(label, field))
        layout.addWidget(control)
        return field
