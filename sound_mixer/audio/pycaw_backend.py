import psutil
from pycaw.pycaw import AudioUtilities

from sound_mixer.audio.win_names import get_exe_friendly_name, get_process_window_title
from sound_mixer.volume import clamp_volume


class _ProcessNameCache:
    def __init__(self) -> None:
        self._exe_info_checked: set[str] = set()
        self._names: dict[str, str] = {}

    def resolve(self, key: str, exe_path: str, pid: int) -> None:
        if key in self._names:
            return
        if key not in self._exe_info_checked:
            self._exe_info_checked.add(key)
            name = get_exe_friendly_name(exe_path)
            if name:
                self._names[key] = name
                return
        name = get_process_window_title(pid)
        if name:
            self._names[key] = name

    def get(self, key: str) -> str:
        return self._names.get(key, "")


class PycawAudioSession:
    def __init__(self, process_name: str, display_name: str, controls: list, icon_path: str = "") -> None:
        self.process_name = process_name
        self.display_name = display_name
        self.icon_path = icon_path
        self.pid = controls[0].ProcessId
        self._controls = controls

    @property
    def volume(self) -> float:
        return self._controls[0].SimpleAudioVolume.GetMasterVolume()

    @property
    def muted(self) -> bool:
        return bool(self._controls[0].SimpleAudioVolume.GetMute())

    def set_volume(self, level: float) -> None:
        level = clamp_volume(level)
        for control in self._controls:
            try:
                control.SimpleAudioVolume.SetMasterVolume(level, None)
            except Exception:
                pass

    def set_muted(self, muted: bool) -> None:
        for control in self._controls:
            try:
                control.SimpleAudioVolume.SetMute(bool(muted), None)
            except Exception:
                pass


class PycawAudioBackend:
    def __init__(self) -> None:
        self._sessions: list[PycawAudioSession] = []
        self._icon_paths: dict[str, str] = {}
        self._name_cache = _ProcessNameCache()
        self.refresh()

    def refresh(self) -> None:
        try:
            sessions = AudioUtilities.GetAllSessions()
        except Exception:
            return
        grouped: dict[str, list] = {}
        for session in sessions:
            process = session.Process
            if process is None:
                continue
            try:
                process_name = process.name()
            except psutil.Error:
                continue
            key = process_name.lower()
            grouped.setdefault(key, []).append(session)

            if key not in self._icon_paths:
                try:
                    self._icon_paths[key] = process.exe()
                except psutil.Error:
                    self._icon_paths[key] = ""

            self._name_cache.resolve(key, self._icon_paths[key], process.pid)

        self._sessions = [
            PycawAudioSession(
                process_name,
                self._name_cache.get(process_name) or controls[0].DisplayName or process_name,
                controls,
                self._icon_paths.get(process_name, ""),
            )
            for process_name, controls in grouped.items()
        ]

    def enumerate_sessions(self) -> list[PycawAudioSession]:
        return list(self._sessions)

    def get_master_volume(self) -> float:
        try:
            return self._endpoint_volume().GetMasterVolumeLevelScalar()
        except Exception:
            return 1.0

    def set_master_volume(self, level: float) -> None:
        try:
            self._endpoint_volume().SetMasterVolumeLevelScalar(clamp_volume(level), None)
        except Exception:
            pass

    def get_master_mute(self) -> bool:
        try:
            return bool(self._endpoint_volume().GetMute())
        except Exception:
            return False

    def set_master_mute(self, muted: bool) -> None:
        try:
            self._endpoint_volume().SetMute(bool(muted), None)
        except Exception:
            pass

    def _endpoint_volume(self):
        return AudioUtilities.GetSpeakers().EndpointVolume
