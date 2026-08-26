from sound_mixer.hotkeys import manager as manager_module
from sound_mixer.hotkeys.binding import combo_to_hotkey
from sound_mixer.hotkeys.manager import HotkeyManager


class FakeUser32:
    def __init__(self) -> None:
        self.registered: dict[int, tuple[int, int]] = {}

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, vk) -> bool:
        self.registered[hotkey_id] = (modifiers, vk)
        return True

    def UnregisterHotKey(self, hwnd, hotkey_id) -> bool:
        del self.registered[hotkey_id]
        return True


def test_start_registers_enabled_hotkeys(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake_user32)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    assert len(fake_user32.registered) == 1
    assert next(iter(fake_user32.registered.values())) == combo_to_hotkey("ctrl+alt+num5")


def test_triggering_hotkey_emits_signal(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake_user32)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    received = []
    hotkey_manager.toggle_overlay.connect(lambda: received.append(True))

    hotkey_id = next(iter(fake_user32.registered))
    hotkey_manager._handle_hotkey(hotkey_id)

    assert received == [True]


def test_stop_unregisters_hotkeys(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake_user32)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()
    hotkey_manager.stop()

    assert fake_user32.registered == {}


def test_reload_replaces_hotkeys(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake_user32)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    settings.set_hotkey("volume_up", "ctrl+up", enabled=True)
    hotkey_manager.reload()

    registered = set(fake_user32.registered.values())
    assert combo_to_hotkey("ctrl+alt+num5") in registered
    assert combo_to_hotkey("ctrl+up") in registered
    assert len(registered) == 2


def test_disabled_hotkey_is_not_registered(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake_user32)

    settings.set_hotkey("toggle_overlay", "ctrl+alt+num5", enabled=False)
    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    assert fake_user32.registered == {}


def test_mini_widget_hotkey_registers_and_emits(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake_user32)
    settings.set_hotkey("toggle_overlay", "ctrl+alt+num5", enabled=False)
    settings.set_hotkey("toggle_mini_widget", "ctrl+alt+num6", enabled=True)
    hotkey_manager = HotkeyManager(settings)
    received = []
    hotkey_manager.toggle_mini_widget.connect(lambda: received.append(True))

    hotkey_manager.start()
    hotkey_manager._handle_hotkey(next(iter(fake_user32.registered)))

    assert received == [True]


def test_failed_registration_is_not_tracked(qapp, settings, monkeypatch):
    fake_user32 = FakeUser32()
    fake_user32.RegisterHotKey = lambda hwnd, hotkey_id, modifiers, vk: False
    monkeypatch.setattr(manager_module, "user32", fake_user32)

    hotkey_manager = HotkeyManager(settings)
    hotkey_manager.start()

    assert hotkey_manager._hotkey_ids == {}

