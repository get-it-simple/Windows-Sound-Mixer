import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QEnterEvent

from sound_mixer.app import SoundMixerApp
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.entry_widget import EntryWidget
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings.store import SettingsStore


@pytest.fixture
def mini(qapp, fake_backend, settings):
    widget = MiniWidget(MixerModel(fake_backend, settings), settings)
    widget.set_enabled(True)
    qapp.processEvents()
    yield widget
    widget.stop()
    widget.close()
    widget.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_selection_cycles_and_keeps_main_focus(mini):
    assert mini.selected_key == "aurora.exe"
    sizes = {key: widget.size() for key, widget in mini._entries.items()}
    mini.move_selection(-1)
    assert mini.selected_key == "lumen.exe"
    mini.move_selection(1)
    assert mini.selected_key == "aurora.exe"
    mini.move_selection(1)
    assert mini.selected_key == "lumen.exe"
    assert mini._model.focused_entry.key == "master"
    mini._model.focus_key("aurora.exe")
    mini.refresh_view()
    assert mini.selected_key == "lumen.exe"
    assert mini._entries["lumen.exe"].property("selected") is True
    assert mini._entries["aurora.exe"].property("selected") is False
    assert sizes == {key: widget.size() for key, widget in mini._entries.items()}
    assert mini.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus


def test_hover_does_not_change_selection(qapp, mini):
    qapp.sendEvent(mini._entries["lumen.exe"], QEnterEvent(QPointF(), QPointF(), QPointF()))
    assert mini.selected_key == "aurora.exe"
    assert mini._model.focused_entry.key == "master"


def test_navigation_follows_whitelist_order_and_excludes_ignored_apps(mini, settings):
    apps = []
    for name in ("lumen", "aurora"):
        path = settings.path.parent / f"{name}.exe"
        path.write_bytes(b"MZ")
        apps.append({"path": str(path), "enabled": True})
    settings.set_whitelist_apps(apps)
    settings.set_whitelist_enabled(True)
    mini._model.refresh()
    mini.refresh_view()
    assert list(mini._entries) == ["lumen.exe", "aurora.exe"]
    assert mini.selected_key == "aurora.exe"
    mini.move_selection(1)
    assert mini.selected_key == "lumen.exe"
    mini._model.ignore_app("lumen.exe")
    mini.refresh_view()
    mini.move_selection(-1)
    assert mini.selected_key == "aurora.exe"
    assert list(mini._entries) == ["aurora.exe"]


def test_volume_uses_first_entry_step_bounds_and_updates_both_views(mini, settings, fake_backend):
    overlay = OverlayWindow(mini._model, settings)
    mini.model_changed.connect(overlay.refresh_view)
    settings.set_arrow_step(0.07)
    try:
        mini.adjust_selected_volume(-1)
        sessions = {session.key: session for session in fake_backend.enumerate_sessions()}
        assert sessions["aurora.exe"].volume == pytest.approx(0.93)
        assert sessions["lumen.exe"].volume == 1.0
        assert fake_backend.get_master_volume() == 0.5
        assert mini._model.focused_entry.key == "master"
        assert mini._entries["aurora.exe"]._volume_label.text() == "93%"
        assert any(widget._slider.value() == 93 for widget in overlay.findChildren(EntryWidget))
        mini.adjust_selected_volume(1)
        mini.adjust_selected_volume(1)
        assert sessions["aurora.exe"].volume == 1.0
        settings.set_arrow_step(1.0)
        mini.adjust_selected_volume(-1)
        mini.adjust_selected_volume(-1)
        assert sessions["aurora.exe"].volume == 0.0
        reloaded = SettingsStore(settings.path)
        reloaded.load()
        assert reloaded.get_app_volume("aurora.exe") == 0.0
    finally:
        overlay.close()
        overlay.deleteLater()


def test_master_visibility_controls_navigation_and_persists(mini, settings, fake_backend):
    mini.toggle_master_visibility()
    assert list(mini._entries) == ["master", "aurora.exe", "lumen.exe"]
    assert mini.selected_key == "aurora.exe"
    mini.move_selection(-1)
    assert mini.selected_key == "master"
    mini.adjust_selected_volume(-1)
    assert fake_backend.get_master_volume() == pytest.approx(0.45)
    mini.toggle_master_visibility()
    assert mini.selected_key == "aurora.exe"
    assert "master" not in mini._entries
    assert not fake_backend.get_master_mute()
    saved = SettingsStore(settings.path)
    saved.load()
    assert saved.get_mini_widget_show_master() is False


def test_hidden_navigation_and_volume_are_ignored_but_toggles_work(mini, settings, fake_backend):
    mini.move_selection(1)
    mini.set_enabled(False)
    mini.move_selection(1)
    mini.adjust_selected_volume(-1)
    assert mini.selected_key == "lumen.exe"
    assert all(session.volume == 1.0 for session in fake_backend.enumerate_sessions())
    mini.toggle_master_visibility()
    assert settings.get_mini_widget_show_master()
    assert not mini.isVisible()
    mini.set_enabled(True)
    assert mini.isVisible()
    assert mini.selected_key == "lumen.exe"
    assert list(mini._entries)[0] == "master"


def test_selection_survives_reorder_and_falls_back_after_removal(mini, fake_backend):
    mini.move_selection(1)
    mini._model.entries.reverse()
    mini.refresh_view()
    assert mini.selected_key == "lumen.exe"
    assert list(mini._entries) == ["lumen.exe", "aurora.exe"]
    fake_backend.remove_session("lumen.exe")
    mini._model.refresh()
    mini.refresh_view()
    assert mini.selected_key == "aurora.exe"
    mini.move_selection(1)
    assert mini.selected_key == "aurora.exe"
    fake_backend.remove_session("aurora.exe")
    mini._model.refresh()
    mini.refresh_view()
    assert mini.selected_key is None
    assert not mini.isVisible()
    mini.move_selection(-1)
    mini.adjust_selected_volume(-1)
    assert fake_backend.get_master_volume() == 0.5


def test_master_is_initial_selection_when_shown(qapp, fake_backend, settings):
    settings.set_mini_widget_show_master(True)
    widget = MiniWidget(MixerModel(fake_backend, settings), settings)
    try:
        widget.set_enabled(True)
        assert widget.selected_key == "master"
    finally:
        widget.stop()
        widget.close()


def test_app_handlers_control_mini_widget(mini):
    app = SoundMixerApp.__new__(SoundMixerApp)
    app.mini_widget = mini
    app._on_mini_focus_next_hotkey()
    assert mini.selected_key == "lumen.exe"
    app._on_mini_volume_down_hotkey()
    assert mini._entries["lumen.exe"]._volume_label.text() == "95%"
    app._on_mini_volume_up_hotkey()
    assert mini._entries["lumen.exe"]._volume_label.text() == "100%"
    app._on_mini_focus_prev_hotkey()
    assert mini.selected_key == "aurora.exe"
    app._on_toggle_mini_widget_hotkey()
    assert not mini.isVisible()
    app._on_toggle_mini_widget_hotkey()
    assert mini.isVisible()
