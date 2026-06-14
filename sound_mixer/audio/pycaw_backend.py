import psutil
from pycaw.pycaw import AudioUtilities

from sound_mixer.volume import clamp_volume


class PycawAudioSession:
    def __init__(self, process_name: str, display_name: str, controls: list) -> None:
        self.process_name = process_name
        self.display_name = display_name
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
        self.refresh()

    def refresh(self) -> None:
        grouped: dict[str, list] = {}
        for session in AudioUtilities.GetAllSessions():
            process = session.Process
            if process is None:
                continue
            try:
                process_name = process.name()
            except psutil.Error:
                continue
            grouped.setdefault(process_name.lower(), []).append(session)

        self._sessions = [
            PycawAudioSession(process_name, controls[0].DisplayName or process_name, controls)
            for process_name, controls in grouped.items()
        ]

    def enumerate_sessions(self) -> list[PycawAudioSession]:
        return list(self._sessions)

    def get_master_volume(self) -> float:
        return self._endpoint_volume().GetMasterVolumeLevelScalar()

    def set_master_volume(self, level: float) -> None:
        self._endpoint_volume().SetMasterVolumeLevelScalar(clamp_volume(level), None)

    def get_master_mute(self) -> bool:
        return bool(self._endpoint_volume().GetMute())

    def set_master_mute(self, muted: bool) -> None:
        self._endpoint_volume().SetMute(bool(muted), None)

    def _endpoint_volume(self):
        return AudioUtilities.GetSpeakers().EndpointVolume
