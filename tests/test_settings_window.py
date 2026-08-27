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
    assert window._mini_widget_scale_slider.value() == round(settings.get_mini_widget_scale() * 100)

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
    window._mini_widget_checkbox.setChecked(True)
    window.accept()

    assert settings.get_autostart_enabled() is True
    assert settings.get_transparency_enabled() is False
    assert settings.get_tooltip_delay_ms() == 1000
    assert settings.get_arrow_step() == 0.1
    assert settings.get_scroll_step() == 0.04
    assert settings.get_default_app_volume() == 0.75
    assert settings.get_mini_widget_enabled() is True


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


def test_mini_widget_scale_slider_updates_only_mini_widget_immediately(qapp, fake_backend, settings):
    from sound_mixer.mixer.model import MixerModel
    from sound_mixer.overlay.entry_widget import BASE_FONT_PX as OVERLAY_BASE_FONT_PX
    from sound_mixer.overlay.mini_widget import BASE_FONT_PX as MINI_BASE_FONT_PX, MiniWidget

    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    mini = MiniWidget(model, settings)
    mini.set_enabled(True)
    window = SettingsWindow(settings, overlay=overlay, mini_widget=mini)

    window._mini_widget_scale_slider.setValue(150)

    assert settings.get_mini_widget_scale() == 1.5
    assert window._mini_widget_scale_label.text() == "150%"
    assert mini._entries["aurora.exe"]._volume_label.font().pixelSize() == round(MINI_BASE_FONT_PX * 1.5)
    assert overlay._entry_widgets[0]._volume_spinbox.font().pixelSize() == OVERLAY_BASE_FONT_PX

    window._ui_scale_slider.setValue(200)

    assert settings.get_ui_scale() == 2.0
    assert mini._entries["aurora.exe"]._volume_label.font().pixelSize() == round(MINI_BASE_FONT_PX * 1.5)
    mini.stop()
    mini.close()
    overlay.close()


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


def test_language_combo_present_and_shows_system_option(qapp, settings):
    from PySide6.QtWidgets import QComboBox

    window = SettingsWindow(settings)

    assert hasattr(window, "_language_combo")
    assert isinstance(window._language_combo, QComboBox)
    system_index = window._language_combo.findData("system")
    assert system_index >= 0


def test_language_combo_contains_all_available_languages(qapp, settings):
    from sound_mixer.i18n import AVAILABLE_LANGUAGES

    window = SettingsWindow(settings)

    for lang_code in AVAILABLE_LANGUAGES:
        assert window._language_combo.findData(lang_code) >= 0


def test_language_combo_reflects_saved_setting(qapp, settings):
    settings.set_language("uk")
    window = SettingsWindow(settings)

    assert window._language_combo.currentData() == "uk"


def test_subprocess_management_tab_builds_row_per_persisted_app(qapp, settings):
    settings.set_managed_apps([{"path": "C:/Games/sandbox.exe", "enabled": False}])
    window = SettingsWindow(settings)

    assert len(window._managed_app_rows) == 1
    row = window._managed_app_rows[0]
    assert row.path == "C:/Games/sandbox.exe"
    assert row.is_enabled() is False
    assert row._name_label.toolTip() == "C:/Games/sandbox.exe"


def test_subprocess_management_interval_spinbox_reflects_settings(qapp, settings):
    settings.set_subprocess_management_interval_seconds(15)
    window = SettingsWindow(settings)

    assert window._subprocess_interval_spinbox.value() == 15


def test_dropping_app_adds_row_with_resolved_name(qapp, settings):
    import sys

    window = SettingsWindow(settings)

    window._on_managed_app_dropped(sys.executable)

    assert len(window._managed_app_rows) == 1
    assert window._managed_app_rows[0].path == sys.executable
    assert window._managed_app_rows[0]._name_label.text()


def test_dropping_same_app_path_twice_does_not_duplicate(qapp, settings):
    window = SettingsWindow(settings)

    window._on_managed_app_dropped("C:/Games/Sandbox.exe")
    window._on_managed_app_dropped("c:/games/sandbox.exe")

    assert len(window._managed_app_rows) == 1


def test_removing_managed_app_row(qapp, settings):
    window = SettingsWindow(settings)
    window._on_managed_app_dropped("C:/Games/Sandbox.exe")
    row = window._managed_app_rows[0]

    row.remove_requested.emit()

    assert window._managed_app_rows == []


