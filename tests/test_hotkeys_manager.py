from sound_mixer.hotkeys import manager as manager_module
from sound_mixer.hotkeys.manager import HotkeyManager


class FakeKeyboard:
    def __init__(self) -> None:
        self.hotkeys: dict[str, object] = {}

    def add_hotkey(self, combo, callback) -> None:
        self.hotkeys[combo] = callback

    def remove_hotkey(self, combo) -> None:
        del self.hotkeys[combo]


def test_start_registers_enabled_hotkeys(qapp, settings, monkeypatch):
    fake_keyboard = FakeKeyboard()
    monkeypatch.setattr(manager_module, "keyboard", fake_keyboard)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    assert "ctrl+alt+num 5" in fake_keyboard.hotkeys
    assert len(fake_keyboard.hotkeys) == 1


def test_triggering_combo_emits_signal(qapp, settings, monkeypatch):
    fake_keyboard = FakeKeyboard()
    monkeypatch.setattr(manager_module, "keyboard", fake_keyboard)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    received = []
    hotkey_manager.toggle_overlay.connect(lambda: received.append(True))

    fake_keyboard.hotkeys["ctrl+alt+num 5"]()

    assert received == [True]


def test_stop_unregisters_hotkeys(qapp, settings, monkeypatch):
    fake_keyboard = FakeKeyboard()
    monkeypatch.setattr(manager_module, "keyboard", fake_keyboard)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()
    hotkey_manager.stop()

    assert fake_keyboard.hotkeys == {}


def test_reload_replaces_hotkeys(qapp, settings, monkeypatch):
    fake_keyboard = FakeKeyboard()
    monkeypatch.setattr(manager_module, "keyboard", fake_keyboard)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    settings.set_hotkey("volume_up", "ctrl+up", enabled=True)
    hotkey_manager.reload()

    assert "ctrl+alt+num 5" in fake_keyboard.hotkeys
    assert "ctrl+up" in fake_keyboard.hotkeys


def test_disabled_hotkey_is_not_registered(qapp, settings, monkeypatch):
    fake_keyboard = FakeKeyboard()
    monkeypatch.setattr(manager_module, "keyboard", fake_keyboard)

    settings.set_hotkey("toggle_overlay", "ctrl+alt+num5", enabled=False)
    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    assert fake_keyboard.hotkeys == {}
