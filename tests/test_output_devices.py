import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
from PySide6.QtCore import QAbstractAnimation, QEvent, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtTest import QTest

from sound_mixer.audio import master_listener, output_devices
from sound_mixer import app as app_module
from sound_mixer.audio.events import SessionEvent
from sound_mixer.mixer import session_sync as session_sync_module
from sound_mixer.audio.master_listener import MasterAudioListener
from sound_mixer.audio.output_devices import OutputDevice
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.window import OverlayWindow
from sound_mixer.overlay import window as window_module
from tests.test_master_audio import Devices
from tests.test_process_exit_listener import wait_until
from tests.test_session_sync import Listener as SessionListener


@pytest.fixture
def outputs(qapp, monkeypatch):
    devices = Devices()
    devices.first.FriendlyName = "Speakers"
    devices.second.FriendlyName = "Headphones with a very long device name"
    devices.active = [devices.first, devices.second]
    devices.scans = []
    devices.switches = []

    def enumerate_outputs(**filters):
        devices.scans.append((filters, threading.get_ident()))
        return list(devices.active)

    def select_output(device_id, roles):
        devices.switches.append((device_id, roles, threading.get_ident()))
        devices.switch(next(device for device in devices.active if device.id == device_id))

    monkeypatch.setattr(output_devices.AudioUtilities, "GetAllDevices", enumerate_outputs)
    monkeypatch.setattr(output_devices.AudioUtilities, "GetSpeakers", devices.GetSpeakers)
    monkeypatch.setattr(output_devices.AudioUtilities, "GetDeviceEnumerator", lambda: devices)
    monkeypatch.setattr(output_devices.AudioUtilities, "SetDefaultDevice", select_output)
    listener = MasterAudioListener(monitor_outputs=True)
    yield devices, listener
    listener.stop()
    listener.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_output_snapshot_filters_active_playback_devices(outputs):
    devices, _ = outputs
    snapshot, current = output_devices.read_output_devices()
    assert snapshot == [OutputDevice(device.id, device.FriendlyName) for device in devices.active]
    assert current == "speakers"
    assert devices.scans[0][0] == {
        "data_flow": EDataFlow.eRender.value,
        "device_state": DEVICE_STATE.ACTIVE.value,
    }


@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("preset_enabled", [False, True])
def test_app_output_switch_preserves_profiles_and_session_sync(
    qapp, outputs, fake_backend, settings, monkeypatch, visible, preset_enabled,
):
    devices, listener = outputs
    preset = settings.create_preset("Output profile", 0.6)
    if preset_enabled:
        settings.set_active_preset_id(preset["id"])
    session_listener = SessionListener()
    process_listener = SessionListener()
    monkeypatch.setattr(app_module, "QApplication", lambda argv: qapp)
    monkeypatch.setattr(app_module, "default_settings_path", lambda: settings.path)
    monkeypatch.setattr(app_module, "create_backend", lambda: fake_backend)
    monkeypatch.setattr(app_module, "InstanceController", Mock())
    monkeypatch.setattr(app_module, "HotkeyManager", Mock())
    monkeypatch.setattr(app_module, "AutostartManager", Mock())
    monkeypatch.setattr(app_module, "TrayIcon", Mock())
    monkeypatch.setattr(app_module, "MasterAudioListener", lambda *args, **kwargs: listener)
    monkeypatch.setattr(session_sync_module, "AudioSessionListener", lambda parent: session_listener)
    monkeypatch.setattr(session_sync_module, "ProcessExitListener", lambda parent: process_listener)
    app = app_module.SoundMixerApp()
    try:
        app.overlay._finish_warm_up()
        app.overlay.setVisible(visible)
        button = app.overlay._device_button
        wait_until(lambda: len(button.menu.actions()) == 2 and session_listener.rescans > 0)
        expected_volume = 0.6 if preset_enabled else 0.17
        fake_backend.set_master_volume(0.17)
        generation = session_listener.generation
        button.menu.actions()[1].trigger()
        wait_until(lambda: button.isEnabled() and session_listener.generation > generation)
        assert devices.current.id == "headphones"
        assert button._label.text() == devices.second.FriendlyName
        assert fake_backend.get_master_volume() == expected_volume
        assert app.model.active_preset_id == (preset["id"] if preset_enabled else None)
        assert app.overlay._preset_indicator.isHidden() == (not preset_enabled)

        session = fake_backend.enumerate_sessions()[0]
        session_listener.event_received.emit(SessionEvent.volume_changed(
            session_listener.generation, session.instance_id, 0.37, True,
        ))
        wait_until(lambda: app.model.entries[1].volume == 0.37)
        assert session.volume == 0.37 and session.muted
        assert app.settings.get_profile_app_state(session.key) == (0.37, True)
        app.overlay.show()
        assert app.overlay._entry_widgets[1]._slider.value() == 37
    finally:
        app.master_sync.stop()
        app.session_sync.stop()
        app.subprocess_manager.stop()
        app.mini_widget.stop()
        app.mini_widget.close()
        app.overlay.close()
        app.settings.flush()
        app.master_sync.deleteLater()
        app.session_sync.deleteLater()
        app.subprocess_manager.deleteLater()
        app.mini_widget.deleteLater()
        app.overlay.deleteLater()


