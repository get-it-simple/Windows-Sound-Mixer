import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.mini_widget import MiniWidget
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings_window.window import SettingsWindow


@pytest.mark.parametrize("main_visible,mini_visible", [(False, False), (True, False), (False, True), (True, True)])
def test_settings_are_topmost_without_changing_widget_visibility(qapp, fake_backend, settings, monkeypatch, main_visible, mini_visible):
    monkeypatch.setattr(OverlayWindow, "_warm_up_acrylic", lambda self: None)
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    mini = MiniWidget(model, settings)
    overlay.setVisible(main_visible)
    mini.set_enabled(mini_visible, persist=False)
    qapp.processEvents()
    main_flags, mini_flags = overlay.windowFlags(), mini.windowFlags()
    main_changes = QSignalSpy(overlay.visibility_changed)
    mini_changes = QSignalSpy(mini.visibility_changed)
    dialog = SettingsWindow(settings, overlay=overlay, mini_widget=mini, parent=overlay)
    try:
        dialog.show()
        qapp.processEvents()
        assert dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        assert dialog.parentWidget() is overlay
        assert overlay.isVisible() == main_visible and mini.isVisible() == mini_visible
        dialog.reject()
        qapp.processEvents()
        assert overlay.isVisible() == main_visible and mini.isVisible() == mini_visible
        assert overlay.windowFlags() == main_flags and mini.windowFlags() == mini_flags
        assert main_changes.count() == mini_changes.count() == 0
    finally:
        dialog.close()
        mini.close()
        overlay.close()
