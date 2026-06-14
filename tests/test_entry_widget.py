from sound_mixer.mixer.model import MixerEntry
from sound_mixer.overlay.entry_widget import BASE_SPINBOX_WIDTH_PX, EntryWidget


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
