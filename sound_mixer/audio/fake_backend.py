from dataclasses import dataclass

from sound_mixer.volume import clamp_volume


@dataclass
class FakeAudioSession:
    pid: int
    process_name: str
    display_name: str
    volume: float = 1.0
    muted: bool = False

    def set_volume(self, level: float) -> None:
        self.volume = clamp_volume(level)

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)


class FakeAudioBackend:
    def __init__(self, sessions=None, master_volume: float = 1.0, master_muted: bool = False):
        self._sessions: list[FakeAudioSession] = list(sessions) if sessions else []
        self._master_volume = clamp_volume(master_volume)
        self._master_muted = master_muted

    def enumerate_sessions(self) -> list[FakeAudioSession]:
        return list(self._sessions)

    def add_session(self, session: FakeAudioSession) -> None:
        self._sessions.append(session)

    def remove_session(self, process_name: str) -> None:
        process_name = process_name.lower()
        self._sessions = [s for s in self._sessions if s.process_name.lower() != process_name]

    def get_master_volume(self) -> float:
        return self._master_volume

    def set_master_volume(self, level: float) -> None:
        self._master_volume = clamp_volume(level)

    def get_master_mute(self) -> bool:
        return self._master_muted

    def set_master_mute(self, muted: bool) -> None:
        self._master_muted = bool(muted)

    def refresh(self) -> None:
        pass
