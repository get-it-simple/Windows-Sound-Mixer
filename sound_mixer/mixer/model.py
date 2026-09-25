from dataclasses import dataclass
from math import isclose
from typing import Callable, Optional
from time import perf_counter

from sound_mixer.audio.interface import AudioBackend
from sound_mixer.mixer.isolation import IsolationPolicy
from sound_mixer.i18n import t
from sound_mixer.settings.store import SettingsStore
from sound_mixer.volume import clamp_volume

MASTER_KEY = "master"
MASTER_DISPLAY_NAME = "System"


def states_equal(first, second) -> bool:
    return first is not None and first[1] == second[1] and isclose(first[0], second[0], abs_tol=1e-6)


@dataclass
class MixerEntry:
    key: str
    display_name: str
    volume: float
    muted: bool
    is_master: bool = False
    icon_path: str = ""
    pids: tuple[int, ...] = ()
    volume_locked: bool = False


class MixerModel:
    def __init__(self, backend: AudioBackend, settings: SettingsStore):
        self._backend = backend
        self._settings = settings
        self.isolation = IsolationPolicy(settings)
        self._known_ids: set[str] = set()
        self._sessions_by_id = {}
        self._sessions_by_key = {}
        self._ready_at = {}
        self._last_change = {}
        self._observed_states = {}
        self._master_changed_at = 0.0
        self.entries: list[MixerEntry] = []
        self.ignored_entries: list[MixerEntry] = []
        self.focused_index = 0
        self._on_master_mute_changed: Optional[Callable[[bool], None]] = None
        self._last_master_muted: Optional[bool] = None
        self._master_refresh_scheduler: Optional[Callable[[], None]] = None
        self.refresh(include_master=False)
        if self._settings.get_active_preset_id() is not None:
            self._apply_master_profile()
        else:
            self.refresh_master()

    @property
    def active_preset_id(self) -> str | None:
        return self._settings.get_active_preset_id()

    @property
    def mode_name(self) -> str:
        preset = self._settings.get_preset(self.active_preset_id)
        return preset["name"] if preset else t("default_mode")

    def activate_preset(self, preset_id: str | None) -> None:
        if preset_id is not None and self._settings.get_preset(preset_id) is None:
            return
        if preset_id == self.active_preset_id:
            return
        self.refresh()
        self._settings.set_active_preset_id(preset_id)
        self.apply_profile()

    def toggle_preset(self, preset_id: str) -> None:
        self.activate_preset(None if preset_id == self.active_preset_id else preset_id)

    def apply_profile(self) -> None:
        self.isolation.sync()
        for key in self._sessions_by_key:
            volume, muted = self.isolation.effective_state(key)
            self._set_session_volume(key, volume)
            self._set_session_muted(key, muted)
        self._apply_master_profile()
        self.refresh(include_master=False)

    def _apply_master_profile(self) -> None:
        volume, muted = self._settings.get_profile_master_state()
        self._master_changed_at = perf_counter()
        self._backend.set_master_volume(volume)
        self._backend.set_master_mute(muted)
        self.apply_master_state(volume, muted)

    def observe_master_state(self, volume: float, muted: bool, timestamp: float) -> bool:
        if timestamp < self._master_changed_at:
            return False
        changed = self.apply_master_state(volume, muted)
        if changed:
            self._settings.set_profile_master_state(volume, muted)
        return changed

    def restore_master_profile(self) -> None:
        if self.active_preset_id is not None:
            self._apply_master_profile()

    def set_master_mute_listener(self, callback: Callable[[bool], None]) -> None:
        self._on_master_mute_changed = callback
        callback(self.is_master_muted())

    def is_master_muted(self) -> bool:
        return bool(self.entries and (self.entries[0].muted or self.entries[0].volume == 0))

    def _notify_master_mute(self) -> None:
        muted = self.is_master_muted()
        if muted != self._last_master_muted:
            self._last_master_muted = muted
            if self._on_master_mute_changed is not None:
                self._on_master_mute_changed(muted)

    def apply_master_state(self, volume: float, muted: bool) -> bool:
        entry = self.entries[0]
        state = (clamp_volume(volume), bool(muted))
        changed = not states_equal((entry.volume, entry.muted), state)
        entry.volume, entry.muted = state
        self._notify_master_mute()
        return changed

    def refresh_master(self) -> bool:
        state = self._backend.get_master_state()
        if state is None:
            return False
        self.observe_master_state(*state, perf_counter())
        return True

    def refresh_master_after_app_event(self) -> None:
        if self._settings.get_mini_widget_show_master():
            if self._master_refresh_scheduler is not None:
                self._master_refresh_scheduler()
            else:
                self.refresh_master()

    def set_master_refresh_scheduler(self, callback: Optional[Callable[[], None]]) -> None:
        self._master_refresh_scheduler = callback

    def refresh(self, *, include_master: bool = True) -> None:
        if self.isolation.sync():
            for key in self._sessions_by_key:
                volume, muted = self.isolation.effective_state(key)
                self._set_session_volume(key, volume)
                self._set_session_muted(key, muted)
        self._backend.refresh()

        master_entry = next((entry for entry in self.entries if entry.is_master), None) or MixerEntry(
            key=MASTER_KEY,
            display_name=MASTER_DISPLAY_NAME,
            volume=self._settings.get_master_volume(),
            muted=self._settings.get_master_muted(),
            is_master=True,
        )

        app_entries: list[MixerEntry] = []
        ignored_entries: list[MixerEntry] = []
        current_ids: set[str] = set()
        observed_states = {}
        self._sessions_by_id = {}
        self._sessions_by_key = {}
        for session in self._backend.enumerate_sessions():
            exe = session.key
            identities = set(session.member_ids)
            current_ids.update(identities)
            new_ids = identities - self._known_ids
            if new_ids:
                initial_volume, initial_muted = self.isolation.effective_state(exe)
                session.set_volume(initial_volume, new_ids)
                session.set_muted(initial_muted, new_ids)
                self._ready_at.update({identity: perf_counter() for identity in new_ids})
            self._sessions_by_key[exe] = session
            self._sessions_by_id.update({identity: session for identity in identities})

            try:
                volume, muted = session.volume, session.muted
            except Exception:
                continue
            state = (volume, muted)
            previous = self._observed_states.get(exe)
            if previous is not None and identities & self._known_ids and not states_equal(previous, state):
                blocked = self.isolation.is_blocked(exe)
                if blocked:
                    volume, muted = self.isolation.effective_state(exe)
                session.set_volume(volume)
                session.set_muted(muted)
                if blocked:
                    self._last_change[exe] = perf_counter()
                    self.isolation.notify_blocked(exe)
                else:
                    self._settings.set_profile_app_state(exe, volume, muted)
                state = (volume, muted)
            observed_states[exe] = state

            entry = MixerEntry(
                key=exe,
                display_name=session.display_name,
                volume=volume,
                muted=muted,
                icon_path=session.icon_path,
                pids=session.pids,
                volume_locked=self.isolation.is_blocked(exe),
            )

            if not self._settings.is_app_whitelisted(exe):
                continue

            if self._settings.is_app_ignored(exe):
                ignored_entries.append(entry)
            else:
                app_entries.append(entry)

        self._known_ids = current_ids
        self._observed_states = observed_states
        self._ready_at = {key: value for key, value in self._ready_at.items() if key in current_ids}
        self._last_change = {key: value for key, value in self._last_change.items()
                            if key in self._sessions_by_key}

        focused_key = None
        if self.entries and 0 <= self.focused_index < len(self.entries):
            focused_key = self.entries[self.focused_index].key

        app_entries.sort(key=lambda entry: self._settings.get_whitelist_app_order(entry.key))
        self.entries = [master_entry, *app_entries]
        self.ignored_entries = ignored_entries

        if include_master:
            self.refresh_master()

        if focused_key is not None:
            for index, entry in enumerate(self.entries):
                if entry.key == focused_key:
                    self.focused_index = index
                    break
            else:
                self.focused_index = 0
        else:
            self.focused_index = max(0, min(self.focused_index, len(self.entries) - 1))

        self._notify_master_mute()

    def apply_session_state(self, event) -> bool:
        session = self._sessions_by_id.get(event.session_id)
        if session is None:
            return False
        key = session.key
        if event.timestamp < max(self._ready_at.get(event.session_id, 0), self._last_change.get(key, 0)):
            if self.isolation.is_blocked(key):
                volume, muted = self.isolation.effective_state(key)
                self._set_session_volume(key, volume)
                self._set_session_muted(key, muted)
            return False
        self._last_change[key] = event.timestamp
        volume, muted = clamp_volume(event.volume), bool(event.muted)
        if self.isolation.is_blocked(key):
            effective = self.isolation.effective_state(key)
            attempted = (volume, muted) != effective
            self._set_session_volume(key, effective[0])
            self._set_session_muted(key, effective[1])
            if attempted:
                self.isolation.notify_blocked(key)
            return False
        session.set_volume(volume)
        session.set_muted(muted)
        if not states_equal(self._observed_states.get(key), (volume, muted)):
            self._settings.set_profile_app_state(key, volume, muted)
        self._observed_states[key] = (volume, muted)
        changed = False
        for entry in self.entries + self.ignored_entries:
            if entry.key == key:
                changed |= (entry.volume, entry.muted) != (volume, muted)
                entry.volume, entry.muted = volume, muted
        return changed

    @property
    def session_pids(self) -> set[int]:
        return {pid for session in self._sessions_by_key.values() for pid in session.pids}

    def sync_names(self) -> None:
        for entry in self.entries + self.ignored_entries:
            session = self._sessions_by_key.get(entry.key)
            if session is not None:
                entry.display_name = session.display_name

    @property
    def focused_entry(self) -> MixerEntry:
        return self.entries[self.focused_index]

    def move_focus(self, delta: int) -> None:
        new_index = self.focused_index + delta
        self.focused_index = max(0, min(len(self.entries) - 1, new_index))

    def set_volume(self, level: float, index: Optional[int] = None) -> float:
        index = self.focused_index if index is None else index
        entry = self.entries[index]
        if self.isolation.is_blocked(entry.key):
            return entry.volume
        level = clamp_volume(level)
        entry.volume = level

        if entry.is_master:
            self._master_changed_at = perf_counter()
            self._backend.set_master_volume(level)
            self._settings.set_profile_master_state(level, entry.muted)
            self._notify_master_mute()
        else:
            self._set_session_volume(entry.key, level)
            self._settings.set_profile_app_state(entry.key, level, entry.muted)
            self.refresh_master_after_app_event()

        return level

    def adjust_volume(self, delta: float, index: Optional[int] = None) -> float:
        index = self.focused_index if index is None else index
        entry = self.entries[index]
        return self.set_volume(entry.volume + delta, index)

    def toggle_mute(self, index: Optional[int] = None) -> bool:
        index = self.focused_index if index is None else index
        entry = self.entries[index]
        if self.isolation.is_blocked(entry.key):
            return entry.muted
        muted = not entry.muted
        entry.muted = muted

        if entry.is_master:
            self._master_changed_at = perf_counter()
            self._backend.set_master_mute(muted)
            self._settings.set_profile_master_state(entry.volume, muted)
        else:
            self._set_session_muted(entry.key, muted)
            self._settings.set_profile_app_state(entry.key, entry.volume, muted)
            self.refresh_master_after_app_event()

        self._notify_master_mute()
        return muted

    def focus_key(self, key: str) -> bool:
        for index, entry in enumerate(self.entries):
            if entry.key == key:
                self.focused_index = index
                return True
        return False

    def adjust_volume_by_key(self, key: str, delta: float) -> float:
        for index, entry in enumerate(self.entries):
            if entry.key == key:
                self.focused_index = index
                return self.adjust_volume(delta, index)
        return 0.0

    def toggle_mute_by_key(self, key: str) -> bool:
        for index, entry in enumerate(self.entries):
            if entry.key == key:
                self.focused_index = index
                return self.toggle_mute(index)
        return False

    def ignore_app(self, key: str) -> None:
        self._settings.add_ignored_app(key)
        self.refresh()

    def unignore_app(self, key: str) -> None:
        self._settings.remove_ignored_app(key)
        self.refresh()

    def set_ignored_volume(self, key: str, level: float) -> float:
        for entry in self.ignored_entries:
            if entry.key == key:
                if self.isolation.is_blocked(key):
                    return entry.volume
                level = clamp_volume(level)
                entry.volume = level
                self._set_session_volume(key, level)
                self._settings.set_profile_app_state(key, level, entry.muted)
                self.refresh_master_after_app_event()
                return level
        return level

    def adjust_ignored_volume(self, key: str, delta: float) -> float:
        for entry in self.ignored_entries:
            if entry.key == key:
                return self.set_ignored_volume(key, entry.volume + delta)
        return 0.0

    def toggle_ignored_mute(self, key: str) -> bool:
        for entry in self.ignored_entries:
            if entry.key == key:
                if self.isolation.is_blocked(key):
                    return entry.muted
                muted = not entry.muted
                entry.muted = muted
                self._set_session_muted(key, muted)
                self._settings.set_profile_app_state(key, entry.volume, muted)
                self.refresh_master_after_app_event()
                return muted
        return False

    def _set_session_volume(self, key: str, level: float) -> None:
        self._last_change[key] = perf_counter()
        if key in self._observed_states:
            self._observed_states[key] = (level, self._observed_states[key][1])
        session = self._sessions_by_key.get(key)
        if session is not None:
            session.set_volume(level)

    def _set_session_muted(self, key: str, muted: bool) -> None:
        self._last_change[key] = perf_counter()
        if key in self._observed_states:
            self._observed_states[key] = (self._observed_states[key][0], muted)
        session = self._sessions_by_key.get(key)
        if session is not None:
            session.set_muted(muted)
