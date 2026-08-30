import pytest

from sound_mixer.audio.fake_backend import FakeAudioBackend, FakeAudioSession
from sound_mixer.mixer.model import MASTER_KEY, MixerModel
from sound_mixer.settings.store import SettingsStore


def make_backend() -> FakeAudioBackend:
    return FakeAudioBackend(
        sessions=[
            FakeAudioSession(pid=100, process_name="aurora.exe", display_name="Aurora Browser", volume=1.0),
            FakeAudioSession(pid=200, process_name="lumen.exe", display_name="Lumen", volume=1.0),
        ],
        master_volume=0.5,
    )


def test_initial_state(settings):
    model = MixerModel(make_backend(), settings)

    assert model.entries[0].key == MASTER_KEY
    assert model.entries[0].is_master is True
    assert model.focused_index == 0


def test_refresh_populates_entries(settings):
    model = MixerModel(make_backend(), settings)

    assert [e.key for e in model.entries] == [MASTER_KEY, "aurora.exe", "lumen.exe"]


def test_persisted_volume_applied_on_first_sight(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_app_volume("aurora.exe", 0.3)

    backend = make_backend()
    model = MixerModel(backend, store)

    aurora_entry = next(e for e in model.entries if e.key == "aurora.exe")
    assert aurora_entry.volume == pytest.approx(0.3)

    aurora_session = next(s for s in backend.enumerate_sessions() if s.process_name == "aurora.exe")
    assert aurora_session.volume == pytest.approx(0.3)


def test_default_app_volume_applied_on_first_sight(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.3)

    backend = make_backend()
    model = MixerModel(backend, store)

    aurora_entry = next(e for e in model.entries if e.key == "aurora.exe")
    assert aurora_entry.volume == pytest.approx(0.3)

    aurora_session = next(s for s in backend.enumerate_sessions() if s.process_name == "aurora.exe")
    assert aurora_session.volume == pytest.approx(0.3)


def test_move_focus_clamped(settings):
    model = MixerModel(make_backend(), settings)

    model.move_focus(-1)
    assert model.focused_index == 0

    model.move_focus(1)
    assert model.focused_index == 1

    model.move_focus(1)
    assert model.focused_index == 2

    model.move_focus(1)
    assert model.focused_index == 2


def test_adjust_volume_clamps_upper_bound(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    backend.set_master_volume(0.98)
    model.refresh()

    result = model.adjust_volume(0.05)

    assert result == 1.0
    assert backend.get_master_volume() == 1.0


def test_adjust_volume_clamps_lower_bound(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    backend.set_master_volume(0.02)
    model.refresh()

    result = model.adjust_volume(-0.05)

    assert result == 0.0
    assert backend.get_master_volume() == 0.0


def test_per_app_independence(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    aurora_index = next(i for i, e in enumerate(model.entries) if e.key == "aurora.exe")
    lumen_index = next(i for i, e in enumerate(model.entries) if e.key == "lumen.exe")

    model.set_volume(0.2, aurora_index)

    assert model.entries[aurora_index].volume == pytest.approx(0.2)
    assert model.entries[lumen_index].volume == pytest.approx(1.0)
    assert model.entries[0].volume == pytest.approx(0.5)


def test_volume_change_persists(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    backend = make_backend()
    model = MixerModel(backend, store)

    aurora_index = next(i for i, e in enumerate(model.entries) if e.key == "aurora.exe")
    model.set_volume(0.25, aurora_index)

    reloaded = SettingsStore(path)
    reloaded.load()

    assert reloaded.get_app_volume("aurora.exe") == pytest.approx(0.25)


def test_toggle_mute(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    aurora_index = next(i for i, e in enumerate(model.entries) if e.key == "aurora.exe")
    assert model.entries[aurora_index].muted is False

    muted = model.toggle_mute(aurora_index)

    assert muted is True
    assert model.entries[aurora_index].muted is True

    aurora_session = next(s for s in backend.enumerate_sessions() if s.process_name == "aurora.exe")
    assert aurora_session.muted is True
    assert settings.get_app_muted("aurora.exe") is True


def test_master_mute_listener_called_with_current_state_on_register(settings):
    backend = FakeAudioBackend(sessions=[], master_volume=0.5, master_muted=True)
    model = MixerModel(backend, settings)

    received: list[bool] = []
    model.set_master_mute_listener(received.append)

    assert received == [True]


def test_master_mute_listener_notified_when_master_muted(settings):
    model = MixerModel(make_backend(), settings)

    received: list[bool] = []
    model.set_master_mute_listener(received.append)
    master_index = next(i for i, e in enumerate(model.entries) if e.key == MASTER_KEY)

    model.toggle_mute(master_index)

    assert received == [False, True]


def test_master_mute_listener_not_notified_when_app_muted(settings):
    model = MixerModel(make_backend(), settings)

    received: list[bool] = []
    model.set_master_mute_listener(received.append)
    aurora_index = next(i for i, e in enumerate(model.entries) if e.key == "aurora.exe")

    model.toggle_mute(aurora_index)

    assert received == [False]


def test_master_mute_listener_notified_on_external_change(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    received: list[bool] = []
    model.set_master_mute_listener(received.append)

    backend.set_master_mute(True)
    model.refresh()

    assert received == [False, True]


def test_session_removed_resets_focus(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    aurora_index = next(i for i, e in enumerate(model.entries) if e.key == "aurora.exe")
    model.focused_index = aurora_index

    backend.remove_session("aurora.exe")
    model.refresh()

    assert all(e.key != "aurora.exe" for e in model.entries)
    assert model.focused_index == 0


def test_arrow_vs_scroll_step(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    backend.set_master_volume(0.5)
    model.refresh()

    arrow_result = model.adjust_volume(0.05)
    assert arrow_result == pytest.approx(0.55)

    scroll_result = model.adjust_volume(0.02)
    assert scroll_result == pytest.approx(0.57)


def test_ignore_app_moves_entry_to_ignored(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("aurora.exe")

    assert all(e.key != "aurora.exe" for e in model.entries)
    assert any(e.key == "aurora.exe" for e in model.ignored_entries)


def test_ignore_app_persists(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("aurora.exe")

    reloaded_store = SettingsStore(path)
    reloaded_store.load()
    assert reloaded_store.is_app_ignored("aurora.exe") is True


def test_unignore_app_moves_entry_back_to_active(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("aurora.exe")
    model.unignore_app("aurora.exe")

    assert any(e.key == "aurora.exe" for e in model.entries)
    assert all(e.key != "aurora.exe" for e in model.ignored_entries)


def test_set_ignored_volume_updates_session(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    backend = make_backend()
    model = MixerModel(backend, store)

    model.ignore_app("aurora.exe")
    model.set_ignored_volume("aurora.exe", 0.3)

    aurora_session = next(s for s in backend.enumerate_sessions() if s.process_name == "aurora.exe")
    assert aurora_session.volume == pytest.approx(0.3)


def test_toggle_ignored_mute(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    backend = make_backend()
    model = MixerModel(backend, store)

    model.ignore_app("aurora.exe")
    muted = model.toggle_ignored_mute("aurora.exe")

    assert muted is True
    aurora_session = next(s for s in backend.enumerate_sessions() if s.process_name == "aurora.exe")
    assert aurora_session.muted is True


def test_master_entry_cannot_be_ignored(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("master")

    assert any(e.key == "master" for e in model.entries)


def test_ignored_entries_empty_by_default(settings):
    model = MixerModel(make_backend(), settings)

    assert model.ignored_entries == []


def test_default_volume_reapplied_when_session_recreated_under_same_name(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.4)

    backend = FakeAudioBackend(sessions=[], master_volume=1.0)
    model = MixerModel(backend, store)

    first_instance = FakeAudioSession(pid=300, process_name="nw.exe", display_name="Game A", volume=1.0)
    backend.add_session(first_instance)
    model.refresh()
    assert first_instance.volume == pytest.approx(0.4)

    backend.remove_session("nw.exe")
    second_instance = FakeAudioSession(pid=301, process_name="nw.exe", display_name="Game B", volume=1.0)
    backend.add_session(second_instance)
    model.refresh()

    assert second_instance.volume == pytest.approx(0.4)


def test_versioned_executable_new_instance_gets_default(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.3)

    backend = FakeAudioBackend(sessions=[], master_volume=1.0)
    model = MixerModel(backend, store)

    old_version = FakeAudioSession(pid=400, process_name="testddd1.5.1.2.6.exe", display_name="Game", volume=1.0)
    backend.add_session(old_version)
    model.refresh()
    assert old_version.volume == pytest.approx(0.3)

    backend.remove_session("testddd1.5.1.2.6.exe")
    new_version = FakeAudioSession(pid=401, process_name="testddd1.5.1.2.7.exe", display_name="Game", volume=1.0)
    backend.add_session(new_version)
    model.refresh()

    assert new_version.volume == pytest.approx(0.3)


def test_running_instance_not_reapplied_on_refresh(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.4)

    session = FakeAudioSession(pid=500, process_name="aurora.exe", display_name="Aurora", volume=1.0)
    backend = FakeAudioBackend(sessions=[session], master_volume=1.0)
    model = MixerModel(backend, store)
    assert session.volume == pytest.approx(0.4)

    session.set_volume(0.9)
    model.refresh()

    assert session.volume == pytest.approx(0.9)


def test_default_volume_applied_to_new_session_after_initial_refresh(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.4)

    backend = FakeAudioBackend(sessions=[], master_volume=1.0)
    model = MixerModel(backend, store)

    new_session = FakeAudioSession(pid=300, process_name="ripple.exe", display_name="Ripple", volume=1.0)
    backend.add_session(new_session)
    model.refresh()

    ripple_entry = next((e for e in model.entries if e.key == "ripple.exe"), None)
    assert ripple_entry is not None
    assert ripple_entry.volume == pytest.approx(0.4)

    ripple_session = next(s for s in backend.enumerate_sessions() if s.process_name == "ripple.exe")
    assert ripple_session.volume == pytest.approx(0.4)


def _game_sessions():
    return [
        FakeAudioSession(
            pid=600,
            process_name="Game.exe",
            display_name="Voidrunner: Echoes",
            key="G:/Games/VOIDRUNNER/Game.exe",
            volume=1.0,
        ),
        FakeAudioSession(
            pid=601,
            process_name="game.exe",
            display_name="Starfall Demo",
            key="D:/Downloads/Starfall Demo/game.exe",
            volume=1.0,
        ),
    ]


def test_same_named_executables_from_different_folders_get_separate_entries(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    voidrunner, webruntime_game = _game_sessions()
    model = MixerModel(FakeAudioBackend(sessions=[voidrunner, webruntime_game]), store)

    keys = [entry.key for entry in model.entries if not entry.is_master]
    names = [entry.display_name for entry in model.entries if not entry.is_master]

    assert keys == ["g:/games/voidrunner/game.exe", "d:/downloads/starfall demo/game.exe"]
    assert names == ["Voidrunner: Echoes", "Starfall Demo"]


def test_volume_change_affects_only_the_matching_install(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    voidrunner, webruntime_game = _game_sessions()
    model = MixerModel(FakeAudioBackend(sessions=[voidrunner, webruntime_game]), store)
    index = next(i for i, entry in enumerate(model.entries) if entry.key == voidrunner.key)

    model.set_volume(0.25, index)

    assert voidrunner.volume == pytest.approx(0.25)
    assert webruntime_game.volume == pytest.approx(1.0)
    assert store.get_app_volume(webruntime_game.key) == pytest.approx(store.get_default_app_volume())


def test_muting_one_install_does_not_mute_the_other(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    voidrunner, webruntime_game = _game_sessions()
    model = MixerModel(FakeAudioBackend(sessions=[voidrunner, webruntime_game]), store)
    index = next(i for i, entry in enumerate(model.entries) if entry.key == webruntime_game.key)

    model.toggle_mute(index)

    assert webruntime_game.muted is True
    assert voidrunner.muted is False


def test_ignoring_one_install_keeps_the_other_visible(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    voidrunner, webruntime_game = _game_sessions()
    model = MixerModel(FakeAudioBackend(sessions=[voidrunner, webruntime_game]), store)

    model.ignore_app(voidrunner.key)

    assert [entry.key for entry in model.ignored_entries] == [voidrunner.key]
    assert [entry.key for entry in model.entries if not entry.is_master] == [webruntime_game.key]


def test_whitelist_keeps_master_and_only_enabled_allowed_apps(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["whitelist"]["apps"] = [
        {"path": "aurora.exe", "enabled": True},
        {"path": "lumen.exe", "enabled": False},
    ]
    store.set_whitelist_enabled(True)

    model = MixerModel(make_backend(), store)

    assert [entry.key for entry in model.entries] == [MASTER_KEY, "aurora.exe"]
    assert model.ignored_entries == []


def test_whitelist_uses_full_path_before_basename_fallback(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["whitelist"]["apps"] = [{"path": "G:/Games/VOIDRUNNER/Game.exe", "enabled": True}]
    store.set_whitelist_enabled(True)
    voidrunner, webruntime_game = _game_sessions()

    model = MixerModel(FakeAudioBackend(sessions=[voidrunner, webruntime_game]), store)

    assert [entry.key for entry in model.entries if not entry.is_master] == [voidrunner.key]


def test_ignored_allowed_app_stays_out_of_active_entries(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.data["whitelist"]["apps"] = [{"path": "aurora.exe", "enabled": True}]
    store.set_whitelist_enabled(True)
    store.add_ignored_app("aurora.exe")

    model = MixerModel(make_backend(), store)

    assert [entry.key for entry in model.entries] == [MASTER_KEY]
    assert [entry.key for entry in model.ignored_entries] == ["aurora.exe"]


def test_keyed_volume_and_mute_operations_focus_matching_app(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    model.adjust_volume_by_key("lumen.exe", -0.2)
    muted = model.toggle_mute_by_key("lumen.exe")

    assert model.focused_entry.key == "lumen.exe"
    assert model.focused_entry.volume == pytest.approx(0.8)
    assert muted is True
