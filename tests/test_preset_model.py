from time import perf_counter

from sound_mixer.audio.events import SessionEvent
from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.settings.store import SettingsStore


def make_preset(settings, name="Game", volume=.25):
    preset = settings.create_preset(name, .6)
    preset["apps"] = {"aurora.exe": {"volume": volume, "muted": False}}
    settings.set_presets([*settings.get_presets()[:-1], preset])
    return preset


def test_switching_restores_apps_master_and_preserves_profiles(settings, fake_backend):
    model = MixerModel(fake_backend, settings)
    model.set_volume(.7, 1)
    model.set_volume(.8, 0)
    a = make_preset(settings)
    b = make_preset(settings, "Music", .4)
    model.activate_preset(a["id"])
    assert model.entries[1].volume == .25
    assert fake_backend.get_master_volume() == .6
    model.set_volume(.3, 1)
    model.toggle_mute(1)
    model.set_volume(.5, 0)
    model.toggle_mute(0)
    model.activate_preset(b["id"])
    assert model.entries[1].volume == .4 and not model.entries[1].muted
    model.activate_preset(a["id"])
    assert (model.entries[1].volume, model.entries[1].muted) == (.3, True)
    assert (fake_backend.get_master_volume(), fake_backend.get_master_mute()) == (.5, True)
    model.toggle_preset(a["id"])
    assert model.active_preset_id is None
    assert (model.entries[1].volume, model.entries[1].muted) == (.7, False)
    assert (fake_backend.get_master_volume(), fake_backend.get_master_mute()) == (.8, False)


def test_external_change_auto_add_and_stale_events(settings, fake_backend):
    model = MixerModel(fake_backend, settings)
    a = make_preset(settings)
    session = fake_backend.enumerate_sessions()[1]
    old = SessionEvent.volume_changed(1, session.member_ids[0], .9, True)
    timestamp = perf_counter()
    model.activate_preset(a["id"])
    assert not model.apply_session_state(old)
    assert not model.observe_master_state(.99, True, timestamp)
    assert "lumen.exe" not in settings.get_preset(a["id"])["apps"]
    event = SessionEvent.volume_changed(1, session.member_ids[0], .2, True)
    model.apply_session_state(event)
    assert settings.get_preset(a["id"])["apps"]["lumen.exe"] == {"volume": .2, "muted": True}
    model.observe_master_state(.1, True, perf_counter())
    assert settings.get_profile_master_state() == (.1, True)
    assert settings.get_app_volume("lumen.exe") == 1


def test_restart_new_sessions_and_deleted_active_preset(settings, fake_backend):
    preset = make_preset(settings)
    settings.set_active_preset_id(preset["id"])
    reloaded = SettingsStore(settings.path)
    reloaded.load()
    model = MixerModel(fake_backend, reloaded)
    assert model.entries[1].volume == .25
    assert fake_backend.get_master_volume() == .6
    fake_backend.add_session(FakeAudioSession(pid=999, process_name="new.exe", display_name="New"))
    model.refresh()
    assert next(e for e in model.entries if e.key == "new.exe").volume == 1
    assert "new.exe" not in reloaded.get_preset(preset["id"])["apps"]
    reloaded.delete_preset(preset["id"])
    model.apply_profile()
    assert model.entries[1].volume == 1


def test_native_float_rounding_does_not_enroll_untouched_apps(settings):
    import struct
    from sound_mixer.audio.fake_backend import FakeAudioBackend

    class NativePrecisionSession(FakeAudioSession):
        def set_volume(self, level, member_ids=None):
            level = struct.unpack("f", struct.pack("f", level))[0]
            super().set_volume(level, member_ids)

    session = NativePrecisionSession(pid=100, process_name="other.exe", display_name="Other")
    backend = FakeAudioBackend(sessions=[session])
    settings.set_app_volume(session.key, .65)
    model = MixerModel(backend, settings)
    preset = make_preset(settings)
    model.activate_preset(preset["id"])
    model.refresh()
    assert set(settings.get_preset(preset["id"])["apps"]) == {"aurora.exe"}
    assert settings.get_app_volume(session.key) == .65
    assert abs(session.volume - .65) < 1e-6
    model.apply_session_state(SessionEvent.volume_changed(1, session.member_ids[0], session.volume, False))
    assert "other.exe" not in settings.get_preset(preset["id"])["apps"]