def test_output_list_updates_on_events_without_rebinding_current_endpoint(outputs):
    devices, listener = outputs
    snapshots, master_changes = [], []
    listener.output_devices_changed.connect(lambda *value: snapshots.append(value))
    listener.device_changed.connect(lambda: master_changes.append(True))
    listener.start()
    wait_until(lambda: snapshots and master_changes)
    assert snapshots[-1][1] == "speakers"
    assert len(snapshots[-1][0]) == 2
    QTest.qWait(80)
    assert len(devices.scans) == 1

    devices.active.pop()
    devices.callback.OnDeviceRemoved("headphones")
    wait_until(lambda: len(snapshots) == 2)
    assert snapshots[-1][0] == [OutputDevice("speakers", "Speakers")]
    assert len(master_changes) == 1
    devices.first.FriendlyName = "Renamed speakers"
    devices.callback.OnPropertyValueChanged("speakers", SimpleNamespace(
        fmtid="{A45C254E-DF1C-4EFD-8020-67D146A850E0}", pid=14,
    ))
    wait_until(lambda: len(snapshots) == 3)
    assert snapshots[-1][0][0].name == "Renamed speakers"
    assert len(master_changes) == 1
    assert len(devices.first.EndpointVolume.history) == 1
    assert all(thread_id != threading.get_ident() for _, thread_id in devices.scans)

    devices.active.append(devices.second)
    devices.callback.OnDeviceAdded("headphones")
    wait_until(lambda: len(snapshots) == 4)
    assert len(snapshots[-1][0]) == 2


def test_selection_uses_system_events_and_existing_master_rebind(outputs):
    devices, listener = outputs
    snapshots, states = [], []
    listener.output_devices_changed.connect(lambda *value: snapshots.append(value))
    listener.state_changed.connect(lambda *value: states.append(value))
    listener.start()
    wait_until(lambda: snapshots and states)
    listener.select_output("headphones")
    wait_until(lambda: snapshots[-1][1] == "headphones" and states[-1] == (0.75, True))
    device_id, roles, thread_id = devices.switches[0]
    assert device_id == "headphones"
    assert roles == [ERole.eConsole, ERole.eMultimedia]
    assert thread_id != threading.get_ident()
    assert not devices.first.EndpointVolume.callbacks
    assert len(devices.second.EndpointVolume.callbacks) == 1


def test_selection_is_not_delayed_by_unrelated_windows_property_events(outputs, monkeypatch):
    devices, listener = outputs
    snapshots = []
    listener.output_devices_changed.connect(lambda *value: snapshots.append(value))
    listener.start()
    wait_until(lambda: snapshots)
    enumerate_outputs = output_devices.AudioUtilities.GetAllDevices

    def slow_enumeration(**filters):
        time.sleep(0.05)
        return enumerate_outputs(**filters)

    monkeypatch.setattr(output_devices.AudioUtilities, "GetAllDevices", slow_enumeration)
    for _ in range(165):
        devices.callback.OnPropertyValueChanged("speakers", SimpleNamespace(
            fmtid="{F112024A-FE30-42A8-80AB-8DD825A06F78}", pid=14,
        ))
    listener.select_output("headphones")
    wait_until(lambda: snapshots[-1][1] == "headphones")
    assert len(devices.switches) == 1
    assert len(devices.scans) == 2


