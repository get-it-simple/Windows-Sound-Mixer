import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget

from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.entry_widget import BASE_ICON_PX as ENTRY_BASE_ICON_PX
from sound_mixer.overlay.mini_widget import BASE_APP_ICON_PX, BASE_SPACING_PX, MiniWidget
from sound_mixer.overlay.window import BASE_ICON_PX, OverlayWindow
from sound_mixer.settings_window.window import SettingsWindow


@pytest.fixture
def windows(qapp, fake_backend, settings):
    settings.set_ui_scale(3.0)
    settings.set_mini_widget_scale(3.0)
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    mini = MiniWidget(model, settings)
    mini.set_enabled(True)
    dialog = SettingsWindow(settings, overlay=overlay, mini_widget=mini)
    yield overlay, mini, dialog
    dialog.close()
    mini.stop()
    mini.close()
    overlay.close()
    for window in (dialog, mini, overlay):
        window.deleteLater()
        qapp.sendPostedEvents(window, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("ratio,maximum", [(1.0, 300), (1.25, 240), (1.75, 171), (2.0, 150), (3.5, 85)])
@pytest.mark.parametrize("layout", ["horizontal", "vertical"])
def test_saved_scale_is_limited_on_startup(qapp, fake_backend, settings, monkeypatch, ratio, maximum, layout):
    monkeypatch.setattr(QWidget, "devicePixelRatioF", lambda self: ratio)
    settings.set_ui_scale(3.0)
    settings.set_mini_widget_scale(3.0)
    settings.set_layout_mode(layout)
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings)
    mini = MiniWidget(model, settings)
    mini.set_enabled(True)
    dialog = SettingsWindow(settings, overlay=overlay, mini_widget=mini)
    try:
        scale = maximum / 100
        assert overlay._close_button.iconSize().width() == round(BASE_ICON_PX * scale)
        assert all(entry._mute_button.iconSize().width() == round(ENTRY_BASE_ICON_PX * scale)
                   for entry in overlay._entry_widgets)
        assert all(entry._icon_container.width() == round(BASE_APP_ICON_PX * scale)
                   for entry in mini._entries.values())
        assert mini._grid.horizontalSpacing() == round(BASE_SPACING_PX * scale)
        for slider, label in ((dialog._ui_scale_slider, dialog._ui_scale_label),
                              (dialog._mini_widget_scale_slider, dialog._mini_widget_scale_label)):
            assert slider.maximum() == maximum
            assert slider.value() == maximum
            assert label.text() == f"{maximum}%"
        assert settings.get_ui_scale() == 3.0
        assert settings.get_mini_widget_scale() == 3.0
    finally:
        dialog.close()
        mini.stop()
        mini.close()
        overlay.close()
        for window in (dialog, mini, overlay):
            window.deleteLater()
            qapp.sendPostedEvents(window, QEvent.Type.DeferredDelete)


def test_dpi_changes_update_each_window_and_restore_saved_scale(qapp, windows, monkeypatch, settings):
    overlay, mini, dialog = windows
    for window, ratio in ((overlay, 2.0), (mini, 3.0)):
        monkeypatch.setattr(window, "devicePixelRatioF", lambda ratio=ratio: ratio)
        qapp.sendEvent(window, QEvent(QEvent.Type.DevicePixelRatioChange))
    qapp.processEvents()

    assert overlay._close_button.iconSize().width() == round(BASE_ICON_PX * 1.5)
    assert all(entry._icon_container.width() == BASE_APP_ICON_PX for entry in mini._entries.values())
    assert dialog._ui_scale_slider.maximum() == 150
    assert dialog._ui_scale_label.text() == "150%"
    assert dialog._mini_widget_scale_slider.maximum() == 100
    assert dialog._mini_widget_scale_label.text() == "100%"
    assert settings.get_ui_scale() == settings.get_mini_widget_scale() == 3.0

    for window in (overlay, mini):
        monkeypatch.setattr(window, "devicePixelRatioF", lambda: 1.0)
        qapp.sendEvent(window, QEvent(QEvent.Type.DevicePixelRatioChange))
    qapp.processEvents()

    assert overlay._close_button.iconSize().width() == BASE_ICON_PX * 3
    assert all(entry._icon_container.width() == BASE_APP_ICON_PX * 3 for entry in mini._entries.values())
    assert dialog._ui_scale_slider.value() == dialog._mini_widget_scale_slider.value() == 300


def test_new_sessions_and_ignored_entries_use_limited_scale(qapp, windows, fake_backend, monkeypatch):
    overlay, mini, dialog = windows
    for window in (overlay, mini):
        monkeypatch.setattr(window, "devicePixelRatioF", lambda: 2.0)
        qapp.sendEvent(window, QEvent(QEvent.Type.DevicePixelRatioChange))
    qapp.processEvents()
    fake_backend.add_session(FakeAudioSession(pid=300, process_name="nimbus.exe", display_name="Nimbus"))
    overlay._model.refresh()
    overlay.refresh_view()
    mini.refresh_view()

    assert overlay._entry_widgets[-1]._mute_button.iconSize().width() == round(ENTRY_BASE_ICON_PX * 1.5)
    assert mini._entries["nimbus.exe"]._icon_container.width() == round(BASE_APP_ICON_PX * 1.5)
    overlay._model.ignore_app("nimbus.exe")
    overlay.refresh_view()
    assert overlay._ignored_widgets[-1]._mute_button.iconSize().width() == round(ENTRY_BASE_ICON_PX * 1.5)


def test_slider_cannot_exceed_display_limit(qapp, windows, settings, monkeypatch):
    overlay, mini, dialog = windows
    for window in (overlay, mini):
        monkeypatch.setattr(window, "devicePixelRatioF", lambda: 2.0)
        qapp.sendEvent(window, QEvent(QEvent.Type.DevicePixelRatioChange))
    qapp.processEvents()
    for slider in (dialog._ui_scale_slider, dialog._mini_widget_scale_slider):
        slider.setValue(100)
        slider.setValue(300)

    assert settings.get_ui_scale() == settings.get_mini_widget_scale() == 1.5
    assert overlay._close_button.iconSize().width() == round(BASE_ICON_PX * 1.5)
    assert all(entry._icon_container.width() == round(BASE_APP_ICON_PX * 1.5)
               for entry in mini._entries.values())


def test_smaller_preferences_are_preserved_on_high_dpi(qapp, windows, settings, monkeypatch):
    overlay, mini, dialog = windows
    dialog._ui_scale_slider.setValue(50)
    dialog._mini_widget_scale_slider.setValue(75)
    for window in (overlay, mini):
        monkeypatch.setattr(window, "devicePixelRatioF", lambda: 3.5)
        qapp.sendEvent(window, QEvent(QEvent.Type.DevicePixelRatioChange))
    qapp.processEvents()

    assert settings.get_ui_scale() == 0.5
    assert settings.get_mini_widget_scale() == 0.75
    assert dialog._ui_scale_slider.value() == 50
    assert dialog._mini_widget_scale_slider.value() == 75
    assert overlay._close_button.iconSize().width() == round(BASE_ICON_PX * 0.5)
    assert all(entry._icon_container.width() == round(BASE_APP_ICON_PX * 0.75)
               for entry in mini._entries.values())
