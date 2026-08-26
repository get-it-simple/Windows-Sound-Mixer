from unittest.mock import patch

import psutil

from sound_mixer.audio.pycaw_backend import PycawAudioBackend

_PATCH_SESSIONS = "sound_mixer.audio.pycaw_backend.AudioUtilities.GetAllSessions"
_PATCH_SPEAKERS = "sound_mixer.audio.pycaw_backend.AudioUtilities.GetSpeakers"
_PATCH_EXE = "sound_mixer.audio.pycaw_backend.get_exe_friendly_name"
_PATCH_TITLES = "sound_mixer.audio.pycaw_backend.get_window_titles_by_pid"

_GAME_PATH = "D:/Games/Voidrunner/voidrunner.exe"
_GAME_KEY = "d:/games/voidrunner/voidrunner.exe"
_GAME_TITLE = "Voidrunner: Echoes"


class StubEndpointVolume:
    def __init__(self, fail_times: int = 0) -> None:
        self._fail_times = fail_times

    def _maybe_fail(self):
        if self._fail_times > 0:
            self._fail_times -= 1
            raise OSError("device gone")

    def GetMasterVolumeLevelScalar(self):
        self._maybe_fail()
        return 0.7

    def GetMute(self):
        self._maybe_fail()
        return False


class StubSpeakers:
    def __init__(self, endpoint) -> None:
        self.EndpointVolume = endpoint


def test_backend_init_does_not_enumerate_sessions():
    with patch(_PATCH_SESSIONS, return_value=[]) as mock_sessions:
        backend = PycawAudioBackend()

        assert mock_sessions.call_count == 0

        backend.refresh()

        assert mock_sessions.call_count == 1


def test_backend_starts_with_no_sessions():
    with patch(_PATCH_SESSIONS, return_value=[]):
        backend = PycawAudioBackend()

    assert backend.enumerate_sessions() == []


def test_master_volume_reads_do_not_reacquire_speakers_within_ttl():
    with patch(_PATCH_SPEAKERS, return_value=StubSpeakers(StubEndpointVolume())) as mock_speakers:
        backend = PycawAudioBackend()

        for _ in range(3):
            assert backend.get_master_volume() == 0.7
            assert backend.get_master_mute() is False

    assert mock_speakers.call_count == 1


def test_master_volume_recovers_after_endpoint_error():
    with patch(_PATCH_SPEAKERS, return_value=StubSpeakers(StubEndpointVolume(fail_times=1))) as mock_speakers:
        backend = PycawAudioBackend()

        assert backend.get_master_volume() == 0.7

    assert mock_speakers.call_count == 2


def _raise_access_denied():
    raise psutil.AccessDenied()


class StubProcess:
    def __init__(self, pid: int, name: str, exe: str) -> None:
        self.pid = pid
        self._name = name
        self._exe = exe
        self.exe_calls = 0
        self.forbidden_calls: list[str] = []

    def name(self):
        return self._name

    def exe(self):
        self.exe_calls += 1
        return self._exe

    def cmdline(self):
        self.forbidden_calls.append("cmdline")
        return []

    def environ(self):
        self.forbidden_calls.append("environ")
        return {}

    def memory_maps(self):
        self.forbidden_calls.append("memory_maps")
        return []

    def open_files(self):
        self.forbidden_calls.append("open_files")
        return []


class StubSession:
    def __init__(self, process, display_name: str = "") -> None:
        self.Process = process
        self.DisplayName = display_name
        self.ProcessId = process.pid


def test_refresh_reports_every_pid_of_a_grouped_process():
    sessions = [
        StubSession(StubProcess(11, "voidrunner.exe", _GAME_PATH)),
        StubSession(StubProcess(22, "voidrunner.exe", _GAME_PATH)),
    ]

    with patch(_PATCH_SESSIONS, return_value=sessions), patch(_PATCH_TITLES, return_value={}), patch(
        "sound_mixer.audio.pycaw_backend._ProcessNameCache.resolve"
    ) as mock_resolve:
        backend = PycawAudioBackend()
        backend.refresh()

    mock_resolve.assert_called_once_with(_GAME_KEY, _GAME_PATH, [11, 22], {})


def test_refresh_groups_sessions_of_the_same_process():
    sessions = [
        StubSession(StubProcess(11, "voidrunner.exe", _GAME_PATH)),
        StubSession(StubProcess(22, "voidrunner.exe", _GAME_PATH)),
    ]

    with patch(_PATCH_SESSIONS, return_value=sessions), patch(
        _PATCH_EXE, return_value="webruntime"
    ), patch(_PATCH_TITLES, return_value={22: _GAME_TITLE}):
        backend = PycawAudioBackend()
        backend.refresh()
        entries = backend.enumerate_sessions()

    assert len(entries) == 1
    assert entries[0].process_name == "voidrunner.exe"
    assert entries[0].display_name == _GAME_TITLE


