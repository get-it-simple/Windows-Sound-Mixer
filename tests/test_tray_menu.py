from PySide6.QtWidgets import QSystemTrayIcon

from sound_mixer.tray.tray_icon import TrayIcon


class Stubs:
    def __init__(self) -> None:
        self.toggle_overlay_calls: list[bool] = []
        self.settings_calls = 0
        self.toggle_autostart_calls: list[bool] = []
        self.exit_calls = 0

    def on_toggle_overlay(self, checked: bool) -> None:
        self.toggle_overlay_calls.append(checked)

    def on_open_settings(self) -> None:
        self.settings_calls += 1

    def on_toggle_autostart(self, checked: bool) -> None:
        self.toggle_autostart_calls.append(checked)

    def on_exit(self) -> None:
        self.exit_calls += 1


def make_tray(qapp, **kwargs) -> tuple[TrayIcon, Stubs]:
    stubs = Stubs()
    tray = TrayIcon(
        on_toggle_overlay=stubs.on_toggle_overlay,
        on_open_settings=stubs.on_open_settings,
        on_toggle_autostart=stubs.on_toggle_autostart,
        on_exit=stubs.on_exit,
        **kwargs,
    )
    return tray, stubs


def test_initial_checkbox_state(qapp):
    tray, _ = make_tray(qapp, overlay_visible=True, autostart_enabled=False)

    assert tray.toggle_overlay_action.isChecked() is True
    assert tray.autostart_action.isChecked() is False


def test_toggle_overlay_action_triggers_callback(qapp):
    tray, stubs = make_tray(qapp, overlay_visible=False)

    tray.toggle_overlay_action.trigger()

    assert stubs.toggle_overlay_calls == [True]


def test_settings_action_triggers_callback(qapp):
    tray, stubs = make_tray(qapp)

    tray.settings_action.trigger()

    assert stubs.settings_calls == 1


def test_autostart_action_triggers_callback(qapp):
    tray, stubs = make_tray(qapp, autostart_enabled=False)

    tray.autostart_action.trigger()

    assert stubs.toggle_autostart_calls == [True]


def test_exit_action_triggers_callback(qapp):
    tray, stubs = make_tray(qapp)

    tray.exit_action.trigger()

    assert stubs.exit_calls == 1


def test_set_overlay_visible_does_not_trigger_callback(qapp):
    tray, stubs = make_tray(qapp, overlay_visible=False)

    tray.set_overlay_visible(True)

    assert tray.toggle_overlay_action.isChecked() is True
    assert stubs.toggle_overlay_calls == []


def test_set_autostart_enabled_does_not_trigger_callback(qapp):
    tray, stubs = make_tray(qapp, autostart_enabled=False)

    tray.set_autostart_enabled(True)

    assert tray.autostart_action.isChecked() is True
    assert stubs.toggle_autostart_calls == []


def test_left_click_triggers_overlay_toggle(qapp):
    tray, stubs = make_tray(qapp, overlay_visible=False)

    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)

    assert stubs.toggle_overlay_calls == [True]
