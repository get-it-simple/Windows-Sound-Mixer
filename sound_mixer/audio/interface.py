from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSession(Protocol):
    pid: int
    pids: tuple[int, ...]
    key: str
    process_name: str
    display_name: str
    icon_path: str
    volume: float
    muted: bool

    def set_volume(self, level: float) -> None: ...

    def set_muted(self, muted: bool) -> None: ...


@runtime_checkable
class AudioBackend(Protocol):
    def get_master_state(self) -> tuple[float, bool] | None: ...

    def invalidate_master_endpoint(self) -> None: ...

    def enumerate_sessions(self) -> list[AudioSession]: ...

    def get_master_volume(self) -> float: ...

    def set_master_volume(self, level: float) -> None: ...

    def get_master_mute(self) -> bool: ...

    def set_master_mute(self, muted: bool) -> None: ...

    def refresh(self) -> None: ...
