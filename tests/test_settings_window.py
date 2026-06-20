from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings_window.window import SettingsWindow


def test_initial_field_values(qapp, settings):
    window = SettingsWindow(settings)

    assert window._autostart_checkbox.isChecked() == settings.get_autostart_enabled()
    assert window._transparency_checkbox.isChecked() == settings.get_transparency_enabled()
    assert window._tooltip_delay_spinbox.value() == settings.get_tooltip_delay_ms()
    assert window._arrow_step_spinbox.value() == round(settings.get_arrow_step() * 100)
    assert window._scroll_step_spinbox.value() == round(settings.get_scroll_step() * 100)
    assert window._default_app_volume_spinbox.value() == round(settings.get_default_app_volume() * 100)
    assert window._ui_scale_slider.value() == round(settings.get_ui_scale() * 100)

    hotkeys = settings.get_hotkeys()
    assert len(window._hotkey_rows) == len(hotkeys)
    for (action, combo_editor, enabled_checkbox), hotkey in zip(window._hotkey_rows, hotkeys):
        assert action == hotkey["action"]
        assert combo_editor.combo() == hotkey["combo"]
        assert enabled_checkbox.isChecked() == hotkey["enabled"]


def test_accept_saves_general_settings(qapp, settings):
    window = SettingsWindow(settings)

    window._autostart_checkbox.setChecked(True)
    window._transparency_checkbox.setChecked(False)
    window._tooltip_delay_spinbox.setValue(1000)
    window._arrow_step_spinbox.setValue(10)
    window._scroll_step_spinbox.setValue(4)
    window._default_app_volume_spinbox.setValue(75)
    window.accept()

    assert settings.get_autostart_enabled() is True
    assert settings.get_transparency_enabled() is False
    assert settings.get_tooltip_delay_ms() == 1000
    assert settings.get_arrow_step() == 0.1
    assert settings.get_scroll_step() == 0.04
    assert settings.get_default_app_volume() == 0.75


def test_accept_applies_transparency_to_overlay(qapp, fake_backend, settings):
    from sound_mixer.mixer.model import MixerModel

    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    window = SettingsWindow(settings, overlay=overlay)

    window._transparency_checkbox.setChecked(False)
    window.accept()

    assert "rgba(32, 32, 32, 140)" not in overlay._background.styleSheet()


def test_ui_scale_slider_updates_settings_and_overlay_immediately(qapp, fake_backend, settings):
    from sound_mixer.mixer.model import MixerModel
    from sound_mixer.overlay.entry_widget import BASE_FONT_PX

    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    window = SettingsWindow(settings, overlay=overlay)

    window._ui_scale_slider.setValue(150)

    assert settings.get_ui_scale() == 1.5
    assert window._ui_scale_label.text() == "150%"
    spinbox = overlay._entry_widgets[0]._volume_spinbox
    assert spinbox.font().pixelSize() == round(BASE_FONT_PX * 1.5)
    assert spinbox.width() == spinbox.minimumSizeHint().width()


def test_autostart_checkbox_uses_toggle_switch_style(qapp, settings):
    window = SettingsWindow(settings)

    assert window._autostart_checkbox.objectName() == "autostartToggle"
    assert "::indicator" in window._autostart_checkbox.styleSheet()


def test_hotkey_editor_captures_shortcut_in_input_with_inner_selects(qapp, settings):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QComboBox

    window = SettingsWindow(settings)
    _, combo_editor, enabled_checkbox = window._hotkey_rows[0]
    combo_editor.clear()

    assert combo_editor.objectName() == "hotkeyComboInput"
    assert "QFrame#hotkeyComboInput" in combo_editor.styleSheet()
    assert combo_editor.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert combo_editor.minimumHeight() >= 56
    assert not combo_editor.findChildren(QComboBox)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_G,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier,
        "g",
    )
    combo_editor.keyPressEvent(event)

    boxes = combo_editor.findChildren(QComboBox)

    assert combo_editor.combo() == "ctrl+win+g"
    assert len(boxes) == 3
    assert any(box.findText("Win (Left)") >= 0 for box in boxes)
    assert any(box.findText("Ctrl (Left)") >= 0 for box in boxes)
    assert any(box.findText("G") >= 0 for box in boxes)
    assert enabled_checkbox.objectName().endswith("HotkeyToggle")
    assert "::indicator" in enabled_checkbox.styleSheet()


def test_hotkey_editor_uses_powertoys_numpad_names(qapp, settings):
    from PySide6.QtWidgets import QComboBox

    window = SettingsWindow(settings)
    _, combo_editor, _ = window._hotkey_rows[0]
    boxes = combo_editor.findChildren(QComboBox)

    assert any(box.currentText() == "NumPad 5" for box in boxes)


def test_hotkey_editor_backspace_clears_entire_combo(qapp, settings):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    window = SettingsWindow(settings)
    _, combo_editor, _ = window._hotkey_rows[0]
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier)

    combo_editor.keyPressEvent(event)

    assert combo_editor.combo() == ""


def test_accept_saves_hotkeys(qapp, settings):
    window = SettingsWindow(settings)

    action, combo_editor, enabled_checkbox = window._hotkey_rows[0]
    combo_editor.set_combo("ctrl+alt+num6")
    enabled_checkbox.setChecked(False)
    window.accept()

    saved = next(h for h in settings.get_hotkeys() if h["action"] == action)
    assert saved["combo"] == "ctrl+alt+num6"
    assert saved["enabled"] is False


def test_accept_with_invalid_combo_shows_error_and_does_not_save(qapp, settings):
    window = SettingsWindow(settings)

    action, combo_editor, _ = window._hotkey_rows[0]
    original_combo = settings.get_hotkeys()[0]["combo"]
    combo_editor.combo = lambda: "ctrl+banana"
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


def test_settings_window_has_app_icon(qapp, settings):
    window = SettingsWindow(settings)

    assert not window.windowIcon().isNull()


def test_about_tab_shows_logo(qapp, settings):
    from PySide6.QtWidgets import QLabel

    window = SettingsWindow(settings)
    about_tab = window._build_about_tab()
    pixmap_labels = [child for child in about_tab.findChildren(QLabel) if not child.pixmap().isNull()]

    assert pixmap_labels
