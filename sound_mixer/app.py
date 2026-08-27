import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import sound_mixer.i18n as i18n
from sound_mixer.audio import create_backend
from sound_mixer.autostart.registry import AutostartManager, AutostartUnavailableError
from sound_mixer.hotkeys.manager import HotkeyManager
from sound_mixer.instance_control import InstanceController
from sound_mixer.mixer.model import MixerModel
from sound_mixer.mixer.subprocess_manager import SubprocessManager
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.paths import default_settings_path
from sound_mixer.settings.store import SettingsStore
from sound_mixer.settings_window.window import SettingsWindow
from sound_mixer.tray.tray_icon import TrayIcon

SETTINGS_SAVE_DELAY_MS = 500


def install_deferred_saves(settings: SettingsStore, qt_app) -> QTimer:
    timer = QTimer(qt_app)
    timer.setSingleShot(True)
    timer.timeout.connect(settings.flush)
    settings.set_save_scheduler(lambda: timer.isActive() or timer.start(SETTINGS_SAVE_DELAY_MS))
    qt_app.aboutToQuit.connect(settings.flush)
    return timer


class SoundMixerApp:
    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.instance_controller = InstanceController(self._shutdown_for_update, self.qt_app)
        self._is_primary_instance = self.instance_controller.start()
        if not self._is_primary_instance:
            return

        self.settings = SettingsStore(default_settings_path())
        self.settings.load()
        install_deferred_saves(self.settings, self.qt_app)
        i18n.setup(self.settings.get_language())
        self.backend = create_backend()
        self.model = MixerModel(self.backend, self.settings)
        self.subprocess_manager = SubprocessManager(self.settings, self._on_subprocess_manager_tick, parent=self.qt_app)
        self.subprocess_manager.sync()
        self.overlay = OverlayWindow(self.model, self.settings, subprocess_manager=self.subprocess_manager)
        self.overlay.visibility_changed.connect(self._on_overlay_visibility_changed)
        self.overlay.settings_requested.connect(self._open_settings)
        self.mini_widget = MiniWidget(self.model, self.settings)
        self.overlay.model_changed.connect(self.mini_widget.refresh_view)
        self.mini_widget.model_changed.connect(self.overlay.refresh_view)
        self.mini_widget.set_enabled(self.settings.get_mini_widget_enabled(), persist=False)

        self.hotkeys = HotkeyManager(self.settings)
        self.hotkeys.toggle_overlay.connect(self._on_toggle_overlay_hotkey)
        self.hotkeys.toggle_mini_widget.connect(self._on_toggle_mini_widget_hotkey)
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
            overlay_visible=self.settings.get_visible_on_start(),
            autostart_enabled=self.settings.get_autostart_enabled(),
            muted=self.model.is_master_muted(),
        )
        self.tray.show()
        self.model.set_master_mute_listener(self.tray.set_muted)

    def _shutdown_for_update(self) -> None:
        self.settings.flush()
        QTimer.singleShot(0, self.qt_app.quit)

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
            mini_widget=getattr(self, "mini_widget", None),
            subprocess_manager=self.subprocess_manager,
            parent=self.overlay,
        )
        try:
            accepted = dialog.exec() == SettingsWindow.DialogCode.Accepted
            if accepted:
                i18n.setup(self.settings.get_language())
                if self.overlay is not None:
                    self.overlay.retranslate()
                    self.overlay.sync_subprocess_management_toggle()
                    self.model.refresh()
                    self.overlay.refresh_view()
                mini_widget = getattr(self, "mini_widget", None)
                if mini_widget is not None:
                    mini_widget.retranslate()
                    mini_widget.sync_from_settings()
                self.tray.retranslate()
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

    def _on_toggle_mini_widget_hotkey(self) -> None:
        self.mini_widget.set_enabled(not self.mini_widget.is_enabled())

    def _refresh_views(self) -> None:
        self.overlay.refresh_view()
        self.mini_widget.refresh_view()

    def _on_volume_up_hotkey(self) -> None:
        self.model.adjust_volume(self.settings.get_arrow_step())
        self._refresh_views()

    def _on_volume_down_hotkey(self) -> None:
        self.model.adjust_volume(-self.settings.get_arrow_step())
        self._refresh_views()

    def _on_focus_next_hotkey(self) -> None:
        self.model.move_focus(1)
        self._refresh_views()

    def _on_focus_prev_hotkey(self) -> None:
        self.model.move_focus(-1)
        self._refresh_views()

    def _on_mute_toggle_hotkey(self) -> None:
        self.model.toggle_mute()
        self._refresh_views()

    def _on_subprocess_manager_tick(self) -> None:
        self.model.refresh()
        self._refresh_views()

    def run(self) -> int:
        if not self._is_primary_instance:
            return 0
        if self.settings.get_visible_on_start():
            self.overlay.show_on_start()
        try:
            return self.qt_app.exec()
        finally:
            self.hotkeys.stop()
            self.mini_widget.stop()
            self.settings.flush()
            self.instance_controller.close()
