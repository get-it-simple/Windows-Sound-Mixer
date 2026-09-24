import os
import time
from math import isclose
from collections import OrderedDict

import psutil
from comtypes import GUID
from pycaw.pycaw import AudioUtilities

from sound_mixer.app_key import normalize_app_key
from sound_mixer.audio.events import VOLUME_EVENT_CONTEXT
from sound_mixer.audio.win_names import get_exe_friendly_name, get_window_titles_by_pid
from sound_mixer.volume import clamp_volume

TITLE_RETRY_INITIAL_S = 2.0
TITLE_RETRY_MAX_S = 30.0
TITLE_CONFIRM_ATTEMPTS = 4
ENDPOINT_TTL_S = 5.0
DYNAMIC_TITLE_SEPARATORS = (" - ", " | ", " — ", " – ")
RELATIVE_DEPTH = 4
RELATIVE_CANDIDATE_LIMIT = 64
NAME_CACHE_LIMIT = 256
_EVENT_CONTEXT = GUID(VOLUME_EVENT_CONTEXT)

FINAL = "final"
PROVISIONAL = "provisional"
PENDING = "pending"


def _exe_stem(exe_path: str) -> str:
    return os.path.splitext(os.path.basename(exe_path))[0]


def _has_dynamic_separator(title: str) -> bool:
    return any(separator in title for separator in DYNAMIC_TITLE_SEPARATORS)


def _ends_with_name(title: str, name: str) -> bool:
    lowered = title.casefold()
    suffix = name.casefold()
    return any(lowered.endswith(separator + suffix) for separator in DYNAMIC_TITLE_SEPARATORS)


def _choose_display_name(description: str, exe_stem: str, title: str) -> tuple[str, str]:
    fallback = description or exe_stem
    if not title:
        return fallback, PENDING
    lowered = title.casefold()
    if description and lowered == description.casefold():
        return description, PENDING
    if exe_stem and lowered == exe_stem.casefold():
        return description or title, PENDING
    if description and _ends_with_name(title, description):
        return description, FINAL
    if description and description.casefold() in lowered and len(title) > len(description):
        return title, PROVISIONAL
    if not _has_dynamic_separator(title):
        return title, PROVISIONAL
    if description and exe_stem and description.casefold() == exe_stem.casefold():
        return description, FINAL
    return title, PROVISIONAL


def _runs_from_exe_path(pid: int, exe_path: str) -> bool:
    try:
        return os.path.normcase(psutil.Process(pid).exe()) == os.path.normcase(exe_path)
    except psutil.Error:
        return False


def _pids_with_exe_path(exe_path: str) -> list[int]:
    if not exe_path:
        return []
    process_name = os.path.basename(os.path.normcase(exe_path))
    pids = []
    try:
        for process in psutil.process_iter(["pid", "name"]):
            name = os.path.normcase(process.info.get("name") or "")
            if name == process_name and _runs_from_exe_path(process.info["pid"], exe_path):
                pids.append(process.info["pid"])
    except psutil.Error:
        return []
    return pids


def _parent_map() -> dict[int, int]:
    parents: dict[int, int] = {}
    try:
        for process in psutil.process_iter(["pid", "ppid"]):
            parents[process.info["pid"]] = process.info.get("ppid") or 0
    except psutil.Error:
        return {}
    return parents


def _ancestors(pid: int, parents: dict[int, int]) -> set[int]:
    chain = {pid}
    current = pid
    for _ in range(RELATIVE_DEPTH):
        parent = parents.get(current)
        if not parent or parent in chain:
            break
        chain.add(parent)
        current = parent
    return chain


def _exe_folder(pid: int) -> str:
    try:
        return os.path.normcase(os.path.dirname(psutil.Process(pid).exe()))
    except psutil.Error:
        return ""


