from dataclasses import dataclass
from typing import Callable, Optional
from time import perf_counter

from sound_mixer.audio.interface import AudioBackend
from sound_mixer.settings.store import SettingsStore
from sound_mixer.volume import clamp_volume

MASTER_KEY = "master"
MASTER_DISPLAY_NAME = "System"


@dataclass
class MixerEntry:
    key: str
    display_name: str
    volume: float
    muted: bool
    is_master: bool = False
    icon_path: str = ""
    pids: tuple[int, ...] = ()


class MixerModel:
    def __init__(self, backend: AudioBackend, settings: SettingsStore):
        self._backend = backend
        self._settings = settings
        self._known_ids: set[str] = set()
        self._sessions_by_id = {}
        self._sessions_by_key = {}
        self._ready_at = {}
        self._last_change = {}
        self._observed_states = {}
        self.entries: list[MixerEntry] = []
        self.ignored_entries: list[MixerEntry] = []
        self.focused_index = 0
        self._on_master_mute_changed: Optional[Callable[[bool], None]] = None
        self._last_master_muted: Optional[bool] = None
        self._master_refresh_scheduler: Optional[Callable[[], None]] = None
        self.refresh()

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
        changed = (entry.volume, entry.muted) != state
        entry.volume, entry.muted = state
        self._notify_master_mute()
        return changed

    def refresh_master(self) -> bool:
        state = self._backend.get_master_state()
        if state is None:
            return False
        self.apply_master_state(*state)
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
                session.set_volume(self._settings.get_app_volume(exe), new_ids)
                session.set_muted(self._settings.get_app_muted(exe), new_ids)
                self._ready_at.update({identity: perf_counter() for identity in new_ids})
            self._sessions_by_key[exe] = session
            self._sessions_by_id.update({identity: session for identity in identities})

            try:
                volume, muted = session.volume, session.muted
            except Exception:
                continue
            state = (volume, muted)
            previous = self._observed_states.get(exe)
            if previous is not None and identities & self._known_ids and previous != state:
                session.set_volume(volume)
                session.set_muted(muted)
                self._settings.set_app_volume(exe, volume)
                self._settings.set_app_muted(exe, muted)
            observed_states[exe] = state

            entry = MixerEntry(
                key=exe,
                display_name=session.display_name,
                volume=volume,
                muted=muted,
                icon_path=session.icon_path,
                pids=session.pids,
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
            return False
        self._last_change[key] = event.timestamp
        volume, muted = clamp_volume(event.volume), bool(event.muted)
        session.set_volume(volume)
        session.set_muted(muted)
        self._settings.set_app_volume(key, volume)
        self._settings.set_app_muted(key, muted)
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
        level = clamp_volume(level)
        entry.volume = level

        if entry.is_master:
            self._backend.set_master_volume(level)
            self._settings.set_master_volume(level)
            self._notify_master_mute()
        else:
            self._set_session_volume(entry.key, level)
            self._settings.set_app_volume(entry.key, level)
            self.refresh_master_after_app_event()

        return level

    def adjust_volume(self, delta: float, index: Optional[int] = None) -> float:
        index = self.focused_index if index is None else index
        entry = self.entries[index]
        return self.set_volume(entry.volume + delta, index)

    def toggle_mute(self, index: Optional[int] = None) -> bool:
        index = self.focused_index if index is None else index
        entry = self.entries[index]
        muted = not entry.muted
        entry.muted = muted

        if entry.is_master:
            self._backend.set_master_mute(muted)
            self._settings.set_master_muted(muted)
        else:
            self._set_session_muted(entry.key, muted)
            self._settings.set_app_muted(entry.key, muted)
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
                level = clamp_volume(level)
                entry.volume = level
                self._set_session_volume(key, level)
                self._settings.set_app_volume(key, level)
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
                muted = not entry.muted
                entry.muted = muted
                self._set_session_muted(key, muted)
                self._settings.set_app_muted(key, muted)
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
