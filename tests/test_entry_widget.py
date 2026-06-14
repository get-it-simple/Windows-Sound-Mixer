from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QSizePolicy

from sound_mixer.mixer.model import MixerEntry
from sound_mixer.overlay.entry_widget import BASE_SPINBOX_WIDTH_PX, EntryWidget


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


def test_apply_scale_resizes_spinbox(qapp):
    widget = EntryWidget()

    widget.apply_scale(2.0)

    assert widget._volume_spinbox.width() == round(BASE_SPINBOX_WIDTH_PX * 2.0)


def test_entry_layout_places_name_above_volume_mixer(qapp):
    widget = EntryWidget()
    layout = widget.layout()
    mixer_layout = layout.itemAt(1).layout()

    assert layout.itemAt(0).widget() == widget._label
    assert mixer_layout.indexOf(widget._mute_button) >= 0
    assert mixer_layout.indexOf(widget._slider) >= 0
    assert mixer_layout.indexOf(widget._volume_spinbox) >= 0


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


def test_long_entry_name_is_limited_to_widget_width(qapp):
    widget = EntryWidget()
    widget.resize(160, 90)
    widget.show()
    qapp.processEvents()

    long_name = "Very Long Application Name That Should Not Stretch The Overlay"
    widget.set_entry(MixerEntry(key="long.exe", display_name=long_name, volume=0.5, muted=False, is_master=False), focused=False)
    qapp.processEvents()

    assert widget._label.text() != long_name
    assert widget._label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert widget._label.width() <= widget.width()
