from dataclasses import dataclass

from sound_mixer.settings.presets import audio_state


@dataclass(frozen=True)
class IsolationBlocked:
    app_key: str
    preset_id: str
    isolated_app: str


class IsolationPolicy:
    def __init__(self, settings):
        self.settings = settings
        self.target = None
        self.on_blocked = None
        self.sync()

    def sync(self) -> bool:
        preset = self.settings.get_preset(self.settings.get_active_preset_id())
        target = preset["isolated_app"] if preset else None
        if target and (target not in preset["apps"] or not self.settings.is_app_whitelisted(target)):
            presets = self.settings.get_presets()
            for item in presets:
                if item["id"] == preset["id"]:
                    item["isolated_app"] = None
            self.settings.set_presets(presets)
            target = None
        changed = self.target != target
        self.target = target
        if not target and self.settings.data["isolation_restore"]:
            for key, state in self.settings.data["isolation_restore"].items():
                if key not in self.settings.data["app_volumes"]:
                    self.settings.set_app_volume(key, state["volume"])
                    self.settings.set_app_muted(key, state["muted"])
            self.settings.data["isolation_restore"] = {}
            self.settings._request_save()
        return changed

    def is_blocked(self, key: str) -> bool:
        return self.target is not None and key != self.target and key != "master"

    def effective_state(self, key: str) -> tuple[float, bool]:
        volume, muted = self.settings.get_profile_app_state(key)
        if self.is_blocked(key):
            restore = self.settings.data["isolation_restore"]
            if key not in restore:
                restore[key] = audio_state(self.settings.get_app_volume(key), self.settings.get_app_muted(key))
                self.settings.save()
            return 0.0, muted
        return volume, muted

    def notify_blocked(self, key: str) -> None:
        if self.on_blocked is not None:
            self.on_blocked(IsolationBlocked(key, self.settings.get_active_preset_id(), self.target))