@pytest.mark.parametrize("property_id", [2, 14])
def test_device_name_properties_refresh_names_without_rebinding(outputs, property_id):
    devices, listener = outputs
    snapshots, master_changes = [], []
    listener.output_devices_changed.connect(lambda *value: snapshots.append(value))
    listener.device_changed.connect(lambda: master_changes.append(True))
    listener.start()
    wait_until(lambda: snapshots and master_changes)
    devices.first.FriendlyName = "Updated output name"
    devices.callback.OnPropertyValueChanged("speakers", SimpleNamespace(
        fmtid="{a45c254e-df1c-4efd-8020-67d146a850e0}", pid=property_id,
    ))
    wait_until(lambda: snapshots[-1][0][0].name == "Updated output name")
    assert len(devices.scans) == 2
    assert len(master_changes) == 1


def test_missing_outputs_do_not_add_periodic_device_scans(outputs, monkeypatch):
    devices, listener = outputs
    monkeypatch.setattr(master_listener, "RETRY_INTERVAL_S", 0.02)
    devices.current = None
    devices.active = []
    snapshots = []
    listener.output_devices_changed.connect(lambda *value: snapshots.append(value))
    listener.start()
    wait_until(lambda: snapshots)
    QTest.qWait(100)
    assert snapshots == [([], "")]
    assert len(devices.scans) == 1
    devices.active = [devices.second]
    devices.switch(devices.second)
    wait_until(lambda: snapshots[-1][1] == "headphones")


@pytest.mark.parametrize("failure", ["removed", "system"])
def test_failed_selection_reports_error_and_keeps_current_device(outputs, monkeypatch, failure):
    devices, listener = outputs
    snapshots, errors = [], []
    listener.output_devices_changed.connect(lambda *value: snapshots.append(value))
    listener.output_selection_failed.connect(lambda: errors.append(True))
    listener.start()
    wait_until(lambda: snapshots)

    def fail(*args, **kwargs):
        raise OSError("Output unavailable")

    monkeypatch.setattr(output_devices.AudioUtilities, "SetDefaultDevice", fail)
    listener.select_output("missing" if failure == "removed" else "headphones")
    wait_until(lambda: errors)
    assert devices.current.id == "speakers"
    assert snapshots[-1][1] == "speakers"
    listener.stop()
    count = len(snapshots)
    QTest.qWait(30)
    assert len(snapshots) == count


@pytest.fixture
def overlay(qapp, fake_backend, settings):
    window = OverlayWindow(MixerModel(fake_backend, settings), settings)
    window._finish_warm_up()
    window.set_output_devices([
        OutputDevice("speakers", "Speakers & monitor with a very long name"),
        OutputDevice("headphones", "Headphones"),
    ], "speakers")
    window.show()
    qapp.processEvents()
    yield window
    window.close()
    window.deleteLater()


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_device_button_adapts_to_layout_and_available_width(qapp, overlay, scale):
    overlay._settings.set_ui_scale(scale)
    overlay.apply_scale()
    overlay.resize(1500, overlay.height())
    qapp.processEvents()
    button = overlay._device_button
    assert button._label.isVisible()
    preview = button._label.text()[:15] + "…"
    assert button.width() <= button._label.fontMetrics().horizontalAdvance(preview) + round(26 * scale)
    assert button.geometry().right() < overlay._settings_button.geometry().left()

    overlay.resize(200, overlay.height())
    qapp.processEvents()
    assert not button._label.isVisible()
    assert button.width() == round(40 * scale)
    assert button.geometry().right() < overlay._settings_button.geometry().left()
    assert overlay._close_button.geometry().right() < overlay._title_bar.width()

    overlay.resize(1500, overlay.height())
    qapp.processEvents()
    assert button._label.isVisible()
    overlay.set_layout_mode("vertical")
    qapp.processEvents()
    assert not button._label.isVisible()
    assert abs(button.geometry().center().x() - overlay._title_bar.rect().center().x()) <= 1
    overlay.set_layout_mode("horizontal")
    overlay.resize(1500, overlay.height())
    qapp.processEvents()
    assert button._label.isVisible()


