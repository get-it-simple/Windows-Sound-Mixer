import sys

from PySide6.QtWidgets import QApplication

from sound_mixer.audio import create_backend
from sound_mixer.autostart.registry import AutostartManager, AutostartUnavailableError
from sound_mixer.hotkeys.manager import HotkeyManager
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.paths import default_settings_path
from sound_mixer.settings.store import SettingsStore
from sound_mixer.settings_window.window import SettingsWindow
from sound_mixer.tray.tray_icon import TrayIcon


class SoundMixerApp:
    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.settings = SettingsStore(default_settings_path())
        self.settings.load()
        self.backend = create_backend()
        self.model = MixerModel(self.backend, self.settings)
        self.overlay = OverlayWindow(self.model, self.settings)
        self.overlay.visibility_changed.connect(self._on_overlay_visibility_changed)
        self.overlay.settings_requested.connect(self._open_settings)

        self.hotkeys = HotkeyManager(self.settings)
        self.hotkeys.toggle_overlay.connect(self._on_toggle_overlay_hotkey)
        self.hotkeys.volume_up.connect(self._on_volume_up_hotkey)
        self.hotkeys.volume_down.connect(self._on_volume_down_hotkey)
        self.hotkeys.focus_next.connect(self._on_focus_next_hotkey)
        self.hotkeys.focus_prev.connect(self._on_focus_prev_hotkey)
        self.hotkeys.mute_toggle.connect(self._on_mute_toggle_hotkey)
        self.hotkeys.start()

        self.autostart = AutostartManager()
        self._sync_autostart()

        self.tray = TrayIcon(
            on_toggle_overlay=self._set_overlay_visible,
            on_open_settings=self._open_settings,
            on_toggle_autostart=self._set_autostart_enabled,
            on_exit=self.qt_app.quit,
            overlay_visible=self.settings.get_overlay_geometry()["visible_on_start"],
            autostart_enabled=self.settings.get_autostart_enabled(),
        )
        self.tray.show()

    def _set_overlay_visible(self, visible: bool) -> None:
        if visible:
            self.overlay.show()
        else:
            self.overlay.hide()

    def _on_overlay_visibility_changed(self, visible: bool) -> None:
        self.tray.set_overlay_visible(visible)

    def _open_settings(self) -> None:
        self.hotkeys.stop()
        accepted = False
        dialog = SettingsWindow(
            self.settings,
            autostart=self.autostart,
            hotkeys=self.hotkeys,
            overlay=self.overlay,
            parent=self.overlay,
        )
        try:
            accepted = dialog.exec() == SettingsWindow.DialogCode.Accepted
            if accepted:
                self.tray.set_autostart_enabled(self.settings.get_autostart_enabled())
        finally:
            if not accepted:
                self.hotkeys.start()

    def _sync_autostart(self) -> None:
        try:
            if self.settings.get_autostart_enabled():
                self.autostart.enable()
            else:
                self.autostart.disable()
        except AutostartUnavailableError:
            pass

    def _set_autostart_enabled(self, enabled: bool) -> None:
        self.settings.set_autostart_enabled(enabled)
        try:
            if enabled:
                self.autostart.enable()
            else:
                self.autostart.disable()
        except AutostartUnavailableError:
            pass

    def _on_toggle_overlay_hotkey(self) -> None:
        self.tray.toggle_overlay_action.trigger()

    def _on_volume_up_hotkey(self) -> None:
        self.model.adjust_volume(self.settings.get_arrow_step())
        self.overlay.refresh_view()

    def _on_volume_down_hotkey(self) -> None:
        self.model.adjust_volume(-self.settings.get_arrow_step())
        self.overlay.refresh_view()

    def _on_focus_next_hotkey(self) -> None:
        self.model.move_focus(1)
        self.overlay.refresh_view()

    def _on_focus_prev_hotkey(self) -> None:
        self.model.move_focus(-1)
        self.overlay.refresh_view()

    def _on_mute_toggle_hotkey(self) -> None:
        self.model.toggle_mute()
        self.overlay.refresh_view()

    def run(self) -> int:
        if self.settings.get_overlay_geometry()["visible_on_start"]:
            self.overlay.show()
        try:
            return self.qt_app.exec()
        finally:
            self.hotkeys.stop()
