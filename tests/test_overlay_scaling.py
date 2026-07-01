from unittest.mock import patch

from sound_mixer.audio.fake_backend import FakeAudioSession
from sound_mixer.mixer.model import MixerModel
from sound_mixer.overlay.entry_widget import BASE_ICON_PX as ENTRY_BASE_ICON_PX
from sound_mixer.overlay.window import BASE_FONT_PX, BASE_ICON_PX, OverlayWindow


def make_overlay(qapp, fake_backend, settings) -> OverlayWindow:
    model = MixerModel(fake_backend, settings)
    return OverlayWindow(model, settings)


def test_default_scale_applies_base_sizes(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    assert f"{BASE_FONT_PX}px" in overlay._background.styleSheet()
    assert overlay._close_button.iconSize().width() == BASE_ICON_PX
    for widget in overlay._entry_widgets:
        assert widget._mute_button.iconSize().width() == ENTRY_BASE_ICON_PX


def test_apply_scale_resizes_icons_and_font(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    settings.set_ui_scale(2.0)
    overlay.apply_scale()

    assert f"{BASE_FONT_PX * 2}px" in overlay._background.styleSheet()
    assert overlay._close_button.iconSize().width() == BASE_ICON_PX * 2
    for widget in overlay._entry_widgets:
        assert widget._mute_button.iconSize().width() == ENTRY_BASE_ICON_PX * 2


def test_background_style_highlights_focused_entry_with_accent_color(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    style = overlay._background.styleSheet()

    assert f'#entryWidget[focused="true"]' in style
    assert overlay._accent_color in style


def test_new_entry_widgets_inherit_current_scale(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    settings.set_ui_scale(1.5)
    overlay.apply_scale()

    fake_backend.add_session(FakeAudioSession(pid=300, process_name="discord.exe", display_name="Discord", volume=1.0))
    overlay._model.refresh()
    overlay.refresh_view()

    new_widget = overlay._entry_widgets[-1]
    assert new_widget._mute_button.iconSize().width() == round(ENTRY_BASE_ICON_PX * 1.5)


def test_apply_scale_uses_opaque_background_when_transparency_disabled(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)

    assert "rgba(32, 32, 32, 140)" in overlay._background.styleSheet()

    settings.set_transparency_enabled(False)
    overlay.apply_scale()

    style = overlay._background.styleSheet()
    assert "rgba(32, 32, 32, 140)" not in style
    assert "rgb(32, 32, 32)" in style


def test_refresh_accent_color_updates_style_when_color_changes(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay._accent_color = "#aabbcc"

    with patch("sound_mixer.overlay.window.get_accent_color", return_value="#112233"):
        overlay._refresh_accent_color()

    assert overlay._accent_color == "#112233"
    assert "#112233" in overlay._background.styleSheet()


def test_refresh_accent_color_skips_update_when_color_unchanged(qapp, fake_backend, settings):
    overlay = make_overlay(qapp, fake_backend, settings)
    overlay._accent_color = "#aabbcc"
    apply_scale_calls = []
    original_apply_scale = overlay.apply_scale
    overlay.apply_scale = lambda: apply_scale_calls.append(1) or original_apply_scale()

    with patch("sound_mixer.overlay.window.get_accent_color", return_value="#aabbcc"):
        overlay._refresh_accent_color()

    assert apply_scale_calls == []