@pytest.mark.parametrize("scale", [0.75, 1.0, 1.25, 1.5, 2.0, 3.0])
def test_vertical_device_button_matches_title_actions(qapp, overlay, scale):
    overlay.set_layout_mode("vertical")
    overlay._settings.set_ui_scale(scale)
    overlay.apply_scale()
    qapp.processEvents()
    button = overlay._device_button
    for peer in (overlay._settings_button, overlay._guide_button, overlay._close_button):
        assert button.size() == peer.size()
        assert button.geometry().center().x() == peer.geometry().center().x()
    assert button.geometry().bottom() < overlay._settings_button.geometry().top()
    original_size = button.size()
    button.menu.actions()[1].trigger()
    qapp.processEvents()
    assert button.size() == original_size
    overlay.set_output_devices(button._devices, "headphones")
    qapp.processEvents()
    assert button.size() == original_size


def test_device_name_scrolls_on_hover_and_resets_on_leave(qapp, overlay):
    overlay.resize(1000, overlay.height())
    qapp.processEvents()
    button = overlay._device_button
    button.enterEvent(QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    assert button._label._group.state() == QAbstractAnimation.State.Running
    button.leaveEvent(QEvent(QEvent.Type.Leave))
    assert button._label._group.state() == QAbstractAnimation.State.Stopped
    assert button._label.xOffset == 0


@pytest.mark.parametrize("scale", [0.75, 1.0, 1.5, 2.0])
@pytest.mark.parametrize("state", ["normal", "hover", "pressed", "menu"])
def test_device_name_has_transparent_background(qapp, overlay, scale, state):
    overlay._settings.set_ui_scale(scale)
    overlay.apply_scale()
    overlay.resize(1500, overlay.height())
    qapp.processEvents()
    button = overlay._device_button
    assert button._label.isVisible()
    if state != "normal":
        button.enterEvent(QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    if state == "pressed":
        button.setDown(True)
    if state == "menu":
        button.click()
        assert button.menu.isVisible()
    qapp.processEvents()
    try:
        image = button._label.grab().toImage()
        assert all(image.pixelColor(x, y).alpha() == 0
                   for x in range(image.width()) for y in (0, image.height() - 1))
        assert any(image.pixelColor(x, y).alpha() > 0
                   for x in range(image.width()) for y in range(1, image.height() - 1))
    finally:
        button.menu.hide()
        button.setDown(False)


def test_device_menu_uses_ids_and_waits_for_confirmed_system_selection(overlay):
    button = overlay._device_button
    selected = []
    overlay.output_device_selected.connect(selected.append)
    actions = button.menu.actions()
    assert [action.data() for action in actions] == ["speakers", "headphones"]
    assert [action.isChecked() for action in actions] == [True, False]
    assert actions[0].text().startswith("Speakers && monitor")
    actions[1].trigger()
    assert selected == ["headphones"]
    assert [action.isChecked() for action in button.menu.actions()] == [True, False]
    overlay.set_output_devices([OutputDevice("headphones", "Headphones")], "headphones")
    assert button._label.text() == "Headphones"
    assert len(button.menu.actions()) == 1
    assert button.menu.actions()[0].isChecked()
    overlay.set_output_devices([], "")
    assert not button.menu.actions()[0].isEnabled()


@pytest.mark.parametrize("mode", ["horizontal", "vertical"])
def test_selection_shows_animated_waiting_and_blocks_repeated_choices(qapp, overlay, mode):
    overlay.set_layout_mode(mode)
    if mode == "horizontal":
        overlay.resize(1000, overlay.height())
    qapp.processEvents()
    button = overlay._device_button
    selected = []
    overlay.output_device_selected.connect(selected.append)
    button.menu.actions()[1].trigger()
    assert selected == ["headphones"]
    assert not button.isEnabled()
    assert not button.menu.isEnabled()
    assert not button._label.isVisible()
    assert button._busy_animation.state() == QAbstractAnimation.State.Running
    button._busy_animation.setCurrentTime(250)
    first_frame = button.grab().toImage()
    button._busy_animation.setCurrentTime(650)
    assert first_frame != button.grab().toImage()
    button.click()
    button._show_menu()
    overlay._on_output_selected(button.menu.actions()[0])
    assert not button.menu.isVisible()
    assert selected == ["headphones"]

    overlay.set_output_devices(button._devices, "speakers")
    assert not button.isEnabled()
    overlay.set_output_devices(button._devices, "headphones")
    assert button.isEnabled()
    assert button.menu.isEnabled()
    assert button._busy_animation.state() == QAbstractAnimation.State.Stopped
    assert button._label.text() == "Headphones"
    assert button._label.isVisible() == (mode == "horizontal")
    button.menu.actions()[0].trigger()
    assert selected == ["headphones", "speakers"]


def test_selection_error_restores_button_and_allows_retry(overlay, monkeypatch):
    errors = []
    monkeypatch.setattr(window_module.QMessageBox, "warning", lambda *args: errors.append(args))
    button = overlay._device_button
    selected = []
    overlay.output_device_selected.connect(selected.append)
    button.menu.actions()[1].trigger()
    overlay.show_output_selection_error()
    assert len(errors) == 1
    assert button.isEnabled()
    assert button.menu.isEnabled()
    assert button._busy_animation.state() == QAbstractAnimation.State.Stopped
    assert button._label.text().startswith("Speakers")
    button.menu.actions()[1].trigger()
    assert selected == ["headphones", "headphones"]


def test_current_device_selection_does_not_wait_for_a_nonexistent_change(overlay):
    selected = []
    overlay.output_device_selected.connect(selected.append)
    button = overlay._device_button
    button.menu.actions()[0].trigger()
    assert selected == []
    assert button.isEnabled()
    assert button._busy_animation.state() == QAbstractAnimation.State.Stopped


def test_removed_target_ends_waiting_and_updates_available_choices(overlay):
    button = overlay._device_button
    button.menu.actions()[1].trigger()
    overlay.set_output_devices([OutputDevice("speakers", "Speakers")], "speakers")
    assert button.isEnabled()
    assert button._busy_animation.state() == QAbstractAnimation.State.Stopped
    assert [action.data() for action in button.menu.actions()] == ["speakers"]


def test_hidden_widget_keeps_selection_locked_and_resumes_animation(qapp, overlay):
    button = overlay._device_button
    button.menu.actions()[1].trigger()
    overlay.hide()
    assert button._busy_animation.state() == QAbstractAnimation.State.Stopped
    assert not button.isEnabled()
    overlay.show()
    qapp.processEvents()
    assert button._busy_animation.state() == QAbstractAnimation.State.Running
    assert not button.isEnabled()
    overlay.set_layout_mode("vertical")
    overlay.set_layout_mode("horizontal")
    assert not button._label.isVisible()
    overlay.hide()
    overlay.set_output_devices(button._devices, "headphones")
    overlay.show()
    qapp.processEvents()
    assert button.isEnabled()
    assert button._busy_animation.state() == QAbstractAnimation.State.Stopped


@pytest.mark.parametrize("rename", [False, True])
def test_device_menu_click_survives_system_update_between_press_and_release(qapp, overlay, rename):
    button = overlay._device_button
    selected = []
    overlay.output_device_selected.connect(selected.append)
    button.click()
    qapp.processEvents()
    menu = button.menu
    assert menu.isVisible()
    target = menu.actions()[1]
    position = menu.actionGeometry(target).center()
    global_position = menu.mapToGlobal(position)
    qapp.sendEvent(menu, QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(position), QPointF(global_position),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    ))
    assert menu.activeAction() is target
    overlay.set_output_devices([
        OutputDevice("speakers", "Speakers & monitor with a very long name"),
        OutputDevice("headphones", "Headphones renamed" if rename else "Headphones"),
    ], "speakers")
    qapp.processEvents()
    assert menu.activeAction() is target
    assert menu.actionGeometry(target).contains(position)
    qapp.sendEvent(menu, QMouseEvent(
        QEvent.Type.MouseButtonRelease, QPointF(position), QPointF(global_position),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
    ))
    qapp.processEvents()
    assert selected == ["headphones"]
    assert not menu.isVisible()
