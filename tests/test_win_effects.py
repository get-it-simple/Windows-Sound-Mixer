import re

from PySide6.QtWidgets import QWidget

from sound_mixer.overlay.win_effects import apply_acrylic_effect, get_accent_color


def test_apply_acrylic_effect_does_not_raise(qapp):
    widget = QWidget()

    apply_acrylic_effect(widget)


def test_get_accent_color_returns_hex_color():
    color = get_accent_color()

    assert re.fullmatch(r"#[0-9a-f]{6}", color)


def test_raise_without_activating_preserves_focus_and_geometry(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from sound_mixer.overlay import win_effects

    set_window_pos = Mock(return_value=True)
    monkeypatch.setattr(win_effects, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(win_effects.ctypes, "windll", SimpleNamespace(
        user32=SimpleNamespace(SetWindowPos=set_window_pos),
    ))
    window = SimpleNamespace(winId=lambda: 0x100000001)

    win_effects.raise_without_activating(window)

    set_window_pos.assert_called_once_with(0x100000001, -1, 0, 0, 0, 0, 0x13)
    assert len(set_window_pos.argtypes) == 7


def test_raise_without_activating_is_noop_off_windows(monkeypatch):
    from types import SimpleNamespace
    from sound_mixer.overlay import win_effects

    monkeypatch.setattr(win_effects, "sys", SimpleNamespace(platform="linux"))
    win_effects.raise_without_activating(None)
