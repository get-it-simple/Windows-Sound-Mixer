import copy
from uuid import uuid4

from sound_mixer.app_key import normalize_app_key
from sound_mixer.volume import clamp_volume


def audio_state(volume, muted=False):
    return {"volume": clamp_volume(float(volume)), "muted": bool(muted)}


class PresetSettings:
    def get_all_hotkeys(self) -> list[dict]:
        return [*self.get_hotkeys(), *[
            {"action": "preset:" + preset["id"], **preset["hotkey"]}
            for preset in self.get_presets()
        ]]

    def get_presets(self) -> list[dict]:
        return copy.deepcopy(self.data["presets"])

    def get_preset(self, preset_id: str | None) -> dict | None:
        return next((copy.deepcopy(p) for p in self.data["presets"] if p["id"] == preset_id), None)

    def get_active_preset_id(self) -> str | None:
        return self.data["active_preset_id"]

    def set_active_preset_id(self, preset_id: str | None) -> None:
        if preset_id is not None and self.get_preset(preset_id) is None:
            raise ValueError("Unknown preset")
        self.data["active_preset_id"] = preset_id
        self._request_save()

    def create_preset(self, name: str, volume: float, muted: bool = False) -> dict:
        preset = {
            "id": uuid4().hex, "name": name.strip() or "Preset", "apps": {},
            "master_volume": clamp_volume(volume), "master_muted": bool(muted),
            "isolated_app": None, "hotkey": {"combo": "", "enabled": False},
        }
        self.set_presets([*self.get_presets(), preset])
        return copy.deepcopy(preset)

    def set_presets(self, presets: list[dict], *, persist: bool = True) -> None:
        normalized = []
        seen = set()
        for source in presets:
            preset = copy.deepcopy(source)
            preset_id = str(preset.get("id") or uuid4().hex)
            if preset_id in seen:
                continue
            seen.add(preset_id)
            apps = {
                normalize_app_key(key): audio_state(value.get("volume", 1), value.get("muted", False))
                for key, value in preset.get("apps", {}).items()
            }
            isolated = preset.get("isolated_app")
            isolated = normalize_app_key(isolated) if isolated else None
            binding = preset.get("hotkey", {})
            normalized.append({
                "id": preset_id, "name": str(preset.get("name", "")).strip() or "Preset",
                "apps": apps, "master_volume": clamp_volume(preset.get("master_volume", 1)),
                "master_muted": bool(preset.get("master_muted", False)),
                "isolated_app": isolated if isolated in apps and self.is_app_whitelisted(isolated) else None,
                "hotkey": {"combo": str(binding.get("combo", "")), "enabled": bool(binding.get("enabled", False))},
            })
        self.data["presets"] = normalized
        if self.get_active_preset_id() not in seen:
            self.data["active_preset_id"] = None
        if persist:
            self._request_save()

    def delete_preset(self, preset_id: str) -> None:
        self.set_presets([p for p in self.get_presets() if p["id"] != preset_id])

    def get_profile_app_state(self, key: str) -> tuple[float, bool]:
        key = normalize_app_key(key)
        preset = self.get_preset(self.get_active_preset_id())
        if preset and self.is_app_whitelisted(key) and key in preset["apps"]:
            state = preset["apps"][key]
            return state["volume"], state["muted"]
        return self.get_app_volume(key), self.get_app_muted(key)

    def set_profile_app_state(self, key: str, volume: float, muted: bool) -> None:
        key = normalize_app_key(key)
        state = audio_state(volume, muted)
        preset_id = self.get_active_preset_id()
        if preset_id is not None and self.is_app_whitelisted(key):
            preset = next(p for p in self.data["presets"] if p["id"] == preset_id)
            if preset["apps"].get(key) != state:
                preset["apps"][key] = state
                self._request_save()
        else:
            self.set_app_volume(key, volume)
            self.set_app_muted(key, muted)

    def get_profile_master_state(self) -> tuple[float, bool]:
        preset = self.get_preset(self.get_active_preset_id())
        source = preset if preset is not None else self.data
        return source["master_volume"], source["master_muted"]

    def set_profile_master_state(self, volume: float, muted: bool) -> None:
        preset_id = self.get_active_preset_id()
        source = next((p for p in self.data["presets"] if p["id"] == preset_id), self.data)
        state = (clamp_volume(volume), bool(muted))
        if (source["master_volume"], source["master_muted"]) != state:
            source["master_volume"], source["master_muted"] = state
            self._request_save()
