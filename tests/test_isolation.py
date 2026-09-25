from unittest.mock import Mock

from sound_mixer.audio.events import SessionEvent
from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.settings.store import SettingsStore
from sound_mixer.tray.isolation_notifications import IsolationNotifications
from tests.test_preset_model import make_preset


def isolated_model(settings, fake_backend):
    model = MixerModel(fake_backend, settings)
    model.set_volume(.65, 2)
    preset = make_preset(settings)
    preset["isolated_app"] = "aurora.exe"
    settings.set_presets([preset])
    model.activate_preset(preset["id"])
    return model, preset


def test_isolation_blocks_local_and_external_without_overwriting(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    session = fake_backend.enumerate_sessions()[1]
    blocked = []
    model.isolation.on_blocked = blocked.append
    assert session.volume == 0
    assert model.entries[2].volume_locked
    assert model.set_volume(.8, 2) == 0
    assert not model.toggle_mute(2)
    assert not blocked
    event = SessionEvent.volume_changed(1, session.member_ids[0], .9, True)
    session.volume, session.muted = .9, True
    model.apply_session_state(event)
    assert session.volume == 0 and not session.muted
    assert len(blocked) == 1
    assert blocked[0].app_key == "lumen.exe"
    assert settings.get_app_volume("lumen.exe") == .65
    assert "lumen.exe" not in settings.get_preset(preset["id"])["apps"]
    model.apply_session_state(SessionEvent.volume_changed(1, session.member_ids[0], 0, False))
    assert len(blocked) == 1
    model.activate_preset(None)
    assert session.volume == .65


def test_isolation_covers_whitelist_exclusions_new_sessions_and_restart(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    settings.data["whitelist"] = {"enabled": True, "apps": [{"path": "aurora.exe", "enabled": True}]}
    model.refresh()
    new = FakeAudioSession(pid=1000, process_name="new.exe", display_name="New")
    fake_backend.add_session(new)
    model.refresh()
    assert new.volume == 0
    assert [e.key for e in model.entries] == ["master", "aurora.exe"]
    settings.set_whitelist_enabled(False)
    loaded = SettingsStore(settings.path)
    loaded.load()
    restarted = MixerModel(fake_backend, loaded)
    assert new.volume == 0 and restarted.active_preset_id == preset["id"]
    restarted.activate_preset(None)
    assert new.volume == 1
    assert fake_backend.enumerate_sessions()[1].volume == .65


def test_removed_whitelist_target_releases_isolation(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    settings.set_whitelist_enabled(True)
    model.refresh()
    assert model.isolation.target is None
    assert settings.get_preset(preset["id"])["isolated_app"] is None
    assert fake_backend.enumerate_sessions()[1].volume == .65


def test_notifications_global_throttle_without_delayed_queue(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    tray = Mock()
    now = [0.0]
    notifications = IsolationNotifications(tray, settings, model, clock=lambda: now[0])
    model.isolation.on_blocked = notifications.show_blocked
    session = fake_backend.enumerate_sessions()[1]
    for timestamp in (0, 1, 9.9, 10, 10.1):
        now[0] = timestamp
        model.apply_session_state(SessionEvent.volume_changed(1, session.member_ids[0], .5, False))
        assert session.volume == 0
    assert tray.showMessage.call_count == 2
    title, body, _, _ = tray.showMessage.call_args.args
    assert title == "Sound isolation is active"
    assert "Lumen" in body and "Game" in body and "Aurora Browser" in body
    model.activate_preset(None)
    model.activate_preset(preset["id"])
    model.apply_session_state(SessionEvent.volume_changed(1, session.member_ids[0], .5, False))
    assert tray.showMessage.call_count == 2


def test_fallback_rejects_external_change_and_ignores_new_session(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    blocked = []
    model.isolation.on_blocked = blocked.append
    session = fake_backend.enumerate_sessions()[1]
    session.volume = .7
    model.refresh()
    assert session.volume == 0 and len(blocked) == 1
    fake_backend.add_session(FakeAudioSession(pid=1000, process_name="new.exe", display_name="New"))
    model.refresh()
    assert len(blocked) == 1
    assert set(settings.get_preset(preset["id"])["apps"]) == {"aurora.exe"}


def test_isolation_target_change_closed_target_and_saved_levels(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    presets = settings.get_presets()
    presets[0]["apps"]["lumen.exe"] = {"volume": .42, "muted": False}
    presets[0]["isolated_app"] = "lumen.exe"
    settings.set_presets(presets)
    blocked = []
    model.isolation.on_blocked = blocked.append
    model.apply_profile()
    aurora, lumen = fake_backend.enumerate_sessions()
    assert aurora.volume == 0 and lumen.volume == .42
    assert not blocked
    fake_backend.remove_session("lumen.exe")
    model.refresh()
    assert model.isolation.target == "lumen.exe" and aurora.volume == 0
    presets[0]["isolated_app"] = None
    settings.set_presets(presets)
    model.apply_profile()
    assert aurora.volume == .25
    assert not blocked
    assert settings.get_app_volume("lumen.exe") == .65


def test_unknown_apps_restore_original_default_even_when_default_changes(settings, fake_backend):
    model, preset = isolated_model(settings, fake_backend)
    new = FakeAudioSession(pid=1000, process_name="new.exe", display_name="New")
    fake_backend.add_session(new)
    model.refresh()
    assert new.volume == 0
    settings.set_default_app_volume(.2)
    model.activate_preset(None)
    assert new.volume == 1
    assert settings.get_app_volume("new.exe") == 1
    assert settings.data["isolation_restore"] == {}


def test_notifications_skip_old_events_master_target_and_unchanged(settings, fake_backend):
    model = MixerModel(fake_backend, settings)
    session = fake_backend.enumerate_sessions()[1]
    old = SessionEvent.volume_changed(1, session.member_ids[0], .8, True)
    preset = make_preset(settings)
    preset["isolated_app"] = "aurora.exe"
    settings.set_presets([preset])
    blocked = []
    model.isolation.on_blocked = blocked.append
    model.activate_preset(preset["id"])
    model.apply_session_state(old)
    model.set_volume(.3, 0)
    target = fake_backend.enumerate_sessions()[0]
    model.apply_session_state(SessionEvent.volume_changed(1, target.member_ids[0], .5, True))
    model.apply_session_state(SessionEvent.volume_changed(1, session.member_ids[0], 0, False))
    assert not blocked
    assert settings.get_profile_app_state(target.key) == (.5, True)


def test_obsolete_callback_cannot_leave_live_session_outside_isolation(settings, fake_backend):
    model = MixerModel(fake_backend, settings)
    session = fake_backend.enumerate_sessions()[1]
    delayed = SessionEvent.volume_changed(1, session.member_ids[0], .8, True)
    preset = make_preset(settings)
    preset["isolated_app"] = "aurora.exe"
    settings.set_presets([preset])
    model.activate_preset(preset["id"])
    blocked = []
    model.isolation.on_blocked = blocked.append
    session.volume, session.muted = .8, True
    model.apply_session_state(delayed)
    assert session.volume == 0 and not session.muted
    assert not blocked
    assert "lumen.exe" not in settings.get_preset(preset["id"])["apps"]
