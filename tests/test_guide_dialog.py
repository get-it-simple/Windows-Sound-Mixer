import pytest

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from sound_mixer import i18n
from sound_mixer.i18n import t
from sound_mixer.overlay.guide import GuideDialog, _MarqueeLabel


def test_guide_dialog_opens(qapp):
    dialog = GuideDialog()
    dialog.show()

    assert dialog.isVisible()
    dialog.close()


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


@pytest.mark.parametrize("language", ["en", "uk"])
@pytest.mark.parametrize("mini_widget_enabled", [False, True])
def test_guide_mini_widget_controls_follow_enabled_state(qapp, language, mini_widget_enabled):
    previous_language = i18n.get_current_language()
    i18n.setup(language)
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
