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
        self.InstanceIdentifier = f"session-{id(self)}"
        self.State = 1


class StubVolume:
    def __init__(self, volume=1.0, muted=False):
        self.volume, self.muted = volume, muted
        self.writes = []

    def GetMasterVolume(self):
        return self.volume

    def GetMute(self):
        return self.muted

    def SetMasterVolume(self, volume, context):
        self.volume = volume
        self.writes.append(("volume", volume, str(context)))

    def SetMute(self, muted, context):
        self.muted = bool(muted)
        self.writes.append(("mute", muted, str(context)))


def test_new_members_restore_saved_state_without_resetting_existing_members(settings):
    from sound_mixer.mixer.model import MixerModel
    from sound_mixer.audio.events import VOLUME_EVENT_CONTEXT

    first = StubSession(StubProcess(11, "voidrunner.exe", _GAME_PATH))
    first.SimpleAudioVolume = StubVolume()
    sessions = [first]
    settings.set_app_volume(_GAME_KEY, 0.3)
    settings.set_app_muted(_GAME_KEY, True)
    with patch(_PATCH_SESSIONS, return_value=sessions), patch(_PATCH_TITLES, return_value={}), patch(_PATCH_EXE, return_value="Game"):
        backend = PycawAudioBackend()
        model = MixerModel(backend, settings)
        first.SimpleAudioVolume.volume = 0.6
        model.refresh(include_master=False)
        assert settings.get_app_volume(_GAME_KEY) == 0.6
        first.SimpleAudioVolume.writes.clear()
        for pid in (11, 22):
            added = StubSession(StubProcess(pid, "voidrunner.exe", _GAME_PATH))
            added.SimpleAudioVolume = StubVolume()
            sessions.append(added)
            model.refresh(include_master=False)
            assert added.SimpleAudioVolume.volume == 0.6
            assert added.SimpleAudioVolume.muted
            assert all(write[2] == VOLUME_EVENT_CONTEXT for write in added.SimpleAudioVolume.writes)
        assert first.SimpleAudioVolume.volume == 0.6
        assert first.SimpleAudioVolume.writes == []
        assert len(model.entries) == 2
        assert len(backend.enumerate_sessions()[0].member_ids) == 3


def test_targeted_restore_writes_only_the_new_member():
    from sound_mixer.audio.pycaw_backend import PycawAudioSession

    old = StubSession(StubProcess(11, "game.exe", _GAME_PATH))
    new = StubSession(old.Process)
    old.SimpleAudioVolume = StubVolume(0.6, False)
    new.SimpleAudioVolume = StubVolume(1.0, False)
    group = PycawAudioSession(_GAME_KEY, "game.exe", "Game", [old, new])
    group.set_volume(0.3, {new.InstanceIdentifier})
    group.set_muted(True, {new.InstanceIdentifier})
    assert old.SimpleAudioVolume.volume == 0.6
    assert not old.SimpleAudioVolume.muted
    assert old.SimpleAudioVolume.writes == []
    assert new.SimpleAudioVolume.volume == 0.3
    assert new.SimpleAudioVolume.muted


def test_reused_pid_reads_new_executable_path():
    first = StubSession(StubProcess(11, "game.exe", "C:/First/game.exe"))
    second = StubSession(StubProcess(11, "game.exe", "D:/Other/game.exe"))
    with patch(_PATCH_SESSIONS, side_effect=[[first], [second]]), patch(_PATCH_TITLES, return_value={}), patch(_PATCH_EXE, return_value="Game"):
        backend = PycawAudioBackend()
        backend.refresh()
        backend.refresh()
        assert backend.enumerate_sessions()[0].key == "d:/other/game.exe"
        assert second.Process.exe_calls == 1


def test_inactive_sessions_remain_but_expired_and_disconnected_are_removed():
    active = StubSession(StubProcess(11, "game.exe", _GAME_PATH))
    inactive = StubSession(StubProcess(22, "other.exe", "C:/Other/other.exe"))
    inactive.State = 0
    with patch(_PATCH_SESSIONS, return_value=[active, inactive]), patch(_PATCH_TITLES, return_value={}), patch(_PATCH_EXE, return_value="Game"):
        backend = PycawAudioBackend()
        backend.refresh()
        assert len(backend.enumerate_sessions()) == 2
        backend.exclude_session(active.InstanceIdentifier)
        backend.refresh()
        assert [s.pid for s in backend.enumerate_sessions()] == [22]
        inactive.State = 2
        backend.refresh()
        assert backend.enumerate_sessions() == []


def test_enumeration_failure_removes_stale_sessions():
    session = StubSession(StubProcess(11, "game.exe", _GAME_PATH))
    with patch(_PATCH_SESSIONS, side_effect=[[session], OSError("No output")]), patch(_PATCH_TITLES, return_value={}), patch(_PATCH_EXE, return_value="Game"):
        backend = PycawAudioBackend()
        backend.refresh()
        assert len(backend.enumerate_sessions()) == 1
        backend.refresh()
        assert backend.enumerate_sessions() == []


def test_hidden_name_discovery_skips_window_scans_and_visible_retry_skips_audio_scans():
    session = StubSession(StubProcess(11, "game.exe", _GAME_PATH))
    with patch(_PATCH_SESSIONS, return_value=[session]) as audio, patch(_PATCH_TITLES, return_value={11: "Title - Game"}) as titles, patch(_PATCH_EXE, return_value="Game"):
        backend = PycawAudioBackend()
        backend.set_names_visible(False)
        backend.refresh()
        titles.assert_not_called()
        backend.set_names_visible(True)
        backend._name_cache._next_retry.clear()
        backend.refresh_names()
        titles.assert_called_once()
        audio.assert_called_once()
        assert backend.enumerate_sessions()[0].display_name == "Game"


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
    assert entries[0].pids == (11, 22)


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
