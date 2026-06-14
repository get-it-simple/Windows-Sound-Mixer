from sound_mixer.audio.interface import AudioBackend, AudioSession


def create_backend() -> AudioBackend:
    try:
        from sound_mixer.audio.pycaw_backend import PycawAudioBackend

        return PycawAudioBackend()
    except ImportError:
        from sound_mixer.audio.fake_backend import FakeAudioBackend

        return FakeAudioBackend()


__all__ = ["AudioBackend", "AudioSession", "create_backend"]
