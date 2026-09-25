import sys

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sound_mixer.i18n import t
from sound_mixer.mixer.model import MixerModel
from sound_mixer.mixer.subprocess_manager import SubprocessManager
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.settings.store import SettingsStore


@pytest.mark.parametrize("layout", ["horizontal", "vertical"])
@pytest.mark.parametrize("monitoring", [False, True])
@pytest.mark.parametrize("scale", [0.5, 1.0, 1.5, 2.0, 3.0])
def test_preset_indicator_switching_tooltip_and_layout(qapp, settings, fake_backend, layout, monitoring, scale):
    settings.set_layout_mode(layout)
    settings.set_ui_scale(scale)
    presets = [settings.create_preset(f"Profile {index}", .5) for index in range(1, 10)]
    if monitoring:
        settings.set_managed_apps([{"path": sys.executable, "enabled": True}])
    manager = SubprocessManager(settings, on_tick=lambda: None)
    model = MixerModel(fake_backend, settings)
    overlay = OverlayWindow(model, settings, subprocess_manager=manager)
    overlay._finish_warm_up()
    try:
        overlay.show()
        qapp.processEvents()
        indicator = overlay._preset_indicator
        assert indicator.isHidden()
        for index, preset in enumerate(presets, 1):
            model.activate_preset(preset["id"])
            overlay.refresh_view()
            qapp.processEvents()
            assert indicator.isVisible()
            assert indicator.text() == f"P{index}"
            assert indicator.toolTip() == preset["name"]
            assert overlay._title_name_label.text() == t("sound_mixer_title")
            assert preset["name"] not in overlay._title_icon_label.toolTip()
            assert overlay.windowTitle() == t("sound_mixer_title")
            assert not indicator.icon().isNull()
            for button in (overlay._settings_button, overlay._guide_button, overlay._close_button):
                assert indicator.iconSize() == button.iconSize()
                assert indicator.sizeHint() == button.sizeHint()
                assert indicator.height() == button.height()
                assert abs(indicator.width() - button.width()) <= 1
            neighbor = overlay._subprocess_management_toggle if monitoring else overlay._settings_button
            assert neighbor.isVisible()
            if layout == "vertical":
                assert indicator.geometry().bottom() < neighbor.geometry().top()
                assert abs(indicator.geometry().center().x() - neighbor.geometry().center().x()) <= 1
            else:
                assert indicator.geometry().right() < neighbor.geometry().left()
            assert overlay._title_bar.rect().contains(indicator.geometry())
            assert overlay._title_bar.rect().contains(overlay._close_button.geometry())
        presets[-1]["name"] = "Renamed profile"
        settings.set_presets(presets)
        overlay.retranslate()
        assert indicator.toolTip() == "Renamed profile"
        assert indicator.text() == "P9"
        settings.delete_preset(presets[0]["id"])
        overlay.refresh_view()
        assert indicator.text() == "P8"
        model.activate_preset(None)
        overlay.refresh_view()
        assert indicator.isHidden()
        assert indicator.toolTip() == ""
    finally:
        overlay.close()
        overlay.deleteLater()
        manager.stop()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("layout", ["horizontal", "vertical"])
@pytest.mark.parametrize("selection", [0, 1, 9])
def test_clicking_preset_indicator_selects_profile(qapp, settings, fake_backend, layout, selection):
    settings.set_layout_mode(layout)
    model = MixerModel(fake_backend, settings)
    normal_volume = fake_backend.get_master_volume()
    presets = [settings.create_preset(f"Profile {index}", index / 10) for index in range(1, 10)]
    model.activate_preset(presets[0]["id"])
    overlay = OverlayWindow(model, settings)
    overlay._finish_warm_up()
    try:
        overlay.show()
        qapp.processEvents()
        changes = []
        overlay.model_changed.connect(lambda: changes.append(model.active_preset_id))
        QTest.mouseClick(overlay._preset_indicator, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        menu = QApplication.activePopupWidget()
        assert menu is not None and menu.isVisible()
        actions = menu.actions()
        assert [action.text() for action in actions] == [t("default_mode"), *[f"P{i}" for i in range(1, 10)]]
        assert [action.isChecked() for action in actions] == [False, True, *[False] * 8]
        assert [action.toolTip() for action in actions[1:]] == [preset["name"] for preset in presets]
        assert menu.toolTipsVisible()
        QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(actions[selection]).center())
        qapp.processEvents()
        expected_id = presets[selection - 1]["id"] if selection else None
        assert not menu.isVisible()
        assert model.active_preset_id == expected_id
        assert changes == [expected_id]
        assert fake_backend.get_master_volume() == pytest.approx(selection / 10 if selection else normal_volume)
        assert overlay._preset_indicator.isHidden() == (selection == 0)
        if selection:
            assert overlay._preset_indicator.text() == f"P{selection}"
            QTest.mouseClick(overlay._preset_indicator, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert [action.isChecked() for action in menu.actions()] == [i == selection for i in range(10)]
            QTest.keyClick(menu, Qt.Key.Key_Escape)
            assert not menu.isVisible()
            assert model.active_preset_id == expected_id
            assert changes == [expected_id]
        saved = SettingsStore(settings.path)
        saved.load()
        assert saved.get_active_preset_id() == expected_id
    finally:
        overlay._preset_menu.close()
        overlay.close()
        overlay.deleteLater()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
