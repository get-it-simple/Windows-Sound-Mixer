from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from sound_mixer.overlay.guide import GuideDialog


def test_guide_dialog_opens(qapp):
    dialog = GuideDialog()
    dialog.show()

    assert dialog.isVisible()
    dialog.close()


def test_guide_dialog_has_window_icon(qapp):
    dialog = GuideDialog()

    assert not dialog.windowIcon().isNull()


def test_guide_dialog_fits_screen_without_forced_scroll(qapp):
    dialog = GuideDialog()
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
