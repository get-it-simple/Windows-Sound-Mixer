from sound_mixer.settings_window.window import SettingsWindow


def test_initial_field_values(qapp, settings):
    window = SettingsWindow(settings)

    assert window._autostart_checkbox.isChecked() == settings.get_autostart_enabled()
    assert window._tooltip_delay_spinbox.value() == settings.get_tooltip_delay_ms()
    assert window._arrow_step_spinbox.value() == round(settings.get_arrow_step() * 100)
    assert window._scroll_step_spinbox.value() == round(settings.get_scroll_step() * 100)

    hotkeys = settings.get_hotkeys()
    assert len(window._hotkey_rows) == len(hotkeys)
    for (action, combo_edit, enabled_checkbox), hotkey in zip(window._hotkey_rows, hotkeys):
        assert action == hotkey["action"]
        assert combo_edit.text() == hotkey["combo"]
        assert enabled_checkbox.isChecked() == hotkey["enabled"]


def test_accept_saves_general_settings(qapp, settings):
    window = SettingsWindow(settings)

    window._autostart_checkbox.setChecked(True)
    window._tooltip_delay_spinbox.setValue(1000)
    window._arrow_step_spinbox.setValue(10)
    window._scroll_step_spinbox.setValue(4)
    window.accept()

    assert settings.get_autostart_enabled() is True
    assert settings.get_tooltip_delay_ms() == 1000
    assert settings.get_arrow_step() == 0.1
    assert settings.get_scroll_step() == 0.04


def test_accept_saves_hotkeys(qapp, settings):
    window = SettingsWindow(settings)

    action, combo_edit, enabled_checkbox = window._hotkey_rows[0]
    combo_edit.setText("ctrl+alt+num6")
    enabled_checkbox.setChecked(False)
    window.accept()

    saved = next(h for h in settings.get_hotkeys() if h["action"] == action)
    assert saved["combo"] == "ctrl+alt+num6"
    assert saved["enabled"] is False


def test_accept_with_invalid_combo_shows_error_and_does_not_save(qapp, settings):
    window = SettingsWindow(settings)

    action, combo_edit, _ = window._hotkey_rows[0]
    original_combo = settings.get_hotkeys()[0]["combo"]
    combo_edit.setText("ctrl+banana")
    window.accept()

    assert not window._error_label.isHidden()
    saved = next(h for h in settings.get_hotkeys() if h["action"] == action)
    assert saved["combo"] == original_combo


def test_about_tab_shows_version(qapp, settings):
    from PySide6.QtWidgets import QLabel

    from sound_mixer import __version__

    window = SettingsWindow(settings)
    about_tab = window._build_about_tab()
    labels = [child.text() for child in about_tab.findChildren(QLabel)]

    assert any(__version__ in label for label in labels)
