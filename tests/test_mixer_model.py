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
