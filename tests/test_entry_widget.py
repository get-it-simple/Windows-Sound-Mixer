import re

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QWheelEvent

from sound_mixer.mixer.model import MixerEntry
from sound_mixer.overlay.entry_widget import BASE_APP_ICON_PX, BASE_FONT_PX, EntryWidget, slider_style


def wheel_event(direction: int = 1) -> QWheelEvent:
    from PySide6.QtCore import Qt

    return QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(0, 120 * direction),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def wheel_event_horizontal(direction: int = 1) -> QWheelEvent:
    from PySide6.QtCore import Qt

    return QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(120 * direction, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.AltModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def make_entry(volume: float = 0.5, muted: bool = False) -> MixerEntry:
    return MixerEntry(key="chrome.exe", display_name="Google Chrome", volume=volume, muted=muted, is_master=False)


def test_set_entry_updates_spinbox_value(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(volume=0.42), focused=False)

    assert widget._volume_spinbox.value() == 42
    assert widget._slider.value() == 42


def test_editing_spinbox_emits_volume_changed(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    received = []
    widget.volume_changed.connect(received.append)
    focus_requests = []
    widget.focus_requested.connect(lambda: focus_requests.append(True))

    widget._volume_spinbox.setValue(75)

    assert received == [0.75]
    assert focus_requests == [True]


def test_set_entry_does_not_emit_volume_changed(qapp):
    widget = EntryWidget()

    received = []
    widget.volume_changed.connect(received.append)

    widget.set_entry(make_entry(volume=0.42), focused=False)

    assert received == []


def test_apply_scale_resizes_spinbox_font(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._volume_spinbox.font().pixelSize() == round(BASE_FONT_PX * 2.0)


def test_apply_scale_fits_spinbox_to_max_value_text(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._volume_spinbox.width() == widget._volume_spinbox.minimumSizeHint().width()


def test_entry_layout_places_icon_mute_spinbox_and_slider_in_order(qapp):
    widget = EntryWidget()
    layout = widget.layout()

    mute_idx = layout.indexOf(widget._mute_button)
    spinbox_idx = layout.indexOf(widget._volume_spinbox)
    column_idx = layout.indexOf(widget._slider_column)

    assert mute_idx > -1
    assert spinbox_idx > mute_idx
    assert column_idx > spinbox_idx
    assert widget._slider_column.layout().indexOf(widget._slider) == 0
    assert widget._slider_column.layout().indexOf(widget._process_name_label) == 1


def test_scroll_on_slider_uses_entry_wheel_handling(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)
    focus_requests = []
    widget.focus_requested.connect(lambda: focus_requests.append(True))

    handled = widget.eventFilter(widget._slider, wheel_event(direction=1))

    assert handled is True
    assert scrolled == [1]
    assert focus_requests == [True]


def test_scroll_on_spinbox_uses_entry_wheel_handling(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    handled = widget.eventFilter(widget._volume_spinbox, wheel_event(direction=-1))

    assert handled is True
    assert scrolled == [-1]


def test_set_entry_shows_display_name_as_tooltip(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(volume=0.5), focused=False)

    assert widget._icon_label.toolTip() == "Google Chrome"


def test_set_entry_hides_icon_for_master(qapp):
    widget = EntryWidget()

    widget.set_entry(
        MixerEntry(key="master", display_name="System", volume=0.5, muted=False, is_master=True), focused=False
    )

    assert widget._icon_container.isHidden()


def test_set_entry_shows_fallback_icon_for_unknown_app(qapp):
    widget = EntryWidget()

    widget.set_entry(make_entry(volume=0.5), focused=False)

    assert not widget._icon_label.pixmap().isNull()


def test_apply_scale_resizes_icon_label(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._icon_label.width() == round(BASE_APP_ICON_PX * 2.0)
    assert widget._icon_label.height() == round(BASE_APP_ICON_PX * 2.0)


@pytest.mark.parametrize("scale_percent", range(50, 301))
def test_slider_handle_stays_round_at_every_scale(scale_percent):
    css = slider_style(scale_percent / 100, "#3a96dd")

    handle_size = int(re.search(r"QSlider::handle:horizontal \{\s*width: (\d+)px", css).group(1))
    groove_height = int(re.search(r"QSlider::groove:horizontal \{\s*height: (\d+)px", css).group(1))

    # The handle is centered over the groove with a negative margin; if the
    # difference is odd, Qt renders the handle as a square instead of a circle.
    assert (handle_size - groove_height) % 2 == 0


def test_hide_button_hidden_by_default(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(), focused=False)

    assert widget._hide_button.isHidden()



def test_hide_button_hidden_when_unfocused(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(), focused=True)
    widget.set_entry(make_entry(), focused=False)

    assert widget._hide_button.isHidden()


def test_hide_button_emits_ignore_requested(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(), focused=True)

    received = []
    widget.ignore_requested.connect(lambda: received.append(True))
    focus_requests = []
    widget.focus_requested.connect(lambda: focus_requests.append(True))

    widget._hide_button.click()

    assert received == [True]
    assert focus_requests == [True]


def test_set_ignore_tooltip_changes_button_tooltip(qapp):
    widget = EntryWidget()

    widget.set_ignore_tooltip("Restore")

    assert widget._hide_button.toolTip() == "Restore"


def test_hide_button_default_tooltip_is_ignore(qapp):
    widget = EntryWidget()

    assert widget._hide_button.toolTip() == "Ignore"


def test_apply_scale_resizes_hide_button_icon(qapp):
    from sound_mixer.overlay.entry_widget import BASE_ICON_PX

    widget = EntryWidget()

    widget.apply_scale(2.0)

    expected = round(BASE_ICON_PX * 2.0)
    assert widget._hide_button.iconSize().width() == expected
    assert widget._hide_button.iconSize().height() == expected


def test_scroll_up_with_alt_held_increases_volume(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    widget.wheelEvent(wheel_event_horizontal(direction=1))

    assert scrolled == [1]


def test_scroll_down_with_alt_held_decreases_volume(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    widget.wheelEvent(wheel_event_horizontal(direction=-1))

    assert scrolled == [-1]


def test_process_name_label_text_set_from_entry(qapp):
    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)
    assert widget._process_name_label.text() == "Google Chrome"


def test_process_name_label_is_left_aligned(qapp):
    from PySide6.QtCore import Qt

    widget = EntryWidget()
    assert widget._process_name_label.alignment() & Qt.AlignmentFlag.AlignLeft


def test_zero_delta_wheel_event_does_not_scroll(qapp):
    from PySide6.QtCore import Qt

    widget = EntryWidget()
    widget.set_entry(make_entry(volume=0.5), focused=False)

    scrolled = []
    widget.scrolled.connect(scrolled.append)

    zero_event = QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    widget.wheelEvent(zero_event)

    assert scrolled == []