def test_accept_saves_subprocess_management_settings(qapp, settings):
    window = SettingsWindow(settings)
    window._subprocess_interval_spinbox.setValue(20)
    window._on_managed_app_dropped("C:/Games/Sandbox.exe")

    window.accept()

    assert settings.get_subprocess_management_interval_seconds() == 20
    assert settings.get_managed_apps() == [{"path": "C:/Games/Sandbox.exe", "enabled": True}]


def test_accept_syncs_subprocess_manager(qapp, settings):
    class FakeSubprocessManager:
        def __init__(self) -> None:
            self.synced = False

        def sync(self) -> None:
            self.synced = True

    subprocess_manager = FakeSubprocessManager()
    window = SettingsWindow(settings, subprocess_manager=subprocess_manager)

    window.accept()

    assert subprocess_manager.synced is True


def test_cancel_does_not_persist_subprocess_management_changes(qapp, settings):
    window = SettingsWindow(settings)
    window._subprocess_interval_spinbox.setValue(45)
    window._on_managed_app_dropped("C:/Games/Sandbox.exe")

    window.reject()

    assert settings.get_subprocess_management_interval_seconds() == 5
    assert settings.get_managed_apps() == []


def test_whitelist_tab_loads_and_saves_independent_app_list(qapp, settings):
    settings.set_managed_apps([{"path": "C:/Apps/Launcher.exe", "enabled": True}])
    settings.set_whitelist_apps([{"path": "C:/Apps/Aurora.exe", "enabled": False}])
    window = SettingsWindow(settings)

    assert len(window._managed_app_rows) == 1
    assert len(window._whitelist_app_rows) == 1
    assert window._whitelist_app_rows[0].path == "C:/Apps/Aurora.exe"
    window._whitelist_checkbox.setChecked(True)
    window._whitelist_editor.add_path("C:/Apps/Lumen.exe")
    window.accept()

    assert settings.get_whitelist_enabled() is True
    assert settings.get_whitelist_apps() == [
        {"path": "C:/Apps/Aurora.exe", "enabled": False},
        {"path": "C:/Apps/Lumen.exe", "enabled": True},
    ]
    assert settings.get_managed_apps() == [{"path": "C:/Apps/Launcher.exe", "enabled": True}]


def test_accept_saves_language(qapp, settings):
    window = SettingsWindow(settings)
    uk_index = window._language_combo.findData("uk")
    window._language_combo.setCurrentIndex(uk_index)

    window.accept()

    assert settings.get_language() == "uk"


def test_start_opened_checkbox_reflects_setting(qapp, settings):
    settings.set_visible_on_start(True)

    window = SettingsWindow(settings)

    assert window._start_opened_checkbox.isChecked() is True
    assert window._start_opened_checkbox.objectName() == "startOpenedToggle"
    assert "::indicator" in window._start_opened_checkbox.styleSheet()


def test_accept_saves_start_opened(qapp, settings):
    window = SettingsWindow(settings)

    window._start_opened_checkbox.setChecked(True)
    window.accept()

    assert settings.get_visible_on_start() is True


def test_layout_mode_combo_reflects_setting(qapp, settings):
    settings.set_layout_mode("vertical")

    window = SettingsWindow(settings)

    assert window._layout_mode_combo.currentData() == "vertical"


def test_accept_saves_layout_mode_without_overlay(qapp, settings):
    window = SettingsWindow(settings)

    window._layout_mode_combo.setCurrentIndex(window._layout_mode_combo.findData("vertical"))
    window.accept()

    assert settings.get_layout_mode() == "vertical"


def test_accept_applies_layout_mode_to_overlay(qapp, fake_backend, settings):
    from PySide6.QtCore import Qt

    from sound_mixer.mixer.model import MixerModel

    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    window = SettingsWindow(settings, overlay=overlay)

    window._layout_mode_combo.setCurrentIndex(window._layout_mode_combo.findData("vertical"))
    window.accept()

    assert settings.get_layout_mode() == "vertical"
    assert overlay.layout_mode() == "vertical"
    assert overlay._entry_widgets[0]._slider.orientation() == Qt.Orientation.Vertical


def test_cancel_does_not_change_layout_mode(qapp, settings):
    window = SettingsWindow(settings)

    window._layout_mode_combo.setCurrentIndex(window._layout_mode_combo.findData("vertical"))
    window.reject()

    assert settings.get_layout_mode() == "horizontal"
