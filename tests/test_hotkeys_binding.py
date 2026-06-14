import pytest

from sound_mixer.hotkeys.binding import (
    HotkeyBinding,
    normalize_combo,
    parse_combo,
    to_keyboard_combo,
)
from sound_mixer.settings.schema import DEFAULT_HOTKEYS


def test_normalize_combo_lowercases_and_strips():
    assert normalize_combo(" Ctrl + ALT + Num5 ") == "ctrl+alt+num5"


def test_normalize_combo_empty():
    assert normalize_combo("") == ""


def test_parse_combo_returns_tokens():
    assert parse_combo("ctrl+alt+num5") == ["ctrl", "alt", "num5"]


def test_parse_combo_empty_returns_empty_list():
    assert parse_combo("") == []


def test_parse_combo_invalid_token_raises():
    with pytest.raises(ValueError):
        parse_combo("ctrl+banana")


def test_parse_combo_accepts_function_and_arrow_keys():
    assert parse_combo("ctrl+shift+f12") == ["ctrl", "shift", "f12"]
    assert parse_combo("alt+up") == ["alt", "up"]


@pytest.mark.parametrize("hotkey", DEFAULT_HOTKEYS)
def test_default_hotkeys_parse_successfully(hotkey):
    if not hotkey["enabled"] and not hotkey["combo"]:
        assert parse_combo(hotkey["combo"]) == []
    else:
        assert parse_combo(hotkey["combo"])


def test_to_keyboard_combo_converts_numpad_digits():
    assert to_keyboard_combo("ctrl+alt+num5") == "ctrl+alt+num 5"


def test_to_keyboard_combo_converts_win_modifier():
    assert to_keyboard_combo("win+s") == "windows+s"


def test_hotkey_binding_round_trip():
    data = {"action": "toggle_overlay", "combo": "ctrl+alt+num5", "enabled": True}
    binding = HotkeyBinding.from_dict(data)

    assert binding.action == "toggle_overlay"
    assert binding.combo == "ctrl+alt+num5"
    assert binding.enabled is True
    assert binding.to_dict() == data
