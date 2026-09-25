from copy import deepcopy

import pytest
from PySide6.QtCore import QEvent

from sound_mixer.app_key import normalize_app_key
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings_window.window import SettingsWindow
from tests.test_preset_model import make_preset


@pytest.fixture
def windows(qapp, settings):
    opened = []

    def create(**kwargs):
        window = SettingsWindow(settings, **kwargs)
        opened.append(window)
        return window

    yield create
    for window in opened:
        window.close()
        window.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_add_rename_shortcut_cancel_and_accept(qapp, windows, settings):
    before = deepcopy(settings.data)
    window = windows()
    window.show()
    qapp.processEvents()
    editor = window._presets_editor
    editor.add_button.click()
    card = editor.cards[0]
    card.name.setText("Gaming")
    card.active.click()
    card.shortcut.click()
    assert window._tabs.currentWidget() is window._hotkeys_scroll
    action = "preset:" + card.preset_id
    _, combo, enabled = next(row for row in window._hotkey_rows if row[0] == action)
    assert window._hotkey_fields[action].layout().itemAt(0).widget().text() == "Gaming"
    assert window.focusWidget() is combo
    assert settings.data == before
    window.reject()
    assert settings.data == before
    saved = windows()
    card = saved._presets_editor.add_preset()
    card.name.setText("Music")
    card.active.click()
    saved.accept()
    assert settings.get_active_preset_id() == card.preset_id
    assert settings.get_preset(card.preset_id)["name"] == "Music"


def test_drop_deduplicate_isolation_switch_and_remove(windows, tmp_path, settings):
    paths = [tmp_path / "one.exe", tmp_path / "two.exe"]
    for path in paths:
        path.touch()
    window = windows()
    card = window._presets_editor.add_preset()
    for path in paths + paths:
        card.drop_zone.app_dropped.emit(str(path))
    assert len(card.rows) == 2
    a, b = card.rows.values()
    a.isolate.setChecked(True)
    assert a.volume.isEnabled() and not b.volume.isEnabled()
    assert b.isolate.isEnabled()
    b.isolate.setChecked(True)
    assert not a.isolate.isChecked() and b.volume.isEnabled()
    assert not a.volume.isEnabled()
    assert card.preset()["isolated_app"] == b.key
    b._remove_button.click()
    assert card.preset()["isolated_app"] is None
    assert a.volume.isEnabled()
    card.add_path(str(tmp_path / "missing.exe"))
    assert not card.error.isHidden()
    assert len(card.rows) == 1


def test_draft_whitelist_blocks_drop_and_clears_isolation(windows, tmp_path):
    app = tmp_path / "one.exe"
    app.touch()
    window = windows()
    card = window._presets_editor.add_preset()
    card.add_path(str(app))
    row = next(iter(card.rows.values()))
    row.isolate.setChecked(True)
    window._whitelist_checkbox.setChecked(True)
    window._presets_editor.refresh_whitelist()
    assert not row.isolate.isChecked() and not row.volume.isEnabled()
    card.remove_row(row.key)
    card.add_path(str(app))
    assert not card.rows and not card.error.isHidden()
    window._whitelist_editor.add_path(str(app))
    card.add_path(str(app))
    assert normalize_app_key(str(app)) in card.rows


def test_ok_merges_background_changes_without_losing_auto_added_apps(windows, settings):
    preset = make_preset(settings, volume=.333)
    settings.set_active_preset_id(preset["id"])
    window = windows()
    card = window._presets_editor.cards[0]
    card.name.setText("Renamed")
    settings.set_profile_app_state("aurora.exe", .43, True)
    settings.set_profile_app_state("new.exe", .27, False)
    settings.set_profile_master_state(.37, True)
    window.accept()
    result = settings.get_preset(preset["id"])
    assert result["name"] == "Renamed"
    assert result["apps"] == {"aurora.exe": {"volume": .43, "muted": True},
                              "new.exe": {"volume": .27, "muted": False}}
    assert result["master_volume"] == .37 and result["master_muted"]


