from dataclasses import dataclass
from time import perf_counter

VOLUME_EVENT_CONTEXT = "{7DD49A98-76AD-4438-B65D-0BBC89F17866}"


@dataclass(frozen=True)
class SessionEvent:
    generation: int
    kind: str
    session_id: str = ""
    volume: float = 0.0
    muted: bool = False
    timestamp: float = 0.0

    @classmethod
    def volume_changed(cls, generation, session_id, volume, muted):
        return cls(generation, "volume", session_id, float(volume), bool(muted), perf_counter())