def test_refresh_keeps_same_named_executables_from_different_folders_apart():
    sessions = [
        StubSession(StubProcess(11, "Game.exe", "G:/Games/Voidrunner/Game.exe")),
        StubSession(StubProcess(22, "game.exe", "D:/Downloads/Starfall Demo/game.exe")),
    ]

    with patch(_PATCH_SESSIONS, return_value=sessions), patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES,
        return_value={11: _GAME_TITLE, 22: "Starfall Demo Build"},
    ):
        backend = PycawAudioBackend()
        backend.refresh()
        entries = backend.enumerate_sessions()

    assert [entry.key for entry in entries] == [
        "g:/games/voidrunner/game.exe",
        "d:/downloads/starfall demo/game.exe",
    ]
    assert [entry.display_name for entry in entries] == [_GAME_TITLE, "Starfall Demo Build"]
    assert [entry.icon_path for entry in entries] == [
        "G:/Games/Voidrunner/Game.exe",
        "D:/Downloads/Starfall Demo/game.exe",
    ]


def test_refresh_groups_sessions_running_from_the_same_executable():
    sessions = [
        StubSession(StubProcess(11, "runtime.exe", "D:/Games/MyGame/runtime.exe")),
        StubSession(StubProcess(22, "runtime.exe", "D:/Games/MyGame/runtime.exe")),
    ]

    with patch(_PATCH_SESSIONS, return_value=sessions), patch(
        _PATCH_EXE, return_value="webruntime"
    ), patch(_PATCH_TITLES, return_value={22: "My RPG Adventure"}):
        backend = PycawAudioBackend()
        backend.refresh()
        entries = backend.enumerate_sessions()

    assert len(entries) == 1
    assert entries[0].key == "d:/games/mygame/runtime.exe"
    assert entries[0].display_name == "My RPG Adventure"


def test_refresh_falls_back_to_process_name_when_path_is_unavailable():
    process = StubProcess(11, "Game.exe", "")
    process.exe = _raise_access_denied

    with patch(_PATCH_SESSIONS, return_value=[StubSession(process)]), patch(
        _PATCH_EXE, return_value=""
    ), patch(_PATCH_TITLES, return_value={}):
        backend = PycawAudioBackend()
        backend.refresh()
        entries = backend.enumerate_sessions()

    assert [entry.key for entry in entries] == ["game.exe"]


def test_exe_path_is_read_once_per_process():
    process = StubProcess(11, "Game.exe", "G:/Games/Voidrunner/Game.exe")

    with patch(_PATCH_SESSIONS, return_value=[StubSession(process)]), patch(
        _PATCH_EXE, return_value="Voidrunner Launcher"
    ), patch(_PATCH_TITLES, return_value={}):
        backend = PycawAudioBackend()
        backend.refresh()
        backend.refresh()
        backend.refresh()

    assert process.exe_calls == 1


def test_windows_are_enumerated_once_per_refresh():
    sessions = [
        StubSession(StubProcess(11, "voidrunner.exe", _GAME_PATH)),
        StubSession(StubProcess(22, "starfall.exe", "E:/Games/Starfall/starfall.exe")),
        StubSession(StubProcess(33, "lumen.exe", "C:/Lumen/lumen.exe")),
    ]

    with patch(_PATCH_SESSIONS, return_value=sessions), patch(_PATCH_EXE, return_value=""), patch(
        _PATCH_TITLES, return_value={}
    ) as mock_titles:
        backend = PycawAudioBackend()
        backend.refresh()

    assert mock_titles.call_count == 1


def test_windows_are_not_enumerated_once_every_name_is_settled():
    sessions = [StubSession(StubProcess(11, "aurora.exe", "C:/Aurora/aurora.exe"))]

    with patch(_PATCH_SESSIONS, return_value=sessions), patch(
        _PATCH_EXE, return_value="Aurora Browser"
    ), patch(_PATCH_TITLES, return_value={11: "Some Page - Aurora Browser"}) as mock_titles:
        backend = PycawAudioBackend()
        backend.refresh()
        backend.refresh()
        backend.refresh()
        entries = backend.enumerate_sessions()

    assert mock_titles.call_count == 1
    assert entries[0].display_name == "Aurora Browser"


def test_refresh_never_reads_another_process_command_line_or_memory():
    process = StubProcess(11, "voidrunner.exe", _GAME_PATH)

    with patch(_PATCH_SESSIONS, return_value=[StubSession(process)]), patch(
        _PATCH_EXE, return_value="webruntime"
    ), patch(_PATCH_TITLES, return_value={11: _GAME_TITLE}):
        backend = PycawAudioBackend()
        backend.refresh()
        backend.refresh()

    assert process.forbidden_calls == []
