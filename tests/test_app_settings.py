from sound_mixer import app as app_module
from sound_mixer.app import SoundMixerApp


class FakeHotkeys:
    def __init__(self) -> None:
        self.calls = []

    def stop(self) -> None:
        self.calls.append("stop")

    def start(self) -> None:
        self.calls.append("start")


class FakeSettings:
    def get_autostart_enabled(self) -> bool:
        return True


class FakeTray:
    def __init__(self) -> None:
        self.autostart_values = []

    def set_autostart_enabled(self, value: bool) -> None:
        self.autostart_values.append(value)


def make_app() -> SoundMixerApp:
    instance = SoundMixerApp.__new__(SoundMixerApp)
    instance.settings = FakeSettings()
    instance.autostart = object()
    instance.overlay = None
    instance.hotkeys = FakeHotkeys()
    instance.tray = FakeTray()
    return instance


def test_open_settings_stops_hotkeys_while_dialog_is_open(monkeypatch):
    events = []

    class FakeDialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, settings, autostart=None, hotkeys=None, overlay=None, parent=None) -> None:
            events.append(("created", list(hotkeys.calls)))
            self.hotkeys = hotkeys

        def exec(self) -> int:
            events.append(("exec", list(self.hotkeys.calls)))
            self.hotkeys.reload()
            return self.DialogCode.Accepted

    app = make_app()
    app.hotkeys.reload = lambda: app.hotkeys.calls.append("reload")
    monkeypatch.setattr(app_module, "SettingsWindow", FakeDialog)

    app._open_settings()

    assert events == [("created", ["stop"]), ("exec", ["stop"])]
    assert app.hotkeys.calls == ["stop", "reload"]
    assert app.tray.autostart_values == [True]


def test_open_settings_restarts_hotkeys_when_dialog_is_closed_without_saving(monkeypatch):
    class FakeDialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self) -> int:
            return 0

    app = make_app()
    monkeypatch.setattr(app_module, "SettingsWindow", FakeDialog)

    app._open_settings()

    assert app.hotkeys.calls == ["stop", "start"]
    assert app.tray.autostart_values == []