def test_explicit_volume_edit_wins_but_other_background_fields_survive(windows, settings):
    preset = make_preset(settings)
    settings.set_active_preset_id(preset["id"])
    window = windows()
    window._presets_editor.cards[0].rows["aurora.exe"].volume.setValue(18)
    settings.set_profile_app_state("aurora.exe", .43, True)
    window.accept()
    assert settings.get_profile_app_state("aurora.exe") == (.18, True)


def test_delete_active_preset_restores_audio_on_ok(qapp, windows, settings, fake_backend):
    model = MixerModel(fake_backend, settings)
    preset = make_preset(settings)
    model.activate_preset(preset["id"])
    overlay = OverlayWindow(model, settings)
    try:
        window = windows(overlay=overlay)
        window._presets_editor.cards[0].remove.click()
        assert model.active_preset_id == preset["id"]
        window.accept()
        assert model.active_preset_id is None
        assert fake_backend.enumerate_sessions()[0].volume == 1
        assert "preset:" + preset["id"] not in window._hotkey_fields
    finally:
        overlay.close()
        overlay.deleteLater()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_preset_shortcut_is_saved_and_conflict_does_not_partially_save(windows, settings):
    window = windows()
    card = window._presets_editor.add_preset()
    action, editor, enabled = next(row for row in window._hotkey_rows if row[0] == "preset:" + card.preset_id)
    editor.set_combo("ctrl+alt+num5")
    enabled.setChecked(True)
    before = deepcopy(settings.data)
    window.accept()
    assert settings.data == before
    assert not window._error_label.isHidden()
    editor.set_combo("ctrl+shift+f9")
    window.accept()
    assert settings.get_preset(card.preset_id)["hotkey"] == {"combo": "ctrl+shift+f9", "enabled": True}


def test_widgets_show_mode_and_lock_other_volume_controls(qapp, settings, fake_backend):
    from sound_mixer.overlay.mini_widget import MiniWidget
    from tests.test_isolation import isolated_model

    model, preset = isolated_model(settings, fake_backend)
    overlay = OverlayWindow(model, settings)
    overlay._finish_warm_up()
    mini = MiniWidget(model, settings)
    try:
        overlay.show()
        overlay.refresh_view()
        mini.set_enabled(True)
        assert overlay._title_name_label.text() == "Sound Mixer"
        assert overlay._preset_indicator.text() == "P1"
        assert overlay._preset_indicator.toolTip() == "Game"
        assert mini.toolTip() == "Game"
        assert not overlay._entry_widgets[2]._slider.isEnabled()
        assert not overlay._entry_widgets[2]._mute_button.isEnabled()
        assert not mini._entries["lumen.exe"].isEnabled()
        model.activate_preset(None)
        overlay.refresh_view()
        mini.refresh_view()
        assert overlay._entry_widgets[2]._slider.isEnabled()
        assert mini._entries["lumen.exe"].isEnabled()
        assert overlay._title_name_label.text() == "Sound Mixer"
        assert overlay._preset_indicator.isHidden()
    finally:
        mini.stop()
        mini.close()
        overlay.close()
        mini.deleteLater()
        overlay.deleteLater()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_preset_limit_disables_add_and_removal_restores_it(windows, settings):
    window = windows()
    editor = window._presets_editor
    for _ in range(9):
        editor.add_button.click()
    assert len(editor.presets()) == 9
    assert not editor.add_button.isEnabled()
    editor.add_button.click()
    assert editor.add_preset() is None
    assert len(editor.presets()) == 9
    editor.cards[0].remove.click()
    assert editor.add_button.isEnabled()
    editor.add_button.click()
    assert len(editor.presets()) == 9
    window.accept()
    assert len(settings.get_presets()) == 9
    assert not windows()._presets_editor.add_button.isEnabled()
