import pytest

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from sound_mixer import i18n
from sound_mixer.i18n import t
from sound_mixer.overlay.guide import GuideDialog, _MarqueeLabel


def test_guide_dialog_opens(qapp):
    dialog = GuideDialog()
    dialog.show()

    assert dialog.isVisible()
    dialog.close()


@pytest.mark.parametrize("source", ["overlay", "settings"])
@pytest.mark.parametrize("main_visible,mini_visible", [(False, False), (True, False), (False, True), (True, True)])
def test_guide_priority_preserves_widgets(qapp, fake_backend, settings, monkeypatch, source, main_visible, mini_visible):
    from sound_mixer.mixer.model import MixerModel
    from sound_mixer.overlay.mini_widget import MiniWidget
    from sound_mixer.overlay.window import OverlayWindow
    from sound_mixer.settings_window.window import SettingsWindow

    monkeypatch.setattr(OverlayWindow, "_warm_up_acrylic", lambda self: None)
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    mini = MiniWidget(model, settings)
    overlay.setVisible(main_visible)
    mini.set_enabled(mini_visible, persist=False)
    window = overlay if source == "overlay" else SettingsWindow(settings, overlay=overlay, mini_widget=mini, parent=overlay)
    if source == "settings":
        window.show()
    qapp.processEvents()
    main_flags, mini_flags = overlay.windowFlags(), mini.windowFlags()
    main_changes = QSignalSpy(overlay.visibility_changed)
    mini_changes = QSignalSpy(mini.visibility_changed)
    shown = []

    def inspect_dialog():
        dialog = QApplication.activeModalWidget()
        try:
            shown.append((
                isinstance(dialog, GuideDialog),
                bool(dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                dialog.parentWidget() is window,
                dialog.isVisible(),
                overlay.isVisible(),
                mini.isVisible(),
            ))
        finally:
            dialog.reject()

    try:
        for _ in range(2):
            QTimer.singleShot(0, inspect_dialog)
            window._guide_button.click()
            qapp.processEvents()
            assert shown[-1] == (True, True, True, True, main_visible, mini_visible)
            assert overlay.isVisible() == main_visible and mini.isVisible() == mini_visible
            assert overlay.windowFlags() == main_flags and mini.windowFlags() == mini_flags
            assert main_changes.count() == mini_changes.count() == 0
    finally:
        window.close()
        mini.close()
        overlay.close()


def test_guide_dialog_has_window_icon(qapp):
    dialog = GuideDialog()

    assert not dialog.windowIcon().isNull()


@pytest.mark.parametrize("mini_widget_enabled", [False, True])
def test_guide_dialog_fits_screen_without_forced_scroll(qapp, mini_widget_enabled):
    dialog = GuideDialog(mini_widget_enabled=mini_widget_enabled)
    screen = QApplication.primaryScreen()
    available_height = screen.availableGeometry().height()

    assert dialog.height() <= round(available_height * 0.88)


def test_guide_dialog_has_mouse_section(qapp):
    dialog = GuideDialog()
    texts = [w.text().lower() for w in dialog.findChildren(QLabel)]

    assert any("scroll" in t for t in texts)


def test_guide_dialog_has_keyboard_section(qapp):
    dialog = GuideDialog()
    texts = [w.text().lower() for w in dialog.findChildren(QLabel)]

    assert any("arrow" in t or "up" in t for t in texts)


def test_guide_dialog_has_hotkeys_section(qapp):
    dialog = GuideDialog()
    texts = [w.text().lower() for w in dialog.findChildren(QLabel)]

    assert any("hotkey" in t or "settings" in t for t in texts)


def test_overlay_has_guide_button(qapp, fake_backend, settings):
    from sound_mixer.mixer.model import MixerModel
    from sound_mixer.overlay.window import OverlayWindow

    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)

    assert hasattr(overlay, "_guide_button")
    assert overlay._guide_button.toolTip() != ""
    assert not overlay._guide_button.icon().isNull()


def test_settings_has_guide_button(qapp, settings):
    from sound_mixer.settings_window.window import SettingsWindow

    window = SettingsWindow(settings)

    assert hasattr(window, "_guide_button")
    buttons = window.findChildren(QPushButton)
    assert any("guide" in b.text().lower() for b in buttons)


@pytest.mark.parametrize("mini_widget_enabled", [False, True])
def test_guide_mini_widget_controls_follow_enabled_state(qapp, mini_widget_enabled):
    previous_language = i18n.get_current_language()
    i18n.setup("en")
    try:
        dialog = GuideDialog(mini_widget_enabled=mini_widget_enabled)
        texts = [label.text() for label in dialog.findChildren(QLabel)]
        descriptions = [label.text() for label in dialog.findChildren(_MarqueeLabel)]

        assert (t("guide_section_mini_widget").upper() in texts) == mini_widget_enabled
        for action in ("scroll", "click", "hover", "drag", "dock", "undock"):
            assert (t(f"guide_mini_{action}") in texts) == mini_widget_enabled
            assert (t(f"guide_mini_{action}_desc") in descriptions) == mini_widget_enabled
        dialog.close()
    finally:
        i18n.setup(previous_language)


@pytest.mark.parametrize("source", ["overlay", "settings"])
def test_guide_buttons_use_current_mini_widget_state(qapp, fake_backend, settings, monkeypatch, source):
    from sound_mixer.mixer.model import MixerModel
    from sound_mixer.overlay.window import OverlayWindow
    from sound_mixer.settings_window.window import SettingsWindow

    if source == "overlay":
        window = OverlayWindow(MixerModel(fake_backend, settings), settings)
    else:
        window = SettingsWindow(settings)

    shown_sections = []

    def capture_dialog(dialog):
        shown_sections.append([label.text() for label in dialog.findChildren(QLabel)])
        return 0

    monkeypatch.setattr(GuideDialog, "exec", capture_dialog)
    for enabled in (False, True, False):
        settings.set_mini_widget_enabled(enabled)
        window._guide_button.click()

    assert len(shown_sections) == 3
    assert [t("guide_section_mini_widget").upper() in texts for texts in shown_sections] == [False, True, False]
    window.close()
