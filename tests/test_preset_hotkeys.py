import pytest

from sound_mixer.hotkeys.binding import MOD_NOREPEAT, combo_to_hotkey, validate_bindings
from sound_mixer.hotkeys import manager as manager_module
from sound_mixer.hotkeys.manager import HotkeyManager
from tests.test_hotkeys_manager import FakeUser32


def test_dynamic_hotkeys_dispatch_identity_and_disable_repeat(qapp, settings, monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(manager_module, "user32", fake)
    preset = settings.create_preset("Game", .5)
    settings.set_hotkey("preset:" + preset["id"], "f9")
    settings.set_hotkey("default_mode", "f10")
    manager = HotkeyManager(settings)
    received = []
    manager.preset_toggled.connect(received.append)
    manager.default_mode.connect(lambda: received.append(None))
    try:
        manager.start()
        for combo, expected in (("f9", preset["id"]), ("f10", None)):
            modifiers, vk = combo_to_hotkey(combo)
            hotkey_id = next(key for key, value in fake.registered.items() if value == (modifiers | MOD_NOREPEAT, vk))
            manager._handle_hotkey(hotkey_id)
            assert received[-1] == expected
        presets = settings.get_presets()
        presets[0]["name"] = "Renamed"
        settings.set_presets(presets)
        manager.reload()
        assert len(fake.registered) == 3
        settings.delete_preset(preset["id"])
        manager.reload()
        assert len(fake.registered) == 2
    finally:
        manager.stop()
    assert not fake.registered


def test_conflicts_use_equivalent_key_combinations():
    bindings = [{"action": "a", "combo": "ctrl+shift+f9", "enabled": True},
                {"action": "b", "combo": "shift+ctrl+f9", "enabled": True}]
    with pytest.raises(ValueError, match="already assigned"):
        validate_bindings(bindings)
    bindings[1]["enabled"] = False
    validate_bindings(bindings)
