from time import monotonic

from PySide6.QtWidgets import QSystemTrayIcon

from sound_mixer.app_key import legacy_app_key
from sound_mixer.i18n import t


class IsolationNotifications:
    def __init__(self, tray, settings, model, clock=monotonic):
        self.tray = tray
        self.settings = settings
        self.model = model
        self.clock = clock
        self.last_shown = float("-inf")

    def _name(self, key):
        for entry in self.model.entries + self.model.ignored_entries:
            if entry.key == key:
                return entry.display_name
        return legacy_app_key(key)

    def show_blocked(self, event):
        preset = self.settings.get_preset(event.preset_id)
        if preset is None or event.preset_id != self.model.active_preset_id:
            return
        now = self.clock()
        if now - self.last_shown < 10:
            return
        self.last_shown = now
        self.tray.showMessage(
            t("isolation_notification_title"),
            t("isolation_notification_body").format(
                app=self._name(event.app_key), preset=preset["name"], target=self._name(event.isolated_app),
            ),
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )
