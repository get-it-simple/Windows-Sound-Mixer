import pytest
from PySide6.QtCore import QAbstractAnimation, QEvent, QPointF
from PySide6.QtGui import QEnterEvent

from sound_mixer.mixer.model import MixerEntry
from sound_mixer.overlay.entry_widget import EntryWidget
from sound_mixer.overlay.guide import GuideDialog, _MarqueeLabel
from sound_mixer.overlay.marquee import MarqueeLabel


def enter(qapp, widget):
    qapp.sendEvent(widget, QEnterEvent(QPointF(), QPointF(), QPointF()))


def test_entry_marquee_runs_only_on_hover_and_survives_volume_updates(qapp):
    widget = EntryWidget()
    entry = MixerEntry("long.exe", "A very long application name " * 8, 0.5, False)
    widget.set_entry(entry, focused=False)
    widget.resize(320, 100)
    widget.show()
    qapp.processEvents()
    label = widget._process_name_label
    try:
        assert label.width() < label.fontMetrics().horizontalAdvance(entry.display_name)
        enter(qapp, widget)
        label._group.setCurrentTime(500)
        assert label.xOffset < 0
        offset = label.xOffset
        entry.volume = 0.6
        widget.set_entry(entry, focused=False)
        assert label.xOffset == offset
        qapp.sendEvent(widget, QEvent(QEvent.Type.Leave))
        assert label.xOffset == 0
        assert label._group.state() == QAbstractAnimation.State.Stopped
        enter(qapp, widget)
        label._group.setCurrentTime(500)
        widget.hide()
        assert label.xOffset == 0
        assert label._group.state() == QAbstractAnimation.State.Stopped
    finally:
        widget.close()


@pytest.mark.parametrize("change", ["text", "width", "font"])
def test_hovered_marquee_recalculates_overflow(qapp, change):
    label = MarqueeLabel("Application name")
    label.resize(500, 60)
    label.show()
    label.start_marquee()
    assert label._group.state() == QAbstractAnimation.State.Stopped
    try:
        if change == "text":
            label.setText("Long application name " * 20)
        elif change == "width":
            label.resize(25, 60)
        else:
            font = label.font()
            font.setPixelSize(100)
            label.setFont(font)
        qapp.processEvents()
        label._group.setCurrentTime(label._fwd.duration() // 2)
        assert label.xOffset < 0
        label.setText("A")
        label.resize(500, 60)
        assert label.xOffset == 0
        assert label._group.state() == QAbstractAnimation.State.Stopped
    finally:
        label.close()


def test_guide_uses_shared_marquee_and_row_hover(qapp):
    dialog = GuideDialog()
    dialog.show()
    label = dialog.findChildren(_MarqueeLabel)[0]
    label.setText("Long guide description " * 20)
    try:
        assert isinstance(label, MarqueeLabel)
        enter(qapp, label.parentWidget())
        label._group.setCurrentTime(label._fwd.duration() // 2)
        assert label.xOffset < 0
        qapp.sendEvent(label.parentWidget(), QEvent(QEvent.Type.Leave))
        assert label.xOffset == 0
    finally:
        dialog.close()