def _pids_in_same_folder(exe_path: str, pids: list[int], candidates: list[int]) -> list[int]:
    folder = os.path.normcase(os.path.dirname(exe_path))
    if not folder or not candidates:
        return []
    parents = _parent_map()
    if not parents:
        return []
    group = set(pids)
    tree: set[int] = set()
    for pid in group:
        tree |= _ancestors(pid, parents)
    related = []
    for pid in candidates[:RELATIVE_CANDIDATE_LIMIT]:
        if pid in group:
            continue
        if not _ancestors(pid, parents) & tree:
            continue
        if _exe_folder(pid) == folder:
            related.append(pid)
    return related


def _window_title_for_group(exe_path: str, pids: list[int], titles: dict[int, str]) -> str:
    if not titles:
        return ""
    own = [titles[pid] for pid in pids if pid in titles]
    if not own:
        own = [titles[pid] for pid in _pids_with_exe_path(exe_path) if pid in titles]
    if not own:
        related = _pids_in_same_folder(exe_path, pids, list(titles))
        own = [titles[pid] for pid in related if pid in titles]
    return max(own, key=len) if own else ""


class _EndpointVolumeCache:
    def __init__(self, acquire, now=time.monotonic, ttl=ENDPOINT_TTL_S) -> None:
        self._acquire = acquire
        self._now = now
        self._ttl = ttl
        self._endpoint = None
        self._acquired_at = 0.0

    def call(self, op):
        endpoint = self._get_endpoint()
        try:
            return op(endpoint)
        except Exception:
            self.invalidate()
            return op(self._get_endpoint())

    def invalidate(self) -> None:
        self._endpoint = None

    def _get_endpoint(self):
        if self._endpoint is None or self._now() - self._acquired_at >= self._ttl:
            self._endpoint = self._acquire()
            self._acquired_at = self._now()
        return self._endpoint


class _ProcessNameCache:
    def __init__(self, now=time.monotonic) -> None:
        self._now = now
        self._exe_info_checked: set[str] = set()
        self._descriptions: dict[str, str] = {}
        self._names: dict[str, str] = {}
        self._provisional: dict[str, str] = {}
        self._attempts: dict[str, int] = {}
        self._final: set[str] = set()
        self._dynamic: set[str] = set()
        self._next_retry: dict[str, float] = {}
        self._retry_interval: dict[str, float] = {}
        self._recent = OrderedDict()

    def _touch(self, key: str) -> None:
        self._recent[key] = None
        self._recent.move_to_end(key)
        while len(self._recent) > NAME_CACHE_LIMIT:
            oldest, _ = self._recent.popitem(last=False)
            for values in (self._exe_info_checked, self._final, self._dynamic):
                values.discard(oldest)
            for values in (self._descriptions, self._names, self._provisional, self._attempts,
                           self._next_retry, self._retry_interval):
                values.pop(oldest, None)

    def wants_titles(self, key: str) -> bool:
        if key in self._final:
            return False
        return key not in self._next_retry or self._now() >= self._next_retry[key]

    def resolve(self, key: str, exe_path: str, pids: list[int], titles=None) -> None:
        self._touch(key)
        if key in self._final:
            return
        if key not in self._exe_info_checked:
            self._exe_info_checked.add(key)
            description = get_exe_friendly_name(exe_path)
            if description:
                self._descriptions[key] = description
                self._names[key] = description
        if key in self._next_retry and self._now() < self._next_retry[key]:
            return
        if titles is None:
            titles = get_window_titles_by_pid()
        description = self._descriptions.get(key, "")
        stem = _exe_stem(exe_path)
        title = _window_title_for_group(exe_path, pids, titles)
        name, state = _choose_display_name(description, stem, title)
        if key in self._dynamic:
            self._resolve_dynamic(key, name, state)
            return
        if state == PENDING:
            if name:
                self._names.setdefault(key, name)
            self._schedule_retry(key)
            return
        if state == FINAL:
            self._commit(key, name)
            return
        if self._provisional.get(key) == name:
            self._commit(key, name)
            return
        attempts = self._attempts.get(key, 0) + 1
        self._provisional[key] = name
        self._names[key] = name
        if attempts >= TITLE_CONFIRM_ATTEMPTS:
            self._enter_dynamic(key, description or stem or name)
            return
        self._attempts[key] = attempts
        self._schedule_retry(key)

    def get(self, key: str) -> str:
        if key in self._recent:
            self._recent.move_to_end(key)
        return self._names.get(key, "")

    def next_retry(self, keys) -> float | None:
        times = [self._next_retry.get(key, self._now()) for key in keys if key not in self._final]
        return max(0.0, min(times) - self._now()) if times else None

    def _enter_dynamic(self, key: str, name: str) -> None:
        self._names[key] = name
        self._dynamic.add(key)
        self._provisional[key] = ""
        self._retry_interval[key] = TITLE_RETRY_MAX_S
        self._schedule_retry(key)

    def _resolve_dynamic(self, key: str, name: str, state: str) -> None:
        stable = state == PROVISIONAL and not _has_dynamic_separator(name)
        if stable and self._provisional.get(key) == name:
            self._commit(key, name)
            return
        self._provisional[key] = name if stable else ""
        self._schedule_retry(key)

    def _commit(self, key: str, name: str) -> None:
        self._names[key] = name
        self._final.add(key)

    def _schedule_retry(self, key: str) -> None:
        interval = min(self._retry_interval.get(key, TITLE_RETRY_INITIAL_S), TITLE_RETRY_MAX_S)
        self._next_retry[key] = self._now() + interval
        self._retry_interval[key] = interval * 2


