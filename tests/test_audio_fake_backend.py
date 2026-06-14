from sound_mixer.audio.fake_backend import FakeAudioBackend, FakeAudioSession
from sound_mixer.audio.interface import AudioBackend, AudioSession


def test_fake_session_implements_protocol():
    session = FakeAudioSession(pid=1, process_name="app.exe", display_name="App")

    assert isinstance(session, AudioSession)


def test_fake_backend_implements_protocol():
    backend = FakeAudioBackend()

    assert isinstance(backend, AudioBackend)


def test_session_set_volume_clamps():
    session = FakeAudioSession(pid=1, process_name="app.exe", display_name="App")

    session.set_volume(1.5)
    assert session.volume == 1.0

    session.set_volume(-0.5)
    assert session.volume == 0.0


def test_backend_master_volume_clamps():
    backend = FakeAudioBackend()

    backend.set_master_volume(2.0)
    assert backend.get_master_volume() == 1.0

    backend.set_master_volume(-1.0)
    assert backend.get_master_volume() == 0.0


def test_add_and_remove_session():
    backend = FakeAudioBackend()
    session = FakeAudioSession(pid=1, process_name="app.exe", display_name="App")

    backend.add_session(session)
    assert backend.enumerate_sessions() == [session]

    backend.remove_session("APP.EXE")
    assert backend.enumerate_sessions() == []


def test_master_mute_toggle():
    backend = FakeAudioBackend()

    assert backend.get_master_mute() is False

    backend.set_master_mute(True)
    assert backend.get_master_mute() is True
