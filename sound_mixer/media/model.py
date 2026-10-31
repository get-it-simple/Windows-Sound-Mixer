from dataclasses import dataclass, field, replace
import threading

from PySide6.QtGui import QImage

from sound_mixer.app_key import legacy_app_key, normalize_app_key


@dataclass(frozen=True)
class MediaOwner:
    key: str
    pids: tuple[int, ...]
    icon_path: str = ""


@dataclass(frozen=True)
class MediaItem:
    session_id: str
    source: str
    title: str = ""
    artwork_key: str = ""
    image: QImage = field(default_factory=QImage, compare=False, repr=False)
    owner_key: str | None = None
    playback_state: str = "playing"
    can_previous: bool = False
    can_next: bool = False
    can_play: bool = False
    can_pause: bool = False
    pending_action: str = ""
    generation: int = 0


class PausedSessions:
    def __init__(self):
        self._sessions = []
        self._epoch = 0
        self._manager = None
        self._lock = threading.Lock()

    @property
    def epoch(self):
        with self._lock:
            return self._epoch

    def contains(self, native):
        with self._lock:
            return native in self._sessions

    def get_manager(self):
        with self._lock:
            return self._manager

    def cache_manager(self, manager, epoch):
        with self._lock:
            if epoch == self._epoch:
                self._manager = manager

    def remember(self, native, epoch):
        with self._lock:
            if epoch == self._epoch and native not in self._sessions:
                self._sessions.append(native)

    def forget(self, native):
        with self._lock:
            self._sessions = [session for session in self._sessions if session != native]

    def retain(self, sessions):
        with self._lock:
            self._sessions = [session for session in self._sessions if session in sessions]

    def clear(self):
        with self._lock:
            self._epoch += 1
            self._sessions.clear()
            self._manager = None


def match_owner(source: str, owners: tuple[MediaOwner, ...], identities: dict[str, set[str]]) -> str | None:
    source = source.casefold()
    exact = {owner.key for owner in owners if source in identities.get(owner.key, set())}
    if len(exact) == 1:
        return exact.pop()
    if exact:
        return None
    normalized = normalize_app_key(source)
    paths = {owner.key for owner in owners if normalized == normalize_app_key(owner.key)}
    if len(paths) == 1:
        return paths.pop()
    if source.endswith(".exe") and "/" not in source and "\\" not in source:
        names = {owner.key for owner in owners if source == legacy_app_key(owner.key)}
        if len(names) == 1:
            return names.pop()
    return None


def attach_owners(items, owners, identities):
    return tuple(replace(item, owner_key=match_owner(item.source, owners, identities)) for item in items)
