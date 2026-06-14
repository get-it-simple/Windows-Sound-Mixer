import re

from PySide6.QtWidgets import QWidget

from sound_mixer.overlay.win_effects import apply_acrylic_effect, get_accent_color


def test_apply_acrylic_effect_does_not_raise(qapp):
    widget = QWidget()

    apply_acrylic_effect(widget)


def test_get_accent_color_returns_hex_color():
    color = get_accent_color()

    assert re.fullmatch(r"#[0-9a-f]{6}", color)
