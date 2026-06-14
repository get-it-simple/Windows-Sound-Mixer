from typing import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from sound_mixer.overlay.icons import load_icon


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        on_toggle_overlay: Callable[[bool], None],
        on_open_settings: Callable[[], None],
        on_toggle_autostart: Callable[[bool], None],
        on_exit: Callable[[], None],
        overlay_visible: bool = False,
        autostart_enabled: bool = False,
        parent: QWidget = None,
    ) -> None:
        super().__init__(load_icon("volume"), parent)
        self.setToolTip("Sound Mixer")

        menu = QMenu()

        self.toggle_overlay_action = QAction("Show Overlay", menu)
        self.toggle_overlay_action.setCheckable(True)
        self.toggle_overlay_action.setChecked(overlay_visible)
        self.toggle_overlay_action.toggled.connect(on_toggle_overlay)
        menu.addAction(self.toggle_overlay_action)

        self.settings_action = QAction("Settings...", menu)
        self.settings_action.triggered.connect(on_open_settings)
        menu.addAction(self.settings_action)

        menu.addSeparator()

        self.autostart_action = QAction("Start with Windows", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart_enabled)
        self.autostart_action.toggled.connect(on_toggle_autostart)
        menu.addAction(self.autostart_action)

        menu.addSeparator()

        self.exit_action = QAction("Exit", menu)
        self.exit_action.triggered.connect(on_exit)
        menu.addAction(self.exit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_overlay_action.trigger()

    def set_overlay_visible(self, visible: bool) -> None:
        self.toggle_overlay_action.blockSignals(True)
        self.toggle_overlay_action.setChecked(visible)
        self.toggle_overlay_action.blockSignals(False)

    def set_autostart_enabled(self, enabled: bool) -> None:
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(enabled)
        self.autostart_action.blockSignals(False)