class PycawAudioSession:
    def __init__(
        self,
        key: str,
        process_name: str,
        display_name: str,
        controls: list,
        icon_path: str = "",
    ) -> None:
        self.key = key
        self.process_name = process_name
        self.display_name = display_name
        self.icon_path = icon_path
        self.pid = controls[0].ProcessId
        self.pids = tuple(dict.fromkeys(control.ProcessId for control in controls))
        self._controls = controls
        self.member_ids = tuple(control.InstanceIdentifier for control in controls)

    @property
    def volume(self) -> float:
        return self._controls[0].SimpleAudioVolume.GetMasterVolume()

    @property
    def muted(self) -> bool:
        return bool(self._controls[0].SimpleAudioVolume.GetMute())

    def set_volume(self, level: float, member_ids: set[str] | None = None) -> None:
        level = clamp_volume(level)
        for identity, control in zip(self.member_ids, self._controls):
            if member_ids is not None and identity not in member_ids:
                continue
            try:
                if not isclose(control.SimpleAudioVolume.GetMasterVolume(), level, abs_tol=1e-6):
                    control.SimpleAudioVolume.SetMasterVolume(level, _EVENT_CONTEXT)
            except Exception:
                pass

    def set_muted(self, muted: bool, member_ids: set[str] | None = None) -> None:
        for identity, control in zip(self.member_ids, self._controls):
            if member_ids is not None and identity not in member_ids:
                continue
            try:
                if bool(control.SimpleAudioVolume.GetMute()) != bool(muted):
                    control.SimpleAudioVolume.SetMute(bool(muted), _EVENT_CONTEXT)
            except Exception:
                pass


