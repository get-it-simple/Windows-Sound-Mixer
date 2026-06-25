import pytest

from sound_mixer.audio.fake_backend import FakeAudioBackend, FakeAudioSession
from sound_mixer.mixer.model import MASTER_KEY, MixerModel
from sound_mixer.settings.store import SettingsStore


def make_backend() -> FakeAudioBackend:
    return FakeAudioBackend(
        sessions=[
            FakeAudioSession(pid=100, process_name="chrome.exe", display_name="Google Chrome", volume=1.0),
            FakeAudioSession(pid=200, process_name="spotify.exe", display_name="Spotify", volume=1.0),
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

    assert [e.key for e in model.entries] == [MASTER_KEY, "chrome.exe", "spotify.exe"]


def test_persisted_volume_applied_on_first_sight(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_app_volume("chrome.exe", 0.3)

    backend = make_backend()
    model = MixerModel(backend, store)

    chrome_entry = next(e for e in model.entries if e.key == "chrome.exe")
    assert chrome_entry.volume == pytest.approx(0.3)

    chrome_session = next(s for s in backend.enumerate_sessions() if s.process_name == "chrome.exe")
    assert chrome_session.volume == pytest.approx(0.3)


def test_default_app_volume_applied_on_first_sight(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.3)

    backend = make_backend()
    model = MixerModel(backend, store)

    chrome_entry = next(e for e in model.entries if e.key == "chrome.exe")
    assert chrome_entry.volume == pytest.approx(0.3)

    chrome_session = next(s for s in backend.enumerate_sessions() if s.process_name == "chrome.exe")
    assert chrome_session.volume == pytest.approx(0.3)


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

    chrome_index = next(i for i, e in enumerate(model.entries) if e.key == "chrome.exe")
    spotify_index = next(i for i, e in enumerate(model.entries) if e.key == "spotify.exe")

    model.set_volume(0.2, chrome_index)

    assert model.entries[chrome_index].volume == pytest.approx(0.2)
    assert model.entries[spotify_index].volume == pytest.approx(1.0)
    assert model.entries[0].volume == pytest.approx(0.5)


def test_volume_change_persists(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()

    backend = make_backend()
    model = MixerModel(backend, store)

    chrome_index = next(i for i, e in enumerate(model.entries) if e.key == "chrome.exe")
    model.set_volume(0.25, chrome_index)

    reloaded = SettingsStore(path)
    reloaded.load()

    assert reloaded.get_app_volume("chrome.exe") == pytest.approx(0.25)


def test_toggle_mute(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    chrome_index = next(i for i, e in enumerate(model.entries) if e.key == "chrome.exe")
    assert model.entries[chrome_index].muted is False

    muted = model.toggle_mute(chrome_index)

    assert muted is True
    assert model.entries[chrome_index].muted is True

    chrome_session = next(s for s in backend.enumerate_sessions() if s.process_name == "chrome.exe")
    assert chrome_session.muted is True
    assert settings.get_app_muted("chrome.exe") is True


def test_session_removed_resets_focus(settings):
    backend = make_backend()
    model = MixerModel(backend, settings)

    chrome_index = next(i for i, e in enumerate(model.entries) if e.key == "chrome.exe")
    model.focused_index = chrome_index

    backend.remove_session("chrome.exe")
    model.refresh()

    assert all(e.key != "chrome.exe" for e in model.entries)
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

    model.ignore_app("chrome.exe")

    assert all(e.key != "chrome.exe" for e in model.entries)
    assert any(e.key == "chrome.exe" for e in model.ignored_entries)


def test_ignore_app_persists(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("chrome.exe")

    reloaded_store = SettingsStore(path)
    reloaded_store.load()
    assert reloaded_store.is_app_ignored("chrome.exe") is True


def test_unignore_app_moves_entry_back_to_active(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("chrome.exe")
    model.unignore_app("chrome.exe")

    assert any(e.key == "chrome.exe" for e in model.entries)
    assert all(e.key != "chrome.exe" for e in model.ignored_entries)


def test_set_ignored_volume_updates_session(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    backend = make_backend()
    model = MixerModel(backend, store)

    model.ignore_app("chrome.exe")
    model.set_ignored_volume("chrome.exe", 0.3)

    chrome_session = next(s for s in backend.enumerate_sessions() if s.process_name == "chrome.exe")
    assert chrome_session.volume == pytest.approx(0.3)


def test_toggle_ignored_mute(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    backend = make_backend()
    model = MixerModel(backend, store)

    model.ignore_app("chrome.exe")
    muted = model.toggle_ignored_mute("chrome.exe")

    assert muted is True
    chrome_session = next(s for s in backend.enumerate_sessions() if s.process_name == "chrome.exe")
    assert chrome_session.muted is True


def test_master_entry_cannot_be_ignored(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    model = MixerModel(make_backend(), store)

    model.ignore_app("master")

    assert any(e.key == "master" for e in model.entries)


def test_ignored_entries_empty_by_default(settings):
    model = MixerModel(make_backend(), settings)

    assert model.ignored_entries == []


def test_default_volume_applied_to_new_session_after_initial_refresh(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_default_app_volume(0.4)

    backend = FakeAudioBackend(sessions=[], master_volume=1.0)
    model = MixerModel(backend, store)

    new_session = FakeAudioSession(pid=300, process_name="vlc.exe", display_name="VLC", volume=1.0)
    backend.add_session(new_session)
    model.refresh()

    vlc_entry = next((e for e in model.entries if e.key == "vlc.exe"), None)
    assert vlc_entry is not None
    assert vlc_entry.volume == pytest.approx(0.4)

    vlc_session = next(s for s in backend.enumerate_sessions() if s.process_name == "vlc.exe")
    assert vlc_session.volume == pytest.approx(0.4)
