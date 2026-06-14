from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sound_mixer import __version__
from sound_mixer.autostart.registry import AutostartManager, AutostartUnavailableError
from sound_mixer.hotkeys.binding import normalize_combo, parse_combo
from sound_mixer.hotkeys.manager import HotkeyManager
from sound_mixer.settings.store import SettingsStore

ACTION_LABELS = {
    "toggle_overlay": "Show/Hide overlay",
    "volume_up": "Volume up",
    "volume_down": "Volume down",
    "focus_next": "Focus next entry",
    "focus_prev": "Focus previous entry",
    "mute_toggle": "Mute toggle",
}


class SettingsWindow(QDialog):
    def __init__(
        self,
        settings: SettingsStore,
        autostart: Optional[AutostartManager] = None,
        hotkeys: Optional[HotkeyManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._autostart = autostart
        self._hotkeys = hotkeys
        self._hotkey_rows: list[tuple[str, QLineEdit, QCheckBox]] = []

        self.setWindowTitle("Sound Mixer Settings")

        layout = QVBoxLayout(self)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_hotkeys_tab(), "Hotkeys")
        tabs.addTab(self._build_about_tab(), "About")
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
        form = QFormLayout(tab)

        self._autostart_checkbox = QCheckBox("Start with Windows", tab)
        self._autostart_checkbox.setChecked(self._settings.get_autostart_enabled())
        form.addRow(self._autostart_checkbox)

        self._tooltip_delay_spinbox = QSpinBox(tab)
        self._tooltip_delay_spinbox.setRange(0, 10000)
        self._tooltip_delay_spinbox.setSingleStep(100)
        self._tooltip_delay_spinbox.setSuffix(" ms")
        self._tooltip_delay_spinbox.setValue(self._settings.get_tooltip_delay_ms())
        form.addRow("Tooltip delay", self._tooltip_delay_spinbox)

        self._arrow_step_spinbox = QSpinBox(tab)
        self._arrow_step_spinbox.setRange(1, 100)
        self._arrow_step_spinbox.setSuffix(" %")
        self._arrow_step_spinbox.setValue(round(self._settings.get_arrow_step() * 100))
        form.addRow("Arrow key volume step", self._arrow_step_spinbox)

        self._scroll_step_spinbox = QSpinBox(tab)
        self._scroll_step_spinbox.setRange(1, 100)
        self._scroll_step_spinbox.setSuffix(" %")
        self._scroll_step_spinbox.setValue(round(self._settings.get_scroll_step() * 100))
        form.addRow("Scroll volume step", self._scroll_step_spinbox)

        return tab

    def _build_hotkeys_tab(self) -> QWidget:
        tab = QWidget(self)
        form = QFormLayout(tab)

        for hotkey in self._settings.get_hotkeys():
            action = hotkey["action"]
            label = ACTION_LABELS.get(action, action)

            row = QWidget(tab)
            row_layout = QFormLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            combo_edit = QLineEdit(hotkey["combo"], row)
            combo_edit.setPlaceholderText("e.g. ctrl+alt+num5")

            enabled_checkbox = QCheckBox("Enabled", row)
            enabled_checkbox.setChecked(hotkey["enabled"])

            row_layout.addRow(combo_edit)
            row_layout.addRow(enabled_checkbox)

            form.addRow(label, row)
            self._hotkey_rows.append((action, combo_edit, enabled_checkbox))

        return tab

    def _build_about_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel(f"Sound Mixer v{__version__}", tab))
        layout.addWidget(QLabel("Per-application volume mixer for Windows.", tab))
        return tab

    def accept(self) -> None:
        try:
            hotkey_updates = []
            for action, combo_edit, enabled_checkbox in self._hotkey_rows:
                combo = normalize_combo(combo_edit.text())
                parse_combo(combo)
                hotkey_updates.append((action, combo, enabled_checkbox.isChecked()))
        except ValueError as exc:
            self._error_label.setText(str(exc))
            self._error_label.show()
            return

        self._error_label.hide()

        autostart_enabled = self._autostart_checkbox.isChecked()
        self._settings.set_autostart_enabled(autostart_enabled)
        self._settings.set_tooltip_delay_ms(self._tooltip_delay_spinbox.value())
        self._settings.set_arrow_step(self._arrow_step_spinbox.value() / 100)
        self._settings.set_scroll_step(self._scroll_step_spinbox.value() / 100)

        for action, combo, enabled in hotkey_updates:
            self._settings.set_hotkey(action, combo, enabled)

        if self._autostart is not None:
            try:
                if autostart_enabled:
                    self._autostart.enable()
                else:
                    self._autostart.disable()
            except AutostartUnavailableError:
                pass

        if self._hotkeys is not None:
            self._hotkeys.reload()

        super().accept()
