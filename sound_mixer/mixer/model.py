from dataclasses import dataclass
from typing import Optional

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


class MixerModel:
    def __init__(self, backend: AudioBackend, settings: SettingsStore):
        self._backend = backend
        self._settings = settings
        self._seen_exes: set[str] = set()
        self.entries: list[MixerEntry] = []
        self.focused_index = 0
        self.refresh()

    def refresh(self) -> None:
        self._backend.refresh()

        master_entry = MixerEntry(
            key=MASTER_KEY,
            display_name=MASTER_DISPLAY_NAME,
            volume=self._backend.get_master_volume(),
            muted=self._backend.get_master_mute(),
            is_master=True,
        )

        app_entries: list[MixerEntry] = []
        for session in self._backend.enumerate_sessions():
            exe = session.process_name.lower()
            if exe not in self._seen_exes:
                self._seen_exes.add(exe)
                session.set_volume(self._settings.get_app_volume(exe))
                session.set_muted(self._settings.get_app_muted(exe))

            app_entries.append(
                MixerEntry(
                    key=exe,
                    display_name=session.display_name,
                    volume=session.volume,
                    muted=session.muted,
                )
            )

        focused_key = None
        if self.entries and 0 <= self.focused_index < len(self.entries):
            focused_key = self.entries[self.focused_index].key

        self.entries = [master_entry, *app_entries]

        if focused_key is not None:
            for index, entry in enumerate(self.entries):
                if entry.key == focused_key:
                    self.focused_index = index
                    break
            else:
                self.focused_index = 0
        else:
            self.focused_index = max(0, min(self.focused_index, len(self.entries) - 1))

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
        else:
            self._set_session_volume(entry.key, level)
            self._settings.set_app_volume(entry.key, level)

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

        return muted

    def _set_session_volume(self, exe: str, level: float) -> None:
        for session in self._backend.enumerate_sessions():
            if session.process_name.lower() == exe:
                session.set_volume(level)

    def _set_session_muted(self, exe: str, muted: bool) -> None:
        for session in self._backend.enumerate_sessions():
            if session.process_name.lower() == exe:
                session.set_muted(muted)