class PycawAudioBackend:
    def __init__(self) -> None:
        self._sessions: list[PycawAudioSession] = []
        self._exe_paths: dict[int, str] = {}
        self._pid_sessions: dict[int, set[str]] = {}
        self._excluded_ids: set[str] = set()
        self._names_visible = True
        self._name_cache = _ProcessNameCache()
        self._endpoint = _EndpointVolumeCache(lambda: AudioUtilities.GetSpeakers().EndpointVolume)

    def refresh(self) -> None:
        try:
            sessions = AudioUtilities.GetAllSessions()
        except Exception:
            self._sessions = []
            self._exe_paths.clear()
            self._pid_sessions.clear()
            return
        grouped: dict[str, list] = {}
        pids: dict[str, list[int]] = {}
        process_names: dict[str, str] = {}
        exe_paths: dict[str, str] = {}
        live_pids: set[int] = set()
        observed_ids: set[str] = set()
        pid_sessions: dict[int, set[str]] = {}
        for session in sessions:
            try:
                if session.State == 2:
                    continue
                process = session.Process
                if process is None:
                    continue
                identity = session.InstanceIdentifier
                observed_ids.add(identity)
                if identity in self._excluded_ids:
                    continue
                process_name = process.name()
            except Exception:
                continue
            live_pids.add(process.pid)
            pid_sessions.setdefault(process.pid, set()).add(identity)
            if identity not in self._pid_sessions.get(process.pid, set()):
                self._exe_paths.pop(process.pid, None)
            exe_path = self._exe_path(process)
            key = normalize_app_key(exe_path) if exe_path else process_name.lower()
            grouped.setdefault(key, []).append(session)
            pids.setdefault(key, []).append(process.pid)
            process_names.setdefault(key, process_name)
            exe_paths.setdefault(key, exe_path)

        self._exe_paths = {pid: path for pid, path in self._exe_paths.items() if pid in live_pids}
        self._pid_sessions = pid_sessions
        self._excluded_ids.intersection_update(observed_ids)

        titles = self._window_titles(pids)
        for key, key_pids in pids.items():
            self._name_cache.resolve(key, exe_paths[key], key_pids, titles)

        self._sessions = [
            PycawAudioSession(
                key,
                process_names[key],
                self._name_cache.get(key) or controls[0].DisplayName or process_names[key],
                controls,
                exe_paths[key],
            )
            for key, controls in grouped.items()
        ]

    def _window_titles(self, pids: dict[str, list[int]]) -> dict[int, str]:
        if not self._names_visible:
            return {}
        if not any(self._name_cache.wants_titles(key) for key in pids):
            return {}
        return get_window_titles_by_pid()

    def _exe_path(self, process) -> str:
        if process.pid not in self._exe_paths:
            try:
                self._exe_paths[process.pid] = process.exe()
            except psutil.Error:
                self._exe_paths[process.pid] = ""
        return self._exe_paths[process.pid]

    def enumerate_sessions(self) -> list[PycawAudioSession]:
        return list(self._sessions)

    def exclude_session(self, identity: str) -> None:
        self._excluded_ids.add(identity)

    def reset_sessions(self) -> None:
        self._sessions.clear()
        self._exe_paths.clear()
        self._pid_sessions.clear()
        self._excluded_ids.clear()

    def set_names_visible(self, visible: bool) -> None:
        self._names_visible = visible

    def refresh_names(self) -> bool:
        pids = {session.key: list(session.pids) for session in self._sessions}
        titles = self._window_titles(pids)
        changed = False
        for session in self._sessions:
            self._name_cache.resolve(session.key, session.icon_path, list(session.pids), titles)
            name = self._name_cache.get(session.key) or session.display_name
            changed |= name != session.display_name
            session.display_name = name
        return changed

    def name_retry_delay(self) -> float | None:
        return self._name_cache.next_retry(session.key for session in self._sessions)

    def get_master_volume(self) -> float:
        try:
            return self._endpoint.call(lambda ep: ep.GetMasterVolumeLevelScalar())
        except Exception:
            return 1.0

    def get_master_state(self) -> tuple[float, bool] | None:
        try:
            return self._endpoint.call(lambda ep: (ep.GetMasterVolumeLevelScalar(), bool(ep.GetMute())))
        except Exception:
            return None

    def invalidate_master_endpoint(self) -> None:
        self._endpoint.invalidate()

    def set_master_volume(self, level: float) -> None:
        try:
            self._endpoint.call(lambda ep: ep.SetMasterVolumeLevelScalar(clamp_volume(level), None))
        except Exception:
            pass

    def get_master_mute(self) -> bool:
        try:
            return bool(self._endpoint.call(lambda ep: ep.GetMute()))
        except Exception:
            return False

    def set_master_mute(self, muted: bool) -> None:
        try:
            self._endpoint.call(lambda ep: ep.SetMute(bool(muted), None))
        except Exception:
            pass
